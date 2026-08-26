import 'package:flutter/material.dart';
import 'dart:async';
import 'package:shared_preferences/shared_preferences.dart';
import 'theme/jarvis_theme.dart';
import 'services/bridge_service.dart';
import 'services/phone_link.dart';
import 'screens/dashboard_screen.dart';
import 'screens/command_screen.dart';
import 'screens/settings_screen.dart';
import 'widgets/toast_host.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
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
  PhoneLink? phoneLink;
  bool laptopOnline = false;
  StreamSubscription? _connSub;

  @override
  void initState() {
    super.initState();
    _initBridge();
  }

  Future<void> _initBridge() async {
    final prefs = await SharedPreferences.getInstance();
    bridge = BridgeService(
      host: prefs.getString('laptop_host') ?? '192.168.1.100',
    );
    final useCloudPref = prefs.getBool('zenith_use_cloud') ?? true;
    final cloudUrl =
        prefs.getString('zenith_cloud_url') ?? 'https://zenith-cloud-brain.onrender.com';
    final savedPin = prefs.getString('zenith_pin') ?? '';
    if (useCloudPref && cloudUrl.isNotEmpty) {
      bridge.configureCloud(url: cloudUrl, pinValue: savedPin);
    }
    phoneLink?.dispose();
    if (useCloudPref && cloudUrl.isNotEmpty && savedPin.isNotEmpty) {
      phoneLink = PhoneLink(cloudUrl: cloudUrl, pin: savedPin)..connect();
    }
    bridge.startPolling(intervalSec: bridge.useCloud ? 15 : 8);
    _connSub = bridge.connectionStream.listen((online) {
      setState(() => laptopOnline = online);
      if (online) {
        ZenithToasts.success('Your laptop just came ONLINE!',
            duration: const Duration(seconds: 4));
      }
    });
    bridge.ping().then((v) {
      if (mounted) setState(() => laptopOnline = v);
    });
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
          child: Stack(
            children: [
              _buildBody(),
              const ZenithToastHost(),
            ],
          ),
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
    phoneLink?.dispose();
    bridge.dispose();
    super.dispose();
  }
}