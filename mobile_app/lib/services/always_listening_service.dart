import 'dart:async';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Unified always-on voice listener.
/// SINGLE SpeechToText instance — no Android conflicts.
/// Listens continuously, detects "ZENITH" wake word, captures command.
///
/// Supports two patterns:
///   1. Single utterance: "ZENITH what time is it" → command = "what time is it"
///   2. Two utterances:  "ZENITH" → [onListening] fires → "what time is it" → [onCommand] fires
class AlwaysListeningService {
  static final AlwaysListeningService _i = AlwaysListeningService._();
  factory AlwaysListeningService() => _i;
  AlwaysListeningService._();

  final stt.SpeechToText _stt = stt.SpeechToText();
  bool _initialized = false;
  bool _running = false;
  bool _awaitingCommand = false; // true after hearing "zenith" with no command
  String? lastError;

  /// Called when a command is captured after "zenith" wake word.
  Function(String command)? onCommand;

  /// Called when "zenith" is heard without a command (user should speak now).
  Function()? onListening;

  bool get isRunning => _running;
  bool get isAwaitingCommand => _awaitingCommand;

  Future<bool> init() async {
    if (_initialized) return true;
    try {
      _initialized = await _stt.initialize(
        onError: (e) {
          lastError = e.errorMsg;
          if (_running) {
            Future.delayed(const Duration(seconds: 1), () => _startListening());
          }
        },
        onStatus: (status) {
          if (!_running) return;
          if (status == 'done' || status == 'notListening') {
            Future.delayed(const Duration(milliseconds: 300), () => _startListening());
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

  /// Start always-on listening.
  Future<void> start() async {
    if (_running) return;
    final ok = await init();
    if (!ok) return;
    _running = true;
    _awaitingCommand = false;
    _startListening();
  }

  /// Stop listening.
  void stop() {
    _running = false;
    _awaitingCommand = false;
    _stt.stop().catchError((_) {});
    _stt.cancel().catchError((_) {});
  }

  void _startListening() {
    if (!_running) return;
    _stt.listen(
      onResult: (result) {
        if (!_running) return;
        if (!result.finalResult) return;
        final text = result.recognizedWords.trim();
        if (text.isEmpty) return;
        final lower = text.toLowerCase();

        if (_awaitingCommand) {
          // We already heard "zenith" — this utterance IS the command
          _awaitingCommand = false;
          onCommand?.call(text);
          return;
        }

        // Check for wake word in speech
        if (lower.contains('zenith') || lower.contains('hey zenith')) {
          // Extract command after wake word
          String command = text;
          final heyIdx = lower.indexOf('hey zenith');
          if (heyIdx >= 0) {
            command = text.substring(heyIdx + 'hey zenith'.length).trim();
          } else {
            final zIdx = lower.indexOf('zenith');
            command = text.substring(zIdx + 'zenith'.length).trim();
          }

          if (command.isNotEmpty) {
            // Single-utterance command: "ZENITH what time is it"
            onCommand?.call(command);
          } else {
            // Wake word only — wait for next utterance as command
            _awaitingCommand = true;
            onListening?.call();
          }
        }
        // Non-wake-word speech → ignored, keep listening
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: false,
        cancelOnError: false,
        listenMode: stt.ListenMode.dictation,
      ),
    ).catchError((_) {});
  }
}
