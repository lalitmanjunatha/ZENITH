import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Speech-to-text service — uses Android/iOS built-in recognition.
/// Press mic → speak → get text → send to laptop as command.
class SpeechService {
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _available = false;
  bool _listening = false;
  String _lastWords = '';

  bool get isListening => _listening;
  bool get isAvailable => _available;
  String get lastWords => _lastWords;
  String lastError = '';

  /// Initialize. Call once at app startup. Returns true if mic available.
  Future<bool> init() async {
    try {
      _available = await _speech.initialize(
        onError: (e) {
          _listening = false;
          lastError = e.errorMsg ?? 'speech error';
        },
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') {
            _listening = false;
          }
        },
      );
      if (!_available) lastError = 'Speech service unavailable on this device';
      return _available;
    } catch (e) {
      _available = false;
      lastError = e.toString();
      return false;
    }
  }

  /// Start listening. Returns recognized text via [onResult] callback
  /// after user stops speaking (auto-detects silence).
  Future<void> listen({
    required Function(String) onResult,
    Function(String)? onPartialResult,
  }) async {
    if (!_available) {
      final ok = await init();
      if (!ok) return;
    }
    if (_listening) return;
    _lastWords = '';
    _listening = true;

    await _speech.listen(
      onResult: (result) {
        _lastWords = result.recognizedWords;
        // Send partial results for live display while speaking
        if (onPartialResult != null && result.recognizedWords.isNotEmpty) {
          onPartialResult(result.recognizedWords);
        }
        // Final result when user stops talking
        if (result.finalResult && _lastWords.isNotEmpty) {
          _listening = false;
          onResult(_lastWords);
        }
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
      ),
      localeId: 'en_US', // can be changed to hi_IN for Hindi
    );

    // Auto-stop after 8 seconds of no speech
    Future.delayed(Duration(seconds: 8), () {
      if (_listening) {
        stop();
        if (_lastWords.isNotEmpty) onResult(_lastWords);
        _listening = false;
      }
    });
  }

  /// Force stop listening.
  Future<void> stop() async {
    await _speech.stop();
    _listening = false;
  }

  /// Cancel without returning result.
  Future<void> cancel() async {
    await _speech.cancel();
    _listening = false;
    _lastWords = '';
  }
}