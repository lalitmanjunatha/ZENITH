import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Always-on voice listener — SINGLE SpeechToText instance.
/// Detects "ZENITH" wake word, captures command, keeps mic alive as long as possible.
class AlwaysListeningService {
  static final AlwaysListeningService _i = AlwaysListeningService._();
  factory AlwaysListeningService() => _i;
  AlwaysListeningService._();

  final stt.SpeechToText _stt = stt.SpeechToText();
  bool _running = false;
  bool _awaitingCommand = false;
  bool _processingCommand = false;
  String? lastError;
  Timer? _restartTimer;
  Timer? _awaitTimer;
  int _sessionCount = 0;

  Function(String command)? onCommand;
  Function()? onListening;
  Function(String status)? onStatus;

  bool get isRunning => _running;

  Future<bool> init() async {
    if (_stt.isAvailable) return true;
    try {
      final ok = await _stt.initialize(
        onError: (e) {
          lastError = e.errorMsg;
          onStatus?.call('Error: ${e.errorMsg}');
          if (_running && !_processingCommand) _scheduleRestart(5);
        },
        onStatus: (status) {
          if (!_running) return;
          onStatus?.call(status);
        },
      );
      if (!ok) {
        lastError = 'Speech recognition unavailable on this device';
        onStatus?.call('Unavailable');
      }
      return ok;
    } catch (e) {
      lastError = e.toString();
      onStatus?.call('Init failed: $e');
      return false;
    }
  }

  Future<void> start() async {
    if (_running) return;
    final ok = await init();
    if (!ok) return;
    _running = true;
    _awaitingCommand = false;
    _processingCommand = false;
    _sessionCount = 0;
    _beginListen();
  }

  void stop() {
    _running = false;
    _awaitingCommand = false;
    _processingCommand = false;
    _restartTimer?.cancel();
    _awaitTimer?.cancel();
    try { _stt.stop(); } catch (_) {}
    try { _stt.cancel(); } catch (_) {}
    onStatus?.call('Stopped');
  }

  void _beginListen() {
    if (!_running) return;
    _sessionCount++;
    onStatus?.call('Listening (#$_sessionCount)...');
    _stt.listen(
      onResult: _onResult,
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: false,
        listenMode: stt.ListenMode.dictation,
        listenFor: const Duration(minutes: 5),
        pauseFor: const Duration(seconds: 30),
      ),
    ).catchError((e) {
      lastError = e.toString();
      onStatus?.call('Listen error: $e');
      if (_running) _scheduleRestart(5);
    });
  }

  void _onResult(dynamic result) {
    if (!_running) return;
    final text = (result.recognizedWords as String).trim();
    if (text.isEmpty) return;
    final lower = text.toLowerCase();
    onStatus?.call('Heard: "$text"');

    // If awaiting command after "zenith" alone
    if (_awaitingCommand) {
      _awaitingCommand = false;
      _awaitTimer?.cancel();
      _processingCommand = true;
      onCommand?.call(text);
      return;
    }

    // Check for wake word
    if (lower.contains('zenith') || lower.contains('hey zenith')) {
      String command = text;
      final heyIdx = lower.indexOf('hey zenith');
      if (heyIdx >= 0) {
        command = text.substring(heyIdx + 'hey zenith'.length).trim();
      } else {
        final zIdx = lower.indexOf('zenith');
        command = text.substring(zIdx + 'zenith'.length).trim();
      }

      if (command.isNotEmpty) {
        _processingCommand = true;
        onCommand?.call(command);
      } else {
        _awaitingCommand = true;
        onListening?.call();
        _awaitTimer?.cancel();
        _awaitTimer = Timer(const Duration(seconds: 8), () {
          if (_awaitingCommand) {
            _awaitingCommand = false;
            onStatus?.call('Command timeout — listening again...');
            _scheduleRestart(2);
          }
        });
      }
    }
  }

  void _scheduleRestart(int seconds) {
    _restartTimer?.cancel();
    _restartTimer = Timer(Duration(seconds: seconds), () {
      if (_running && !_processingCommand) _beginListen();
    });
  }

  void onCommandProcessed() {
    _processingCommand = false;
    if (_running) _scheduleRestart(2);
  }
}
