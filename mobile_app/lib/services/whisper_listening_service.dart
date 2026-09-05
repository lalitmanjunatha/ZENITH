import 'dart:async';
import '../secrets.dart';
import 'whisper_service.dart';

/// Always-on voice listener using raw PCM audio + Groq Whisper.
/// NO speech_to_text — NO system chime — NO session restarts — NO loops.
///
/// Architecture:
///   Kotlin AudioRecord → PCM stream (EventChannel) → buffer 4s of audio
///   → send to Groq Whisper API → get text → check for "ZENITH" wake word.
class WhisperListeningService {
  static final WhisperListeningService _i = WhisperListeningService._();
  factory WhisperListeningService() => _i;
  WhisperListeningService._();

  final WhisperService _whisper = WhisperService();
  bool _running = false;
  bool _processingCommand = false;
  bool _awaitingCommand = false;
  Timer? _pollTimer;
  Timer? _awaitTimer;
  String? lastError;

  Function(String command)? onCommand;
  Function()? onListening;
  Function(String status)? onStatus;

  bool get isRunning => _running;

  Future<void> start() async {
    if (_running) return;
    _running = true;
    _processingCommand = false;
    _awaitingCommand = false;

    final apiKey = Secrets.groqApiKey;
    if (apiKey.isEmpty) {
      lastError = 'Groq API key not configured';
      onStatus?.call(lastError!);
      _running = false;
      return;
    }

    _whisper.startCapture();
    onStatus?.call('Listening...');

    _pollTimer = Timer.periodic(const Duration(seconds: 4), (_) => _poll(apiKey));
  }

  void stop() {
    _running = false;
    _processingCommand = false;
    _awaitingCommand = false;
    _pollTimer?.cancel();
    _awaitTimer?.cancel();
    _whisper.stopCapture();
    onStatus?.call('OFF');
  }

  Future<void> _poll(String apiKey) async {
    if (!_running || _processingCommand) return;
    if (_whisper.bufferMs < 2000) return;

    onStatus?.call('Transcribing...');
    final text = await _whisper.transcribe(apiKey);
    if (text.isEmpty || !_running) return;

    final lower = text.toLowerCase();
    onStatus?.call('Heard: "$text"');

    if (_awaitingCommand) {
      _awaitingCommand = false;
      _awaitTimer?.cancel();
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
        _awaitTimer = Timer(const Duration(seconds: 8), () {
          if (_awaitingCommand) {
            _awaitingCommand = false;
            onStatus?.call('Listening...');
          }
        });
      }
    }
  }

  void onCommandProcessed() {
    _processingCommand = false;
    onStatus?.call('Listening...');
  }
}
