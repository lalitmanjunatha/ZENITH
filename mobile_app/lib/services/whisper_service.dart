import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

/// Captures raw PCM audio from native Kotlin AudioRecord via EventChannel,
/// converts to WAV, sends to Groq Whisper API for transcription.
/// NO speech_to_text package — NO system chime — NO session timeouts.
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

  void startCapture() {
    if (_recording) return;
    _buffer.clear();
    _pcmSub?.cancel();
    _pcmSub = _channel.receiveBroadcastStream({'sampleRate': _sampleRate}).listen(
      (data) {
        if (data is Uint8List) {
          _buffer.addAll(data);
        }
      },
      onError: (e) {
        lastError = e.toString();
        _recording = false;
      },
    );
    _recording = true;
  }

  void stopCapture() {
    _pcmSub?.cancel();
    _pcmSub = null;
    _recording = false;
    _buffer.clear();
  }

  Future<String> transcribe(String groqApiKey) async {
    if (_buffer.isEmpty) return '';
    if (groqApiKey.isEmpty) {
      lastError = 'GROQ_API_KEY not configured';
      return '';
    }

    final pcmData = Uint8List.fromList(_buffer);
    _buffer.clear();

    if (pcmData.length < 8000) return '';

    try {
      final wavBytes = _pcmToWavBytes(pcmData);

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

      if (response.statusCode == 200) {
        final body = json.decode(response.body) as Map<String, dynamic>;
        return (body['text'] as String?)?.trim() ?? '';
      } else {
        lastError = 'Whisper ${response.statusCode}: ${response.body}';
        return '';
      }
    } catch (e) {
      lastError = e.toString();
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
