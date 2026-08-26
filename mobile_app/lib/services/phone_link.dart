import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'phone_tools.dart';

/// Persistent WebSocket link from this phone TO the Zenith Cloud Brain.
/// The brain routes phone-class tool calls down this pipe; we execute them
/// natively via PhoneTools and return results.
class PhoneLink {
  final String cloudUrl;
  final String pin;
  WebSocketChannel? _ws;
  Timer? _hb;
  Timer? _retry;
  bool _disposed = false;
  double _backoff = 2;

  PhoneLink({required this.cloudUrl, required this.pin});

  String get _wsUrl {
    var u = cloudUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    return '$u/ws?role=phone&pin=${Uri.encodeComponent(pin)}';
  }

  void connect() {
    if (_disposed) return;
    try {
      _ws?.sink.close();
    } catch (_) {}
    try {
      _ws = WebSocketChannel.connect(Uri.parse(_wsUrl));
      _backoff = 2;      _ws!.stream.listen(_onMessage, onDone: _scheduleReconnect,
          onError: (_) => _scheduleReconnect());
      _hb?.cancel();
      _hb = Timer.periodic(const Duration(seconds: 20), (_) {
        _send({'type': 'heartbeat'});
      });
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic data) {
    try {
      final msg = json.decode(data as String);
      if (msg['type'] == 'tool_exec') {
        _runTool(msg);
      }
    } catch (_) {}
  }

  Future<void> _runTool(Map<String, dynamic> msg) async {
    final reqId = msg['req_id'] ?? '';
    final tool = msg['tool'] ?? '';
    final args = (msg['args'] as Map?)?.cast<String, dynamic>() ?? {};
    String output;
    bool ok = true;
    try {
      output = await PhoneTools().execute(tool, args);
    } catch (e) {
      ok = false;
      output = e.toString();
    }
    _send({'type': 'result', 'req_id': reqId, 'ok': ok, 'output': output});
  }

  void _send(Map<String, dynamic> m) {
    try {
      _ws?.sink.add(json.encode(m));
    } catch (_) {}
  }

  void _scheduleReconnect() {
    if (_disposed || _retry != null) return;
    _hb?.cancel();
    _retry = Timer(Duration(seconds: _backoff.round()), () {
      _retry = null;
      _backoff = (_backoff * 1.6).clamp(2.0, 30.0);
      connect();
    });
  }

  void restart() {
    _backoff = 1;
    connect();
  }

  void dispose() {
    _disposed = true;
    _hb?.cancel();
    _retry?.cancel();
    try {
      _ws?.sink.close();
    } catch (_) {}
  }
}
