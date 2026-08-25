import 'package:flutter/material.dart';
import 'dart:async';
import 'theme/jarvis_theme.dart';
import 'services/bridge_service.dart';
import 'screens/dashboard_screen.dart';
import 'screens/command_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(ZenithMobileApp());
}

class ZenithMobileApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ZENITH',
      theme: JTheme.dark(),
      home: HomeShell(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class HomeShell extends StatefulWidget {
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  late BridgeService bridge;
  bool laptopOnline = false;
  StreamSubscription? _connSub;

  @override
  void initState() {
    super.initState();
    bridge = BridgeService(host: '192.168.1.100'); // TODO: make configurable
    bridge.startPolling(intervalSec: 8);
    _connSub = bridge.connectionStream.listen((online) {
      setState(() => laptopOnline = online);
      if (online) {
        _showLaptopOnlineSnackBar();
      }
    });
    // Initial check
    bridge.ping().then((v) => setState(() => laptopOnline = v));
  }

  void _showLaptopOnlineSnackBar() {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(Icons.laptop_windows, color: JTheme.green),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Your laptop just came online!',
                style: TextStyle(color: JTheme.textPrimary),
              ),
            ),
          ],
        ),
        backgroundColor: JTheme.surface,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: JTheme.green.withOpacity(0.4)),
        ),
        duration: Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [JTheme.bg, Color(0xFF0D1420)],
          ),
        ),
        child: SafeArea(
          child: _buildBody(),
        ),
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBody() {
    switch (_tab) {
      case 0:
        return DashboardScreen(bridge: bridge, online: laptopOnline);
      case 1:
        return CommandScreen(bridge: bridge, online: laptopOnline);
      case 2:
        return SettingsScreen(bridge: bridge);
      default:
        return DashboardScreen(bridge: bridge, online: laptopOnline);
    }
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: JTheme.border)),
      ),
      child: BottomNavigationBar(
        currentIndex: _tab,
        onTap: (i) => setState(() => _tab = i),
        backgroundColor: JTheme.bg,
        selectedItemColor: JTheme.cyan,
        unselectedItemColor: JTheme.textMuted,
        type: BottomNavigationBarType.fixed,
        items: [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), activeIcon: Icon(Icons.dashboard), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.terminal_outlined), activeIcon: Icon(Icons.terminal), label: 'Commands'),
          BottomNavigationBarItem(icon: Icon(Icons.settings_outlined), activeIcon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _connSub?.cancel();
    bridge.dispose();
    super.dispose();
  }
}