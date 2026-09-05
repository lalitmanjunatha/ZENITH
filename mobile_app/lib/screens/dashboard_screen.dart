import 'package:flutter/material.dart';
import 'dart:async';
import '../theme/jarvis_theme.dart';
import '../services/bridge_service.dart';
import '../services/whisper_listening_service.dart';
import '../services/phone_tools.dart';
import '../widgets/toast_host.dart';

class DashboardScreen extends StatefulWidget {
  final BridgeService bridge;
  final bool online;
  DashboardScreen({required this.bridge, required this.online});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  StreamSubscription? _statusSub;
  Map<String, dynamic>? stats;
  final PhoneTools _phone = PhoneTools();
  final WhisperListeningService _listener = WhisperListeningService();
  bool _listeningOn = false;
  String _voiceStatus = '';

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: Duration(seconds: 2),
    )..repeat(reverse: true);
    _statusSub = widget.bridge.statusStream.listen((data) {
      if (!mounted) return;
      setState(() => stats = data);
      _checkLaptopTransition(data);
    });
  }

  bool? _lastLaptopOnline;

  void _checkLaptopTransition(Map<String, dynamic> data) {
    final cloud = data['_cloud'] as Map?;
    final online =
        ((cloud?['laptop'] as Map?)?['online'] == true);
    final prev = _lastLaptopOnline;
    _lastLaptopOnline = online;
    if (prev == null || prev == online) return;
    ZenithToasts.success(online
        ? 'Your laptop just came ONLINE!'
        : 'Your laptop just went offline');
  }

  void _onVoiceCommand(String command) {
    if (command.isEmpty) return;
    ZenithToasts.clear();
    ZenithToasts.info('ZENITH thinking about "$command"…',
        duration: const Duration(seconds: 45));

    widget.bridge.askBrain(command).then((reply) async {
      if (!mounted) return;
      if (reply.type == 'confirm' && reply.session != null) {
        ZenithToasts.clear();
        final yes = await _askConfirmDialog(reply.reply);
        final answer = yes ? 'yes do it' : 'no cancel';
        ZenithToasts.success(yes ? '▶️ Running on laptop…' : '🚫 Cancelled');
        final finalReply =
            await widget.bridge.respondConfirm(reply.session!, answer);
        if (mounted) {
          ZenithToasts.clear();
          _showBrainReply(finalReply.reply);
        }
      } else {
        if (mounted) {
          ZenithToasts.clear();
          _showBrainReply(reply.reply);
        }
      }
      _listener.onCommandProcessed();
    });
  }

  void _showBrainReply(String text) {
    if (!mounted) return;
    if (_listeningOn && text.length <= 160) {
      _phone.execute('phone_tts_speak', {'text': text});
    }
    if (text.length > 220) {
      showDialog(context: context, builder: (_) => AlertDialog(
        backgroundColor: JTheme.card,
        title: Text('ZENITH', style: TextStyle(color: JTheme.cyan, fontSize: 16)),
        content: SingleChildScrollView(child: Text(text, style: TextStyle(color: JTheme.textPrimary))),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text('OK', style: TextStyle(color: JTheme.cyan)))],
      ));
      return;
    }
    ZenithToasts.info(text, duration: const Duration(seconds: 6));
  }

  Future<bool> _askConfirmDialog(String question) async {
    final result = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        backgroundColor: JTheme.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: JTheme.cyan.withOpacity(0.4))),
        title: Row(children: [
          Icon(Icons.laptop_windows, color: JTheme.cyan, size: 20),
          SizedBox(width: 8),
          Text('Laptop Tool', style: TextStyle(color: JTheme.cyan, fontSize: 15)),
        ]),
        content: Text(question, style: TextStyle(color: JTheme.textPrimary)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: Text('No', style: TextStyle(color: JTheme.textMuted))),
          ElevatedButton(onPressed: () => Navigator.pop(context, true),
              style: ElevatedButton.styleFrom(backgroundColor: JTheme.cyan, foregroundColor: JTheme.bg),
              child: Text('Yes, run it')),
        ],
      ),
    );
    return result ?? false;
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _statusSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          SizedBox(height: 20),
          _buildStatusCard(),
          SizedBox(height: 20),
          if (_hasStats()) ...[
            _buildStatsGrid(),
            SizedBox(height: 20),
          ],
          if (widget.online && !widget.bridge.useCloud) _buildQuickActions(),
          SizedBox(height: 8),
          _buildPhoneActions(),
          if (widget.bridge.useCloud && widget.bridge.pinConfigured) ...[
            SizedBox(height: 12),
            Center(
              child: Container(
                padding: EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: JTheme.surface.withOpacity(0.7),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: JTheme.cyan.withOpacity(0.25)),
                ),
                child: Text(
                  widget.online
                      ? 'Brain · Laptop ONLINE'
                      : 'Brain · Laptop offline',
                  style: TextStyle(color: JTheme.textMuted, fontSize: 11),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _toggleListening() async {
    if (_listeningOn) {
      _listener.stop();
      setState(() { _listeningOn = false; _voiceStatus = ''; });
      ZenithToasts.info('Voice OFF', duration: const Duration(seconds: 2));
      return;
    }

    // Request RECORD_AUDIO permission first
    final granted = await _phone.requestPermissions(['android.permission.RECORD_AUDIO']);
    if (!granted) {
      ZenithToasts.error('Microphone permission denied', duration: const Duration(seconds: 3));
      return;
    }

    _listener.onStatus = (s) {
      if (mounted) setState(() => _voiceStatus = s);
    };
    _listener.onListening = () {
      if (!mounted) return;
      ZenithToasts.success('Yes? Speak your command.', duration: const Duration(seconds: 3));
      _phone.execute('phone_tts_speak', {'text': 'Yes?'});
    };
    _listener.onCommand = (cmd) {
      if (!mounted) return;
      _onVoiceCommand(cmd);
    };
    final started = await _listener.start();
    if (mounted) {
      setState(() => _listeningOn = started);
      if (!started) {
        ZenithToasts.error(_listener.lastError ?? 'Failed to start mic', duration: const Duration(seconds: 3));
      }
    }
  }

  Widget _buildPhoneActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('VOICE',
            style: TextStyle(
                color: JTheme.textMuted,
                fontSize: 11,
                letterSpacing: 1.5)),
        const SizedBox(height: 10),
        InkWell(
          onTap: _toggleListening,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
            decoration: BoxDecoration(
              color: _listeningOn
                  ? JTheme.cyan.withOpacity(0.15)
                  : JTheme.card.withOpacity(0.6),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color:
                      (_listeningOn ? JTheme.cyan : JTheme.border).withOpacity(0.4)),
            ),
            child: Row(children: [
              Icon(_listeningOn ? Icons.graphic_eq : Icons.mic_none,
                  color: _listeningOn ? JTheme.cyan : JTheme.textMuted, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _listeningOn
                      ? 'ALWAYS ON - say "ZENITH" + command'
                      : 'Tap to enable always-listening',
                  style: TextStyle(
                      color: _listeningOn ? JTheme.cyan : JTheme.textSecondary,
                      fontSize: 11),
                ),
              ),
              Icon(Icons.power_settings_new,
                  size: 16,
                  color: _listeningOn ? JTheme.green : JTheme.textMuted),
            ]),
          ),
        ),
        if (_listeningOn && _voiceStatus.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(_voiceStatus,
              style: TextStyle(color: JTheme.textMuted, fontSize: 10)),
        ],
      ],
    );
  }

  bool _hasStats() =>
      widget.online || (stats?.containsKey('cpu_pct') ?? false);

  Widget _buildHeader() {
    return Row(
      children: [
        Container(
          width: 42, height: 42,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(colors: [JTheme.cyan.withOpacity(0.3), Colors.transparent]),
            border: Border.all(color: JTheme.cyan.withOpacity(0.5)),
          ),
          child: Icon(Icons.smart_toy_outlined, color: JTheme.cyan, size: 24),
        ),
        SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('ZENITH', style: TextStyle(color: JTheme.cyan, fontSize: 22,
                fontWeight: FontWeight.bold, letterSpacing: 3)),
            Text('Cross-Device Manager', style: TextStyle(color: JTheme.textSecondary, fontSize: 12)),
          ],
        ),
      ],
    );
  }

  Widget _buildStatusCard() {
    final cloud = (stats?['_cloud'] as Map?) ?? const {};
    final cloudLaptopOnline = (cloud['laptop'] as Map?)?['online'] == true;
    final brainOk = widget.online;

    final laptopOnline = widget.bridge.useCloud
        ? (stats != null ? cloudLaptopOnline : brainOk)
        : brainOk;
    final color = laptopOnline ? JTheme.green : JTheme.red;
    final title = widget.bridge.useCloud
        ? (laptopOnline ? 'LAPTOP ONLINE · CLOUD' : 'LAPTOP OFFLINE · CLOUD OK')
        : (brainOk ? 'LAPTOP ONLINE' : 'LAPTOP OFFLINE');
    final sub = widget.bridge.useCloud
        ? (laptopOnline
            ? 'Cloud brain linked - laptop daemon reporting'
            : 'Brain reachable. Run START_ZENITH_CLOUD.bat on laptop.')
        : (brainOk
            ? 'Bridge server reachable - all systems go'
            : 'Laptop is powered off or bridge not started');

    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          width: double.infinity,
          padding: EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: JTheme.card.withOpacity(0.8),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: color.withOpacity(0.3 + _pulseController.value * 0.3),
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: color.withOpacity(0.1 + _pulseController.value * 0.1),
                blurRadius: 20,
                spreadRadius: 2,
              ),
            ],
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 14, height: 14,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: color,
                      boxShadow: [
                        BoxShadow(
                          color: color.withOpacity(0.3 + _pulseController.value * 0.5),
                          blurRadius: 8 + _pulseController.value * 8,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                  ),
                  SizedBox(width: 12),
                  Text(
                    title,
                    style: TextStyle(
                      color: color,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
              SizedBox(height: 12),
              Text(
                sub,
                textAlign: TextAlign.center,
                style: TextStyle(color: JTheme.textSecondary, fontSize: 13),
              ),
              if (!laptopOnline) ...[
                SizedBox(height: 8),
                Text(
                  'I\'ll notify you the moment it comes online.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: JTheme.cyanDim, fontSize: 12, fontStyle: FontStyle.italic),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildStatsGrid() {
    final s = stats ?? {};
    return GridView.count(
      shrinkWrap: true,
      physics: NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.6,
      children: [
        _statCard('CPU', '${s['cpu_pct'] ?? '--'}%', Icons.memory, JTheme.cyan),
        _statCard('RAM', '${s['ram_pct'] ?? '--'}%', Icons.storage, JTheme.amber),
        _statCard('Disk Free', '${s['disk_free_gb'] ?? '--'} GB', Icons.folder_open, JTheme.green),
        _statCard('Battery', s['battery_pct'] != null ? '${s['battery_pct']}%' : 'N/A',
            Icons.battery_charging_full, JTheme.red),
      ],
    );
  }

  Widget _statCard(String label, String value, IconData icon, Color accent) {
    return Container(
      padding: EdgeInsets.all(14),
      decoration: JTheme.glassCard(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(icon, color: accent, size: 18),
              Text(label.toUpperCase(),
                  style: TextStyle(color: JTheme.textMuted, fontSize: 9, letterSpacing: 1)),
            ],
          ),
          SizedBox(height: 6),
          Text(value,
              style: TextStyle(color: JTheme.textPrimary, fontSize: 22, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }

  Widget _buildQuickActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('QUICK ACTIONS',
            style: TextStyle(color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
        SizedBox(height: 10),
        Wrap(
          spacing: 8, runSpacing: 8,
          children: [
            _actionChip('Health Check', Icons.monitor_heart, () => _run('get_laptop_health')),
            _actionChip('Threat Board', Icons.security, () => _run('daily_threat_board')),
            _actionChip('Clean Slate', Icons.cleaning_services, () => _run('run_protocol', {'name': 'clean slate'})),
            _actionChip('Study Mode', Icons.school, () => _run('run_protocol', {'name': 'study mode'})),
            _actionChip('Damage Report', Icons.healing, () => _run('damage_report')),
            _actionChip('Battery Coach', Icons.battery_saver, () => _run('battery_coach')),
          ],
        ),
      ],
    );
  }

  Widget _actionChip(String label, IconData icon, VoidCallback onTap) {
    return InkWell(
      onTap: widget.online ? onTap : null,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: widget.online ? JTheme.surface : JTheme.surface.withOpacity(0.4),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: widget.online ? JTheme.border : JTheme.textMuted.withOpacity(0.2)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: widget.online ? JTheme.cyan : JTheme.textMuted),
            SizedBox(width: 6),
            Text(label, style: TextStyle(
              color: widget.online ? JTheme.textPrimary : JTheme.textMuted,
              fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Future<void> _run(String tool, [Map<String, dynamic>? args]) async {
    final result = await widget.bridge.runCommand(tool, args: args);
    if (mounted) {
      ZenithToasts.info(
        result.length > 200 ? result.substring(0, 200) + '…' : result,
      );
    }
  }
}
