import 'dart:async';
import 'package:flutter/foundation.dart';
import '../secrets.dart';
import 'whisper_service.dart';

/// Always-on voice listener using raw PCM audio + Groq Whisper.
class WhisperListeningService {
  static final WhisperListeningService _i = WhisperListeningService._();
  factory WhisperListeningService() => _i;
  WhisperListeningService._();

  final WhisperService _whisper = WhisperService();
  bool _running = false;
  bool _processingCommand = false;
  bool _awaitingCommand = false;
  bool _inCooldown = false;
  Timer? _pollTimer;
  Timer? _awaitTimer;
  Timer? _cooldownTimer;
  String? lastError;

  Function(String command)? onCommand;
  Function()? onListening;
  Function(String status)? onStatus;

  bool get isRunning => _running;

  Future<bool> start() async {
    if (_running) return true;
    _processingCommand = false;
    _awaitingCommand = false;
    _inCooldown = false;

    final apiKey = Secrets.groqApiKey;
    if (apiKey.isEmpty) {
      lastError = 'Groq API key not configured';
      onStatus?.call(lastError!);
      return false;
    }

    final started = await _whisper.startCapture();
    if (!started) {
      lastError = _whisper.lastError ?? 'Mic access denied';
      onStatus?.call(lastError!);
      return false;
    }

    _running = true;
    onStatus?.call('Listening...');
    _pollTimer = Timer.periodic(const Duration(seconds: 4), (_) => _poll(apiKey));
    return true;
  }

  void stop() {
    _running = false;
    _processingCommand = false;
    _awaitingCommand = false;
    _inCooldown = false;
    _pollTimer?.cancel();
    _awaitTimer?.cancel();
    _cooldownTimer?.cancel();
    _whisper.stopCapture();
    onStatus?.call('OFF');
  }

  Future<void> _poll(String apiKey) async {
    if (!_running || _processingCommand || _inCooldown) return;
    final bufMs = _whisper.bufferMs;
    debugPrint('[LISTENER] Poll: bufferMs=$bufMs');
    if (bufMs < 2000) return;

    onStatus?.call('Transcribing...');
    final text = await _whisper.transcribe(apiKey);
    debugPrint('[LISTENER] Transcribe result: "$text"');
    if (text.isEmpty || !_running) return;

    final lower = text.toLowerCase();
    onStatus?.call('Heard: "$text"');

    if (_awaitingCommand) {
      _awaitingCommand = false;
      _awaitTimer?.cancel();
      _processingCommand = true;
      _whisper.flushBuffer();
      debugPrint('[LISTENER] Sending awaited command: "$text"');
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

      debugPrint('[LISTENER] Wake word found, command: "$command"');
      if (command.isNotEmpty) {
        _processingCommand = true;
        _whisper.flushBuffer();
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
    _whisper.flushBuffer();
    _inCooldown = true;
    _cooldownTimer?.cancel();
    onStatus?.call('Processing reply...');
    // 7s cooldown: blocks polling while TTS speaks the brain reply
    _cooldownTimer = Timer(const Duration(seconds: 7), () {
      _inCooldown = false;
      _whisper.flushBuffer();
      if (_running) onStatus?.call('Listening...');
    });
  }
}
