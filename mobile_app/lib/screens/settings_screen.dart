import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/jarvis_theme.dart';
import '../services/bridge_service.dart';

class SettingsScreen extends StatefulWidget {
  final BridgeService bridge;
  SettingsScreen({required this.bridge});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _hostController = TextEditingController();
  String _savedHost = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _savedHost = prefs.getString('laptop_host') ?? '';
      _hostController.text = _savedHost;
    });
  }

  Future<void> _save() async {
    final host = _hostController.text.trim();
    if (host.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('laptop_host', host);
    widget.bridge.host = host;
    setState(() => _savedHost = host);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('Laptop address saved: $host'),
      backgroundColor: JTheme.surface,
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('CONNECTION',
              style: TextStyle(color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
          SizedBox(height: 12),
          Container(
            padding: EdgeInsets.all(16),
            decoration: JTheme.glassCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Laptop IP Address',
                    style: TextStyle(color: JTheme.textSecondary, fontSize: 12)),
                SizedBox(height: 8),
                TextField(
                  controller: _hostController,
                  style: TextStyle(color: JTheme.textPrimary, fontSize: 14),
                  decoration: InputDecoration(hintText: '192.168.1.100'),
                ),
                SizedBox(height: 12),
                ElevatedButton(
                  onPressed: _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: JTheme.cyan,
                    foregroundColor: JTheme.bg,
                    minimumSize: Size(double.infinity, 44),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  child: Text('Save & Connect', style: TextStyle(fontWeight: FontWeight.w600)),
                ),
                if (_savedHost.isNotEmpty)
                  Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text('Connected to: $_savedHost',
                        style: TextStyle(color: JTheme.textMuted, fontSize: 11)),
                  ),
              ],
            ),
          ),
          SizedBox(height: 24),
          Text('ABOUT',
              style: TextStyle(color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
          SizedBox(height: 12),
          Container(
            padding: EdgeInsets.all(16),
            decoration: JTheme.glassCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ZENITH Mobile v1.0', style: TextStyle(
                    color: JTheme.cyan, fontWeight: FontWeight.bold, fontSize: 14)),
                SizedBox(height: 6),
                Text('Cross-device manager for your Zenith AI laptop.\n'
                     'Monitor status · Send commands · Get notified when it boots.',
                     style: TextStyle(color: JTheme.textSecondary, fontSize: 12)),
                SizedBox(height: 8),
                Text('Make sure the Zenith bridge server is running on your laptop '
                     '(it starts automatically with the agent).',
                     style: TextStyle(color: JTheme.textMuted, fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}