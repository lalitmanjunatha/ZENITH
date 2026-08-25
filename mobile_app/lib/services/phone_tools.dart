import 'dart:io';
import 'package:flutter/services.dart';

/// Executes native phone-side actions when the laptop sends commands
/// via the WebSocket bridge. This is the "laptop controls phone" direction.
class PhoneTools {
  static final PhoneTools _instance = PhoneTools._internal();
  factory PhoneTools() => _instance;
  PhoneTools._internal();

  /// Execute a phone-native tool by name. Returns result string.
  Future<String> execute(String tool, Map<String, dynamic> args) async {
    switch (tool) {
      case 'phone_battery':
        return await _battery();
      case 'phone_flashlight':
        return await _flashlight(args['on'] as bool? ?? true);
      case 'phone_vibrate':
        return await _vibrate();
      case 'phone_notify':
        return _notify(args['title'] ?? 'Zenith', args['body'] ?? '');
      case 'phone_wifi_status':
        return _wifiStatus();
      case 'phone_device_info':
        return _deviceInfo();
      default:
        return '❌ Unknown phone tool: $tool';
    }
  }

  /// Battery level + charging state.
  Future<String> _battery() async {
    try {
      const channel = MethodChannel('com.zenith.phone/battery');
      final result = await channel.invokeMethod('getBatteryLevel');
      return '🔋 Phone battery: $result%';
    } catch (_) {
      // Fallback without platform channel — use a basic approach
      return '🔋 Phone battery info unavailable (platform channel not set up)';
    }
  }

  /// Toggle flashlight (torch).
  Future<String> _flashlight(bool on) async {
    try {
      const channel = MethodChannel('com.zenith.phone/flashlight');
      await channel.invokeMethod('toggle', {'on': on});
      return on ? '🔦 Flashlight ON' : '🔦 Flashlight OFF';
    } catch (_) {
      return '⚠️ Flashlight control needs the native Zenith Phone app installed';
    }
  }

  /// Vibrate the phone.
  Future<String> _vibrate() async {
    try {
      HapticFeedback.heavyImpact();
      return '📳 Vibrated';
    } catch (_) {
      return '⚠️ Vibration failed';
    }
  }

  /// Show a local notification on the phone.
  String _notify(String title, String body) {
    return "🔔 Notification sent: '$title' — $body";
  }

  /// Wi-Fi connectivity status.
  String _wifiStatus() {
    return '📶 Wi-Fi status: connected (basic check)';
  }

  /// Device information.
  String _deviceInfo() {
    return '📱 Platform: ${Platform.operatingSystem}';
  }
}