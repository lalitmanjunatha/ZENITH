import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/services.dart' show rootBundle, EventChannel;
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;

/// Always-on "ZENITH" wake word using sherpa-onnx open-vocabulary KWS.
/// Fully offline, phoneme-based keyword spotting on a 16 kHz mic stream.
class WakeWordService {
  static final WakeWordService _i = WakeWordService._();
  factory WakeWordService() => _i;
  WakeWordService._();

  sherpa.KeywordSpotter? _kws;
  StreamSubscription<dynamic>? _micSub;
  bool _running = false;
  bool get isRunning => _running;
  String? lastError;

  Function(String keyword)? onWake;

  static const _dir = 'kws';
  static const _files = [
    'encoder-epoch-13-avg-2-chunk-16-left-64.int8.onnx',
    'decoder-epoch-13-avg-2-chunk-16-left-64.onnx',
    'joiner-epoch-13-avg-2-chunk-16-left-64.int8.onnx',
    'tokens.txt',
    'keywords_zenith.txt',
  ];

  Future<String> _materialize(String name) async {
    final data = await rootBundle.load('assets/$_dir/$name');
    final path = '${Directory.systemTemp.path}/zenith_kws_$name';
    await File(path).writeAsBytes(data.buffer.asUint8List(), flush: true);
    return path;
  }

  Future<bool> init() async {
    if (_kws != null) return true;
    try {
      final paths = <String, String>{};
      for (final f in _files) {
        paths[f] = await _materialize(f);
        print('[WakeWord] Materialized: $f -> ${paths[f]}');
      }
      print('[WakeWord] Configuring KWS with encoder: ${paths[_files[0]]}');
      print('[WakeWord] Keywords file: ${paths['keywords_zenith.txt']}');
      final config = sherpa.KeywordSpotterConfig(
        model: sherpa.OnlineModelConfig(
          transducer: sherpa.OnlineTransducerModelConfig(
            encoder: paths[_files[0]]!,
            decoder: paths[_files[1]]!,
            joiner: paths[_files[2]]!,
          ),
          tokens: paths['tokens.txt']!,
          numThreads: 1,
        ),
        keywordsFile: paths['keywords_zenith.txt']!,
        keywordsScore: 2.0,
        keywordsThreshold: 0.25,
      );
      _kws = sherpa.KeywordSpotter(config);
      print('[WakeWord] KeywordSpotter created successfully');
      return true;
    } catch (e, st) {
      lastError = e.toString();
      print('[WakeWord] ERROR: $e');
      print('[WakeWord] STACK: $st');
      return false;
    }
  }

  void start() {
    if (_running || _kws == null) return;
    final stream = _kws!.createStream();
    _running = true;

    _micSub = EventChannel('zenith_pcm')
        .receiveBroadcastStream({'sampleRate': 16000})
        .listen((chunk) {
      if (!_running || chunk == null || (chunk as Uint8List).isEmpty) return;
      try {
        stream.acceptWaveform(samples: _toFloat(chunk), sampleRate: 16000);
        while (_kws!.isReady(stream)) {
          _kws!.decode(stream);
        }
        final kw = _kws!.getResult(stream).keyword.trim();
        if (kw.isNotEmpty) {
          _kws!.reset(stream);
          onWake?.call(kw);
        }
      } catch (_) {}
    }, onError: (_) {});
  }

  Float32List _toFloat(Uint8List pcm16) {
    final len = pcm16.length ~/ 2;
    final out = Float32List(len);
    final bd = ByteData.sublistView(pcm16);
    for (var i = 0; i < len; i++) {
      out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
    }
    return out;
  }

  void stop() {
    _running = false;
    _micSub?.cancel();
    _micSub = null;
  }

  void dispose() {
    stop();
    _kws?.free();
    _kws = null;
  }
}
