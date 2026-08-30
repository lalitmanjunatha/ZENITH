import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Always-on "ZENITH" wake word using speech_to_text.
/// Continuously listens for the keyword in any language, then fires [onWake].
class WakeWordService {
  static final WakeWordService _i = WakeWordService._();
  factory WakeWordService() => _i;
  WakeWordService._();

  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _running = false;
  bool _initialized = false;
  bool _paused = false;
  bool get isRunning => _running;
  String? lastError;

  Function(String keyword)? onWake;

  Future<bool> init() async {
    if (_initialized) return true;
    try {
      _initialized = await _speech.initialize(
        onError: (e) {
          if (_running && !_paused &&
              e.errorMsg != 'noSpeech' && e.errorMsg != 'retry') {
            lastError = e.errorMsg;
          }
        },
        onStatus: (status) {
          if (_running && !_paused &&
              (status == 'done' || status == 'notListening')) {
            _restartListening();
          }
        },
      );
      if (!_initialized) {
        lastError = 'Speech recognition unavailable on this device';
      }
      return _initialized;
    } catch (e) {
      lastError = e.toString();
      _initialized = false;
      return false;
    }
  }

  void start() {
    if (_running) return;
    _running = true;
    _paused = false;
    _restartListening();
  }

  /// Temporarily stop listening so another SpeechToText can take over
  /// (e.g. command capture after wake word detected).
  Future<void> pause() async {
    _paused = true;
    await _speech.stop().catchError((_) {});
  }

  /// Resume wake word listening after command capture is done.
  void resume() {
    if (!_running) return;
    _paused = false;
    _restartListening();
  }

  void _restartListening() {
    if (!_running || _paused) return;
    _speech.listen(
      onResult: (result) {
        if (!_running || _paused) return;
        final text = result.recognizedWords.toLowerCase();
        if (text.contains('zenith') || text.contains('hey zenith')) {
          final kw = text.contains('hey') ? 'HEY_ZENITH' : 'ZENITH';
          onWake?.call(kw);
        }
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: false,
        listenMode: stt.ListenMode.dictation,
      ),
    ).catchError((_) {});
    Timer(const Duration(seconds: 10), () {
      if (_running && !_paused) _restartListening();
    });
  }

  void stop() {
    _running = false;
    _paused = false;
    _speech.stop().catchError((_) {});
  }

  void dispose() {
    stop();
    _initialized = false;
  }
}
