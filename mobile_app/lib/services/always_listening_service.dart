import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Unified always-on voice listener — SINGLE SpeechToText instance.
/// Detects "ZENITH" wake word, captures command, auto-restarts.
class AlwaysListeningService {
  static final AlwaysListeningService _i = AlwaysListeningService._();
  factory AlwaysListeningService() => _i;
  AlwaysListeningService._();

  final stt.SpeechToText _stt = stt.SpeechToText();
  bool _initialized = false;
  bool _running = false;
  bool _awaitingCommand = false;
  bool _processingCommand = false;
  int _emptyCount = 0;
  String? lastError;
  Timer? _restartTimer;
  Timer? _awaitTimer;

  Function(String command)? onCommand;
  Function()? onListening;

  bool get isRunning => _running;

  Future<bool> init() async {
    if (_initialized) return true;
    try {
      _initialized = await _stt.initialize(
        onError: (e) {
          lastError = e.errorMsg;
          if (_running && !_processingCommand) _scheduleRestart(3);
        },
        onStatus: (status) {
          if (!_running || _processingCommand) return;
          if (status == 'done' || status == 'notListening') {
            _onSessionEnded();
          }
        },
      );
      if (!_initialized) lastError = 'Speech recognition unavailable on this device';
      return _initialized;
    } catch (e) {
      lastError = e.toString();
      _initialized = false;
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
    _emptyCount = 0;
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
  }

  void _beginListen() {
    if (!_running) return;
    _stt.listen(
      onResult: _onResult,
      listenOptions: stt.SpeechListenOptions(
        partialResults: false,
        cancelOnError: false,
        listenMode: stt.ListenMode.dictation,
        pauseFor: const Duration(seconds: 10),
      ),
    ).catchError((_) {
      if (_running) _scheduleRestart(3);
    });
  }

  void _onSessionEnded() {
    // Speech session ended (silence timeout or user stopped).
    // Empty count tracks consecutive sessions with no speech.
    _emptyCount++;
    if (_awaitingCommand) {
      // User said "zenith" but didn't speak a command — timeout
      _awaitingCommand = false;
      _scheduleRestart(1);
    } else {
      // Backoff: 1s, 2s, 4s, capped at 8s
      final delay = [1, 2, 4, 8][_emptyCount.clamp(0, 3)];
      _scheduleRestart(delay);
    }
  }

  void _scheduleRestart(int seconds) {
    _restartTimer?.cancel();
    _restartTimer = Timer(Duration(seconds: seconds), () {
      if (_running && !_processingCommand) _beginListen();
    });
  }

  void _onResult(dynamic result) {
    if (!_running) return;
    final text = (result.recognizedWords as String).trim();
    if (text.isEmpty) return;
    _emptyCount = 0; // Got speech — reset backoff
    final lower = text.toLowerCase();

    if (_awaitingCommand) {
      _awaitingCommand = false;
      _processingCommand = true;
      onCommand?.call(text);
      return;
    }

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
        _awaitTimer = Timer(const Duration(seconds: 5), () {
          if (_awaitingCommand) {
            _awaitingCommand = false;
            _scheduleRestart(1);
          }
        });
      }
    }
  }

  /// Call this after command has been processed to resume listening.
  void onCommandProcessed() {
    _processingCommand = false;
    if (_running) _scheduleRestart(1);
  }
}
