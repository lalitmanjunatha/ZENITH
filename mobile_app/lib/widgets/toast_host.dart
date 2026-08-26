import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/jarvis_theme.dart';

enum ToastType { info, success, warning, error }

class _ToastEntry {
  final int id;
  final String message;
  final ToastType type;
  final Duration duration;
  final String? actionLabel;
  final VoidCallback? onAction;
  bool visible = false;
  _ToastEntry(this.id, this.message, this.type, this.duration,
      this.actionLabel, this.onAction);
}

/// Central notification manager for the whole app.
/// Callers never handle positioning — [ZenithToastHost] renders every toast
/// anchored ABOVE the BottomNavigationBar plus system gesture insets.
class ZenithToasts {
  ZenithToasts._();
  static final ZenithToasts instance = ZenithToasts._();

  final List<_ToastEntry> _entries = [];
  final List<VoidCallback> _listeners = [];
  int _nextId = 1;
  static const _maxVisible = 3;

  String? _lastMessage;
  DateTime _lastAt = DateTime.fromMillisecondsSinceEpoch(0);

  void addListener(VoidCallback l) => _listeners.add(l);
  void removeListener(VoidCallback l) => _listeners.remove(l);

  void _notify() {
    for (final l in List.of(_listeners)) {
      l();
    }
  }

  /// Show a toast anywhere in the app.
  static void show(
    String message, {
    ToastType type = ToastType.info,
    Duration? duration,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    instance._show(message, type, duration, actionLabel, onAction);
  }

  static void success(String m, {Duration? duration}) =>
      show(m, type: ToastType.success, duration: duration);
  static void error(String m, {Duration? duration}) =>
      show(m, type: ToastType.error, duration: duration ?? const Duration(seconds: 5));
  static void warning(String m, {Duration? duration}) =>
      show(m, type: ToastType.warning, duration: duration);
  static void info(String m, {Duration? duration}) =>
      show(m, type: ToastType.info, duration: duration);

  /// Dismiss everything immediately (e.g. when a reply replaces "thinking").
  static void clear() => instance._clear();

  void _show(String message, ToastType type, Duration? duration,
      String? actionLabel, VoidCallback? onAction) {
    final now = DateTime.now();
    if (message == _lastMessage &&
        now.difference(_lastAt) < const Duration(milliseconds: 2500)) {
      return;
    }
    _lastMessage = message;
    _lastAt = now;

    final e = _ToastEntry(_nextId++, message, type,
        duration ?? const Duration(seconds: 4), actionLabel, onAction);
    _entries.add(e);

    while (_entries.length > _maxVisible) {
      _entries.removeAt(0);
    }
    _notify();

    Timer(e.duration, () {
      if (_entries.remove(e)) {
        if (_entries.isEmpty) _lastMessage = null;
        _notify();
      }
    });
  }

  void dismiss(int id) {
    final before = _entries.length;
    _entries.removeWhere((x) => x.id == id);
    if (_entries.length != before) {
      if (_entries.isEmpty) _lastMessage = null;
      _notify();
    }
  }

  void _clear() {
    if (_entries.isEmpty) return;
    _entries.clear();
    _lastMessage = null;
    _notify();
  }

  void tap(int id) {
    for (final e in List.of(_entries)) {
      if (e.id == id) {
        e.onAction?.call();
        dismiss(id);
        return;
      }
    }
  }

  Color _color(ToastType t) {
    switch (t) {
      case ToastType.success:
        return JTheme.green;
      case ToastType.warning:
        return JTheme.amber;
      case ToastType.error:
        return JTheme.red;
      case ToastType.info:
        return JTheme.cyan;
    }
  }

  IconData _icon(ToastType t) {
    switch (t) {
      case ToastType.success:
        return Icons.check_circle_outline;
      case ToastType.warning:
        return Icons.warning_amber_outlined;
      case ToastType.error:
        return Icons.error_outline;
      case ToastType.info:
        return Icons.info_outline;
    }
  }

  Widget buildEntry(BuildContext context, _ToastEntry e) {
    final accent = _color(e.type);
    return AnimatedOpacity(
      opacity: e.visible ? 1 : 0,
      duration: const Duration(milliseconds: 180),
      child: AnimatedSlide(
        offset: e.visible ? Offset.zero : const Offset(0, 0.35),
        curve: Curves.easeOutCubic,
        duration: const Duration(milliseconds: 220),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => dismiss(e.id),
            child: Container(
              width: double.infinity,
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: JTheme.surface.withOpacity(0.97),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: accent.withOpacity(0.45)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.35),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(_icon(e.type), color: accent, size: 18),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      e.message,
                      style: TextStyle(
                          color: JTheme.textPrimary, fontSize: 13, height: 1.25),
                    ),
                  ),
                  if (e.actionLabel != null) ...[
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: () => instance.tap(e.id),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        child: Text(e.actionLabel!,
                            style: TextStyle(
                                color: accent,
                                fontSize: 12,
                                fontWeight: FontWeight.w700)),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Mount ONCE inside the Scaffold body (above the nav bar slot).
/// Anchors toasts at: viewPadding.bottom (gesture inset) + gap, which sits
/// directly above the BottomNavigationBar because the host lives in the
/// body Stack, whose bottom edge already ends at the nav bar's top.
class ZenithToastHost extends StatefulWidget {
  const ZenithToastHost({super.key});

  @override
  State<ZenithToastHost> createState() => _ZenithToastHostState();
}

class _ZenithToastHostState extends State<ZenithToastHost> {
  @override
  void initState() {
    super.initState();
    ZenithToasts.instance.addListener(_onChange);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      for (final e in ZenithToasts.instance._entries) {
        e.visible = true;
      }
    });
  }

  void _onChange() {
    if (!mounted) return;
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      var changed = false;
      for (final e in ZenithToasts.instance._entries) {
        if (!e.visible) {
          e.visible = true;
          changed = true;
        }
      }
      if (changed && mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    ZenithToasts.instance.removeListener(_onChange);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final entries = ZenithToasts.instance._entries;
    final gestureInset = MediaQuery.viewPaddingOf(context).bottom;
    return Positioned(
      left: 16,
      right: 16,
      bottom: gestureInset + 12,
      child: IgnorePointer(
        ignoring: entries.isEmpty,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final e in entries.reversed)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: ZenithToasts.instance.buildEntry(context, e),
              ),
          ],
        ),
      ),
    );
  }
}
