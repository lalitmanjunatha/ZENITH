import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Voice listener — SINGLE SpeechToText instance.
/// Detects "ZENITH" wake word, captures command.
/// Mic runs one session at a time. Auto-restarts ONLY after command processing.
class AlwaysListeningService {
  static final AlwaysListeningService _i = AlwaysListeningService._();
  factory AlwaysListeningService() => _i;
  AlwaysListeningService._();

  final stt.SpeechToText _stt = stt.SpeechToText();
  bool _running = false;
  bool _awaitingCommand = false;
  bool _processingCommand = false;
  bool _sessionActive = false;
  String? lastError;
  Timer? _restartTimer;
  Timer? _awaitTimer;

  Function(String command)? onCommand;
  Function()? onListening;
  Function(String status)? onStatus;

  bool get isRunning => _running;

  Future<bool> init() async {
    try {
      final ok = await _stt.initialize(
        onError: _onError,
        onStatus: _onStatus,
      );
      if (!ok) {
        lastError = 'Speech unavailable — grant microphone permission in Settings';
        onStatus?.call(lastError!);
      }
      return ok;
    } catch (e) {
      lastError = 'Init failed: $e';
      onStatus?.call(lastError!);
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
    _beginListen();
  }

  void stop() {
    _running = false;
    _awaitingCommand = false;
    _processingCommand = false;
    _sessionActive = false;
    _restartTimer?.cancel();
    _awaitTimer?.cancel();
    try { _stt.stop(); } catch (_) {}
    try { _stt.cancel(); } catch (_) {}
    onStatus?.call('OFF');
  }

  void _beginListen() {
    if (!_running) return;
    _sessionActive = true;
    onStatus?.call('Listening — say "ZENITH"');
    _stt.listen(
      onResult: _onResult,
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
        listenFor: const Duration(minutes: 3),
        pauseFor: const Duration(seconds: 20),
      ),
    ).catchError((e) {
      _sessionActive = false;
      lastError = e.toString();
      if (_running) {
        onStatus?.call('Mic error — retrying...');
        _scheduleRestart(5);
      }
    });
    // DO NOT use .then() to restart — that causes the loop.
    // Session ends naturally and stays dead until we explicitly restart.
  }

  void _onError(dynamic e) {
    if (!_running) return;
    final code = e.errorMsg as String? ?? '';
    _sessionActive = false;

    // noSpeech = user is silent, mic works fine. Just wait — don't restart.
    if (code == 'noSpeech' || code == 'notRecognized') {
      onStatus?.call('Listening — say "ZENITH"');
      return;
    }

    // For actual errors, restart with backoff
    lastError = code;
    onStatus?.call('Error: $code — retrying...');
    _scheduleRestart(5);
  }

  void _onStatus(String status) {
    if (!_running) return;

    // Session ended naturally — DON'T restart, just report.
    // Only restarts happen after command processing or on errors.
    if (status == 'done' || status == 'notListening') {
      _sessionActive = false;
      if (!_processingCommand && !_awaitingCommand) {
        onStatus?.call('Mic paused — tap toggle to restart');
      }
      return;
    }

    onStatus?.call(status);
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
            onStatus?.call('Listening — say "ZENITH"');
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

  /// Called after command is processed — restarts mic for next command.
  void onCommandProcessed() {
    _processingCommand = false;
    if (_running) _scheduleRestart(2);
  }
}
