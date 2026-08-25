import 'package:flutter/material.dart';
import 'dart:ui';

class JTheme {
  // ── Palette ──
  static const bg = Color(0xFF0A0E14);
  static const surface = Color(0xFF111820);
  static const card = Color(0xFF16202B);
  static const border = Color(0xFF1E2D3D);
  static const cyan = Color(0xFF00D4FF);
  static const cyanDim = Color(0xFF00A8CC);
  static const green = Color(0xFF00E676);
  static const red = Color(0xFFFF5252);
  static const amber = Color(0xFFFFC107);
  static const textPrimary = Color(0xFFE8F0F8);
  static const textSecondary = Color(0xFF7F95A8);
  static const textMuted = Color(0xFF3D5166);

  static ThemeData dark() {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bg,
      colorScheme: ColorScheme.dark(
        primary: cyan,
        secondary: cyanDim,
        surface: surface,
        error: red,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: bg.withOpacity(0.85),
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: cyan,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.5,
        ),
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: border, width: 1),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: cyan, width: 1.5),
        ),
        hintStyle: TextStyle(color: textMuted),
      ),
    );
  }

  // ── Glow decorations ──
  static BoxDecoration glassCard({Color? borderColor}) {
    return BoxDecoration(
      color: card.withOpacity(0.7),
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: borderColor ?? border, width: 1),
    );
  }

  static List<BoxShadow> glow(Color color, {double intensity = 0.3}) {
    return [
      BoxShadow(color: color.withOpacity(intensity), blurRadius: 12, spreadRadius: 1),
    ];
  }
}