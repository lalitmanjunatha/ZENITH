import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/jarvis_theme.dart';
import '../services/bridge_service.dart';
import '../widgets/toast_host.dart';

class SettingsScreen extends StatefulWidget {
  final BridgeService bridge;
  SettingsScreen({required this.bridge});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _cloudUrlController = TextEditingController();
  final _pinController = TextEditingController();
  final _hostController = TextEditingController();
  bool _useCloud = true;
  String _savedMsg = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _useCloud = prefs.getBool('zenith_use_cloud') ?? true;
      _cloudUrlController.text =
          prefs.getString('zenith_cloud_url') ?? 'https://zenith-cloud-brain.onrender.com';
      _pinController.text = prefs.getString('zenith_pin') ?? '';
      _hostController.text = prefs.getString('laptop_host') ?? '';
    });
  }

  Future<void> _save() async {
    final url = _cloudUrlController.text.trim();
    final pinVal = _pinController.text.trim();
    final host = _hostController.text.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('zenith_use_cloud', _useCloud);
    await prefs.setString('zenith_cloud_url', url);
    await prefs.setString('zenith_pin', pinVal);
    if (host.isNotEmpty) {
      await prefs.setString('laptop_host', host);
      widget.bridge.host = host;
    }
    if (_useCloud && url.isNotEmpty) {
      widget.bridge.configureCloud(url: url, pinValue: pinVal);
    } else {
      widget.bridge.configureCloud(url: '', pinValue: '');
    }
    setState(() => _savedMsg =
        'Saved · Mode: ${_useCloud ? "CLOUD ☁️" : "LAN 💻"}${_useCloud && pinVal.isEmpty ? " (PIN missing!)" : ""}');
    ZenithToasts.success(_savedMsg);
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('CONNECTION MODE',
              style: TextStyle(
                  color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
          SizedBox(height: 12),
          Container(
            padding: EdgeInsets.all(16),
            decoration: JTheme.glassCard(),
            child: Column(
              children: [
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('Use Cloud Brain ☁️',
                      style: TextStyle(
                          color: JTheme.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600)),
                  subtitle: Text(
                      'Works anywhere via render.com.\nOFF = direct laptop on same Wi-Fi.',
                      style:
                          TextStyle(color: JTheme.textMuted, fontSize: 11)),
                  value: _useCloud,
                  activeColor: JTheme.cyan,
                  onChanged: (v) => setState(() => _useCloud = v),
                ),
                SizedBox(height: 12),
                TextField(
                  controller: _cloudUrlController,
                  enabled: _useCloud,
                  style: TextStyle(color: JTheme.textPrimary, fontSize: 13),
                  decoration: InputDecoration(
                    labelText: 'Cloud Brain URL',
                    labelStyle: TextStyle(color: JTheme.textMuted, fontSize: 12),
                    hintText: 'https://zenith-cloud-brain.onrender.com',
                    hintStyle: TextStyle(fontSize: 12),
                  ),
                ),
                SizedBox(height: 12),
                TextField(
                  controller: _pinController,
                  enabled: _useCloud,
                  obscureText: true,
                  style: TextStyle(color: JTheme.textPrimary, fontSize: 14, letterSpacing: 3),
                  decoration: InputDecoration(
                    labelText: 'Pairing PIN',
                    labelStyle: TextStyle(color: JTheme.textMuted, fontSize: 12),
                    hintText: 'same as Render BRIDGE_PIN',
                    hintStyle: TextStyle(letterSpacing: 0, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _save,
            icon: Icon(Icons.cloud_sync, size: 18),
            label: Text('Save Connection', style: TextStyle(fontWeight: FontWeight.w600)),
            style: ElevatedButton.styleFrom(
              backgroundColor: JTheme.cyan,
              foregroundColor: JTheme.bg,
              minimumSize: Size(double.infinity, 46),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
          ),
          SizedBox(height: 24),
          Text('LAN FALLBACK (OPTIONAL)',
              style: TextStyle(
                  color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
          SizedBox(height: 12),
          Container(
            padding: EdgeInsets.all(16),
            decoration: JTheme.glassCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Laptop IP (direct Wi-Fi mode)',
                    style: TextStyle(color: JTheme.textSecondary, fontSize: 12)),
                SizedBox(height: 8),
                TextField(
                  controller: _hostController,
                  style: TextStyle(color: JTheme.textPrimary, fontSize: 14),
                  decoration: InputDecoration(hintText: '192.168.1.100'),
                ),
              ],
            ),
          ),
          SizedBox(height: 24),
          Text('ABOUT',
              style: TextStyle(
                  color: JTheme.textMuted, fontSize: 11, letterSpacing: 1.5)),
          SizedBox(height: 12),
          Container(
            padding: EdgeInsets.all(16),
            decoration: JTheme.glassCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ZENITH Mobile v2.0 — Cloud Edition',
                    style: TextStyle(
                        color: JTheme.cyan,
                        fontWeight: FontWeight.bold,
                        fontSize: 14)),
                SizedBox(height: 6),
                Text(
                    'Talk to ZENITH from anywhere. Phone tools run natively; '
                    'laptop tools run remotely with your confirmation.',
                    style: TextStyle(color: JTheme.textSecondary, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
