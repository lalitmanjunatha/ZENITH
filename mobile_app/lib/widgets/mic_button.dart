import 'package:flutter/material.dart';
import '../theme/jarvis_theme.dart';
import '../services/speech_service.dart';

/// Big glowing mic button — press to speak, release to send command.
/// Shows pulsing rings while listening, recognized text below.
class MicButton extends StatefulWidget {
  final SpeechService speech;
  final Function(String) onCommand;
  final bool laptopOnline;

  const MicButton({
    required this.speech,
    required this.onCommand,
    required this.laptopOnline,
  });

  @override
  State<MicButton> createState() => _MicButtonState();
}

class _MicButtonState extends State<MicButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _anim;
  bool _listening = false;
  String _recognizedText = '';

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: 1200),
    )..repeat();
    widget.speech.init();
    widget.speech.onStopped = _finalize;
  }

  void _finalize() {
    if (!mounted) return;
    if (!_listening) return;
    setState(() { _listening = false; });
    if (_recognizedText.trim().isNotEmpty) {
      final cmd = _recognizedText.trim();
      _recognizedText = '';
      widget.onCommand(cmd);
    } else {
      _snack("Didn't catch that — try again, a bit louder");
    }
  }

  Future<void> _toggleMic() async {
    if (_listening) {
      await widget.speech.stop();
      _finalize();
      return;
    }

    if (!widget.speech.isAvailable) {
      final ok = await widget.speech.init();
      if (!ok) {
        _snack('Speech recognition unavailable: ${widget.speech.lastError}');
        return;
      }
    }

    // Start listening
    setState(() { _listening = true; _recognizedText = ''; });
    await widget.speech.listen(
      onResult: (text) {
        if (mounted) setState(() => _recognizedText = text);
      },
      onPartialResult: (partial) {
        if (mounted) setState(() => _recognizedText = partial);
      },
    );
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: JTheme.surface,
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 3),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final color = _listening ? JTheme.red : JTheme.cyan;
    final pulseValue = _anim.value;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Recognized text display while listening
        if (_listening && _recognizedText.isNotEmpty)
          Container(
            margin: EdgeInsets.only(bottom: 12),
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: JTheme.surface.withOpacity(0.9),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: JTheme.cyan.withOpacity(0.3)),
            ),
            child: Text(
              '"$_recognizedText"',
              style: TextStyle(color: JTheme.textPrimary, fontSize: 14),
            ),
          ),

        // The big mic button with expanding rings
        GestureDetector(
          onTap: _toggleMic,
          child: SizedBox(
            width: 100, height: 100,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Expanding ring 1
                if (_listening)
                  Transform.scale(
                    scale: 1.0 + pulseValue * 0.5,
                    child: Container(
                      width: 80, height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: color.withOpacity(0.4), width: 2),
                      ),
                    ),
                  ),
                // Expanding ring 2 (delayed)
                if (_listening)
                  Transform.scale(
                    scale: 1.0 + ((pulseValue + 0.5) % 1.0) * 0.7,
                    child: Container(
                      width: 70, height: 70,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: color.withOpacity(0.2), width: 1.5),
                      ),
                    ),
                  ),
                // Main circle
                Container(
                  width: 64, height: 64,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      begin: Alignment.topLeft, end: Alignment.bottomRight,
                      colors: [color, color.withOpacity(0.7)],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: color.withOpacity(_listening ? 0.6 : 0.3 + pulseValue * 0.2),
                        blurRadius: _listening ? 25 : 15,
                        spreadRadius: _listening ? 5 : 2,
                      ),
                    ],
                  ),
                  child: Icon(
                    _listening ? Icons.mic : Icons.mic_none,
                    color: JTheme.bg, size: 30,
                  ),
                ),
              ],
            ),
          ),
        ),

        SizedBox(height: 6),
        Text(
          _listening ? 'Listening…' : 'Tap to Speak',
          style: TextStyle(
            color: _listening ? color : JTheme.textMuted,
            fontSize: 11,
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }
}