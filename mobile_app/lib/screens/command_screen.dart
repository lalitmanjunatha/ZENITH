import 'package:flutter/material.dart';
import '../theme/jarvis_theme.dart';
import '../services/bridge_service.dart';

class CommandScreen extends StatefulWidget {
  final BridgeService bridge;
  final bool online;
  CommandScreen({required this.bridge, required this.online});

  @override
  State<CommandScreen> createState() => _CommandScreenState();
}

class _CommandScreenState extends State<CommandScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<Map<String, dynamic>> _messages = [];

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();

    setState(() {
      _messages.add(<String, dynamic>{'role': 'user', 'text': text});
    });

    if (!widget.online) {
      setState(() {
        _messages.add(<String, dynamic>{
          'role': 'system',
          'text': '🔴 Laptop is offline — command cannot execute now.'
        });
      });
      return;
    }

    final mapped = _mapToTool(text);
    setState(() {
      _messages.add(<String, dynamic>{
        'role': 'zenith',
        'text': '⚡ Executing: ${mapped['tool']}…'
      });
    });

    final result = await widget.bridge.runCommand(
      mapped['tool'] as String,
      args: mapped['args'] as Map<String, dynamic>?,
    );
    setState(() {
      _messages.add(<String, dynamic>{'role': 'result', 'text': result});
    });

    await Future.delayed(Duration(milliseconds: 100));
    _scrollController.animateTo(
      _scrollController.position.maxScrollExtent,
      duration: Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  }

  Map<String, dynamic> _mapToTool(String input) {
    final l = input.toLowerCase().trim();
    if (l.contains('health') || l.contains('how is my laptop'))
      return {'tool': 'get_laptop_health', 'args': <String, dynamic>{}};
    if (l.contains('threat') || l.contains('risk'))
      return {'tool': 'daily_threat_board', 'args': <String, dynamic>{}};
    if (l.contains('damage') || l.contains('what broke'))
      return {'tool': 'damage_report', 'args': <String, dynamic>{}};
    if (l.contains('battery'))
      return {'tool': 'battery_coach', 'args': <String, dynamic>{}};
    if (l.contains('clean slate'))
      return {'tool': 'run_protocol', 'args': <String, dynamic>{'name': 'clean slate'}};
    if (l.contains('study mode'))
      return {'tool': 'run_protocol', 'args': <String, dynamic>{'name': 'study mode'}};
    if (l.contains('catch me up'))
      return {'tool': 'catch_me_up', 'args': <String, dynamic>{}};
    if (l.contains('power check') || l.contains('capabilities'))
      return {'tool': 'power_check', 'args': <String, dynamic>{}};
    return {'tool': 'decide_and_act', 'args': <String, dynamic>{'goal': input}};
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: _messages.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  controller: _scrollController,
                  padding: EdgeInsets.all(16),
                  itemCount: _messages.length,
                  itemBuilder: (_, i) => _buildBubble(_messages[i]),
                ),
        ),
        _buildInputBar(),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.terminal, size: 48, color: JTheme.textMuted.withOpacity(0.3)),
          SizedBox(height: 12),
          Text('Send a command to your laptop',
              style: TextStyle(color: JTheme.textMuted)),
          SizedBox(height: 6),
          Text('Try: "health check" · "threat board" · "clean slate"',
              style: TextStyle(color: JTheme.textMuted.withOpacity(0.5), fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildBubble(Map<String, dynamic> msg) {
    final role = msg['role'] as String;
    final text = msg['text'] as String;

    Color bgColor;
    Alignment align;
    IconData? icon;
    Color textColor;

    switch (role) {
      case 'user':
        bgColor = JTheme.cyan.withOpacity(0.15);
        align = Alignment.centerRight;
        textColor = JTheme.textPrimary;
        break;
      case 'zenith':
        bgColor = JTheme.card;
        align = Alignment.centerLeft;
        icon = Icons.smart_toy_outlined;
        textColor = JTheme.cyanDim;
        break;
      case 'result':
        bgColor = JTheme.surface;
        align = Alignment.centerLeft;
        textColor = JTheme.textSecondary;
        break;
      default:
        bgColor = JTheme.red.withOpacity(0.1);
        align = Alignment.center;
        textColor = JTheme.red;
    }

    return Align(
      alignment: align,
      child: Container(
        margin: EdgeInsets.only(bottom: 8),
        padding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: JTheme.border.withOpacity(0.5)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 16, color: JTheme.cyan),
              SizedBox(width: 8),
            ],
            Flexible(
              child: SelectableText(text,
                  style: TextStyle(color: textColor, fontSize: 13)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: JTheme.border)),
        color: JTheme.bg,
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              onSubmitted: (_) => _send(),
              style: TextStyle(color: JTheme.textPrimary, fontSize: 14),
              decoration: InputDecoration(
                hintText: widget.online
                    ? 'Type a command…'
                    : 'Laptop offline — commands won\'t run',
                hintStyle: TextStyle(
                    color: widget.online ? JTheme.textMuted : JTheme.red.withOpacity(0.5)),
                contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                prefixIcon: Icon(Icons.chevron_right, color: JTheme.cyan),
              ),
            ),
          ),
          SizedBox(width: 8),
          InkWell(
            onTap: _send,
            borderRadius: BorderRadius.circular(12),
            child: Container(
              padding: EdgeInsets.all(10),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [JTheme.cyan, JTheme.cyanDim]),
                borderRadius: BorderRadius.circular(12),
                boxShadow: JTheme.glow(JTheme.cyan, intensity: 0.2),
              ),
              child: Icon(Icons.send, color: JTheme.bg, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}