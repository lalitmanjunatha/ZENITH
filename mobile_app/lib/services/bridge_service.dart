import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

class BrainReply {
  final String type;
  final String reply;
  final String? session;
  BrainReply({required this.type, required this.reply, this.session});
}

/// Dual-mode service: CLOUD (render.com brain) or LAN (laptop bridge direct).
class BridgeService {
  String host;
  int port;
  String? cloudUrl;
  String? pin;

  BridgeService({required this.host, this.port = 8990});

  bool get useCloud => cloudUrl != null && (cloudUrl?.isNotEmpty ?? false);
  bool get pinConfigured => (pin ?? '').isNotEmpty;

  String get baseUrl => 'http://$host:$port';

  void configureCloud({required String url, required String pinValue}) {
    var u = url.trim();
    if (u.isEmpty) {
      cloudUrl = null;
      pin = null;
      return;
    }
    if (!u.startsWith('http')) u = 'https://$u';
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    cloudUrl = u;
    pin = pinValue.trim();
  }

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

  Map<String, dynamic>? stats;

  Timer? _pollTimer;

  void startPolling({int intervalSec = 8}) {
    _pollTimer?.cancel();
    _pollTimer =
        Timer.periodic(Duration(seconds: intervalSec), (_) => _poll());
    _poll();
  }

  void stopPolling() {
    _pollTimer?.cancel();
  }

  Future<void> _poll() async {
    final online = await ping();
    if (online != _isOnline) {
      _isOnline = online;
      if (online) {
        _lastOnline = DateTime.now();
        _wentOfflineAt = null;
        _connectionController.add(true);
      } else {
        _wentOfflineAt = DateTime.now();
        _connectionController.add(false);
      }
    }
    if (online) {
      try {
        stats = useCloud ? await cloudStatus() : await getStatus();
        _statusController.add(stats ?? {});
      } catch (_) {}
    }
  }

  // ── API calls ──

  Future<bool> ping() async {
    try {
      if (useCloud) {
        final r = await http
            .get(Uri.parse('$cloudUrl/api/ping'))
            .timeout(const Duration(seconds: 60));
        return r.statusCode == 200;
      }
      final r = await http
          .get(Uri.parse('$baseUrl/api/ping'))
          .timeout(const Duration(seconds: 4));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> cloudStatus() async {
    try {
      final r = await http
          .get(Uri.parse('$cloudUrl/api/status?pin=${Uri.encodeComponent(pin ?? '')}'))
          .timeout(const Duration(seconds: 60));
      if (r.statusCode == 200) {
        final d = json.decode(r.body) as Map<String, dynamic>;
        final flat = <String, dynamic>{};
        if (d['stats'] is Map) {
          (d['stats'] as Map).forEach((k, v) => flat[k.toString()] = v);
        }
        flat['_cloud'] = d;
        return flat;
      }
    } catch (_) {}
    return null;
  }

  Future<BrainReply> askBrain(String text) async {
    if (!useCloud) {
      return BrainReply(
          type: 'text', reply: '☁️ Cloud not configured — add URL & PIN in Settings.');
    }
    if (!pinConfigured) {
      return BrainReply(type: 'text', reply: '🔑 Set your pairing PIN in Settings.');
    }
    try {
      final r = await http
          .post(
            Uri.parse('$cloudUrl/api/command'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'command': text, 'pin': pin}),
          )
          .timeout(const Duration(seconds: 90));
      if (r.statusCode == 401) {
        return BrainReply(type: 'text', reply: '🔑 Wrong PIN — fix it in Settings.');
      }
      final d = json.decode(r.body);
      return BrainReply(
        type: d['type'] ?? 'text',
        reply: d['reply'] ?? '…',
        session: d['session'],
      );
    } catch (e) {
      return BrainReply(type: 'text', reply: '⚠️ $e');
    }
  }

  Future<BrainReply> respondConfirm(String session, String answer) async {
    try {
      final r = await http
          .post(
            Uri.parse('$cloudUrl/api/respond'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'session': session, 'text': answer, 'pin': pin}),
          )
          .timeout(const Duration(seconds: 90));
      final d = json.decode(r.body);
      return BrainReply(type: 'text', reply: d['reply'] ?? '…');
    } catch (e) {
      return BrainReply(type: 'text', reply: '⚠️ $e');
    }
  }

  Future<Map<String, dynamic>?> getStatus() async {
    try {
      final r = await http
          .get(Uri.parse('$baseUrl/api/status'))
          .timeout(const Duration(seconds: 6));
      if (r.statusCode == 200) return json.decode(r.body);
    } catch (_) {}
    return null;
  }

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
