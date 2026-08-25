import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Service that talks to the laptop's Zenith bridge server.
/// Handles: status polling, command execution, online/offline detection.
class BridgeService {
  String host;
  int port;

  BridgeService({required this.host, this.port = 8990});

  String get baseUrl => 'http://$host:$port';

  // ── State ──
  bool _isOnline = false;
  DateTime? _lastOnline;
  DateTime? _wentOfflineAt;
  final _statusController = StreamController<Map<String, dynamic>>.broadcast();
  final _connectionController = StreamController<bool>.broadcast();

  bool get isOnline => _isOnline;
  DateTime? get lastOnline => _lastOnline;
  Stream<Map<String, dynamic>> get statusStream => _statusController.stream;
  Stream<bool> get connectionStream => _connectionController.stream;

  Timer? _pollTimer;

  // ── Polling ──
  void startPolling({int intervalSec = 8}) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(Duration(seconds: intervalSec), (_) => _poll());
    _poll(); // immediate first check
  }

  void stopPolling() {
    _pollTimer?.cancel();
  }

  Future<void> _poll() async {
    final online = await ping();
    if (online != _isOnline) {
      // State transition!
      _isOnline = online;
      if (online) {
        _lastOnline = DateTime.now();
        _wentOfflineAt = null;
        _connectionController.add(true); // laptop just came ONLINE
      } else {
        _wentOfflineAt = DateTime.now();
        _connectionController.add(false); // laptop just went OFFLINE
      }
    }
    if (online) {
      try {
        stats = await getStatus();
        _statusController.add(stats ?? {});
      } catch (_) {}
    }
  }

  Map<String, dynamic>? stats;

  // ── API calls ──

  /// Quick heartbeat — returns true if bridge is reachable.
  Future<bool> ping() async {
    try {
      final r = await http
          .get(Uri.parse('$baseUrl/api/ping'))
          .timeout(const Duration(seconds: 4));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Full system dashboard data.
  Future<Map<String, dynamic>?> getStatus() async {
    try {
      final r = await http
          .get(Uri.parse('$baseUrl/api/status'))
          .timeout(const Duration(seconds: 6));
      if (r.statusCode == 200) return json.decode(r.body);
    } catch (_) {}
    return null;
  }

  /// Execute a tool on the laptop remotely.
  Future<String> runCommand(String tool, {Map<String, dynamic>? args}) async {
    try {
      final r = await http
          .post(
            Uri.parse('$baseUrl/api/command'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'tool': tool, 'args': args ?? {}}),
          )
          .timeout(const Duration(seconds: 60));
      final d = json.decode(r.body);
      return d['result'] ?? d['error'] ?? 'No output';
    } catch (e) {
      return '❌ $e';
    }
  }

  /// List available tools on the laptop.
  Future<List<String>> getTools() async {
    try {
      final r = await http
          .get(Uri.parse('$baseUrl/api/tools'))
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = json.decode(r.body);
        return List<String>.from(d['tools'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  void dispose() {
    stopPolling();
    _statusController.close();
    _connectionController.close();
  }
}