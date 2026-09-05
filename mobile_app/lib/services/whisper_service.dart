import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

/// Captures raw PCM audio from native Kotlin AudioRecord via EventChannel,
/// converts to WAV, sends to Groq Whisper API for transcription.
class WhisperService {
  static final WhisperService _i = WhisperService._();
  factory WhisperService() => _i;
  WhisperService._();

  static const _channel = EventChannel('zenith_pcm');
  static const _sampleRate = 16000;
  static const _channels = 1;
  static const _bitsPerSample = 16;
  StreamSubscription? _pcmSub;
  final List<int> _buffer = [];
  bool _recording = false;
  String? lastError;

  bool get isRecording => _recording;
  int get bufferMs => (_buffer.length ~/ (_sampleRate * 2)) * 1000;

  Future<bool> startCapture() async {
    if (_recording) return true;
    _buffer.clear();
    lastError = null;
    _pcmSub?.cancel();
    final completer = Completer<bool>();
    _pcmSub = _channel.receiveBroadcastStream({'sampleRate': _sampleRate}).listen(
      (data) {
        if (data is String && data == 'ready') {
          debugPrint('[WHISPER] Kotlin says mic ready');
          _recording = true;
          if (!completer.isCompleted) completer.complete(true);
          return;
        }
        if (data is Uint8List) {
          _buffer.addAll(data);
        }
      },
      onError: (e) {
        debugPrint('[WHISPER] Stream error: $e');
        lastError = e.toString();
        _recording = false;
        if (!completer.isCompleted) completer.complete(false);
      },
      onDone: () {
        debugPrint('[WHISPER] Stream done');
        _recording = false;
      },
    );
    Future.delayed(const Duration(seconds: 3), () {
      if (!completer.isCompleted) {
        lastError = lastError ?? 'Mic init timed out';
        _recording = false;
        completer.complete(false);
      }
    });
    return completer.future;
  }

  void stopCapture() {
    _pcmSub?.cancel();
    _pcmSub = null;
    _recording = false;
    _buffer.clear();
  }

  void flushBuffer() {
    _buffer.clear();
  }

  Future<String> transcribe(String groqApiKey) async {
    if (_buffer.isEmpty) return '';
    if (groqApiKey.isEmpty) {
      lastError = 'GROQ_API_KEY not configured';
      debugPrint('[WHISPER] No API key');
      return '';
    }

    final pcmData = Uint8List.fromList(_buffer);
    _buffer.clear();

    debugPrint('[WHISPER] PCM buffer: ${pcmData.length} bytes (${pcmData.length ~/ 32000}s)');
    if (pcmData.length < 8000) {
      debugPrint('[WHISPER] Too short, skipping');
      return '';
    }

    try {
      final wavBytes = _pcmToWavBytes(pcmData);
      debugPrint('[WHISPER] WAV: ${wavBytes.length} bytes, sending to Groq...');

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('https://api.groq.com/openai/v1/audio/transcriptions'),
      );
      request.headers['Authorization'] = 'Bearer $groqApiKey';
      request.fields['model'] = 'whisper-large-v3-turbo';
      request.fields['response_format'] = 'verbose_json';
      request.files.add(http.MultipartFile.fromBytes(
        'file', wavBytes, filename: 'audio.wav',
      ));

      final streamed = await request.send().timeout(const Duration(seconds: 15));
      final response = await http.Response.fromStream(streamed);

      debugPrint('[WHISPER] Groq response: ${response.statusCode}');
      if (response.statusCode == 200) {
        final body = json.decode(response.body) as Map<String, dynamic>;
        final text = (body['text'] as String?)?.trim() ?? '';
        debugPrint('[WHISPER] Transcribed: "$text"');
        return text;
      } else {
        lastError = 'Whisper ${response.statusCode}: ${response.body}';
        debugPrint('[WHISPER] ERROR: $lastError');
        return '';
      }
    } catch (e) {
      lastError = e.toString();
      debugPrint('[WHISPER] EXCEPTION: $lastError');
      return '';
    }
  }

  Uint8List _pcmToWavBytes(Uint8List pcm) {
    final fileSize = 44 + pcm.length;
    final bw = ByteData(fileSize);

    _writeStr(bw, 0, 'RIFF');
    bw.setUint32(4, fileSize - 8, Endian.little);
    _writeStr(bw, 8, 'WAVE');
    _writeStr(bw, 12, 'fmt ');
    bw.setUint32(16, 16, Endian.little);
    bw.setUint16(20, 1, Endian.little);
    bw.setUint16(22, _channels, Endian.little);
    bw.setUint32(24, _sampleRate, Endian.little);
    bw.setUint32(28, _sampleRate * _channels * _bitsPerSample ~/ 8, Endian.little);
    bw.setUint16(32, _channels * _bitsPerSample ~/ 8, Endian.little);
    bw.setUint16(34, _bitsPerSample, Endian.little);
    _writeStr(bw, 36, 'data');
    bw.setUint32(40, pcm.length, Endian.little);

    final out = Uint8List(fileSize);
    out.setAll(0, bw.buffer.asUint8List());
    out.setAll(44, pcm);
    return out;
  }

  void _writeStr(ByteData bd, int off, String s) {
    for (var i = 0; i < s.length; i++) {
      bd.setUint8(off + i, s.codeUnitAt(i));
    }
  }
}
