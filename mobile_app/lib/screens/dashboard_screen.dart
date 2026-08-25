import 'package:flutter/material.dart';
import 'dart:async';
import '../theme/jarvis_theme.dart';
import '../services/bridge_service.dart';
import '../services/speech_service.dart';
import '../widgets/mic_button.dart';

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
  late SpeechService _speech;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: Duration(seconds: 2),
    )..repeat(reverse: true);
    _statusSub = widget.bridge.statusStream.listen((data) {
      if (mounted) setState(() => stats = data);
    });
    _speech = SpeechService();
    _speech.init();
  }

  void _onVoiceCommand(String command) {
    if (!widget.online || command.isEmpty) return;

    // Show what was recognized
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('🎙 "$command"'),
      backgroundColor: JTheme.surface,
      behavior: SnackBarBehavior.floating,
      duration: Duration(seconds: 2),
    ));

    // Map and execute
    final mapped = _mapCommand(command);
    widget.bridge.runCommand(mapped['tool'] as String,
        args: mapped['args'] as Map<String, dynamic>?).then((result) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(result.length > 150 ? result.substring(0, 150) + '…' : result),
          backgroundColor: JTheme.card,
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 4),
        ));
      }
    });
  }

  Map<String, dynamic> _mapCommand(String input) {
    final l = input.toLowerCase().trim();
    if (l.contains('health')) return {'tool': 'get_laptop_health', 'args': <String,dynamic>{}};
    if (l.contains('threat') || l.contains('risk')) return {'tool': 'daily_threat_board', 'args': <String,dynamic>{}};
    if (l.contains('damage')) return {'tool': 'damage_report', 'args': <String,dynamic>{}};
    if (l.contains('battery')) return {'tool': 'battery_coach', 'args': <String,dynamic>{}};
    if (l.contains('clean slate')) return {'tool': 'run_protocol', 'args': <String,dynamic>{'name':'clean slate'}};
    if (l.contains('study mode')) return {'tool': 'run_protocol', 'args': <String,dynamic>{'name':'study mode'}};
    if (l.contains('catch me up')) return {'tool': 'catch_me_up', 'args': <String,dynamic>{}};
    return {'tool': 'decide_and_act', 'args': <String,dynamic>{'goal': input}};
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
          if (widget.online) ...[
            _buildStatsGrid(),
            SizedBox(height: 20),
            _buildQuickActions(),
            SizedBox(height: 24),
            // VOICE COMMAND BUTTON
            Center(
              child: MicButton(
                speech: _speech,
                onCommand: _onVoiceCommand,
                laptopOnline: widget.online,
              ),
            ),
          ] else
            _buildOfflineMessage(),
        ],
      ),
    );
  }

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
    final online = widget.online;
    final color = online ? JTheme.green : JTheme.red;

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
              // Status dot + label
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Pulsing indicator
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
                    online ? 'LAPTOP ONLINE' : 'LAPTOP OFFLINE',
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
                online
                    ? 'Bridge server reachable — all systems go'
                    : 'Laptop is powered off or bridge not started',
                textAlign: TextAlign.center,
                style: TextStyle(color: JTheme.textSecondary, fontSize: 13),
              ),
              if (!online) ...[
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

  Widget _buildOfflineMessage() {
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: 40),
        child: Column(
          children: [
            Icon(Icons.laptop_windows, size: 60, color: JTheme.textMuted.withOpacity(0.3)),
            SizedBox(height: 16),
            Text('Laptop is offline',
                style: TextStyle(color: JTheme.textMuted, fontSize: 15)),
            SizedBox(height: 6),
            Text('Stats and commands unavailable until it comes back online.',
                textAlign: TextAlign.center,
                style: TextStyle(color: JTheme.textMuted.withOpacity(0.5), fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Future<void> _run(String tool, [Map<String, dynamic>? args]) async {
    final result = await widget.bridge.runCommand(tool, args: args);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(result.length > 200 ? result.substring(0, 200) + '…' : result),
        backgroundColor: JTheme.surface,
        behavior: SnackBarBehavior.floating,
      ));
    }
  }
}