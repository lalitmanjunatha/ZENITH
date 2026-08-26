import 'dart:async';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_contacts/flutter_contacts.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:android_intent_plus/android_intent.dart';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:share_plus/share_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// Executes every phone-native Zenith tool.
/// Plugin-based tools run directly; hardware/SMS/calendar/app tools route
/// through the `zenith_native` MethodChannel implemented in MainActivity.kt.
class PhoneTools {
  static final PhoneTools _instance = PhoneTools._internal();
  factory PhoneTools() => _instance;
  PhoneTools._internal();

  static const _ch = MethodChannel('zenith_native');
  final ImagePicker _picker = ImagePicker();
  final FlutterLocalNotificationsPlugin _notifPlugin =
      FlutterLocalNotificationsPlugin();
  bool _notifInit = false;
  final FlutterTts _tts = FlutterTts();
  bool _ttsInit = false;

  Future<dynamic> _native(String method, [Map<String, dynamic>? args]) async {
    try {
      return await _ch.invokeMethod(method, args ?? {});
    } on PlatformException catch (e) {
      return {'__error': e.message ?? e.code};
    } on MissingPluginException {
      return {'__error': 'Native layer missing - reinstall the APK'};
    }
  }

  String _err(dynamic r) => r is Map ? (r['__error']?.toString() ?? '?') : '?';

  Future<bool> _perms(List<String> wanted) async {
    final r = await _native('requestPermissions', {'permissions': wanted});
    if (r is Map && r['__error'] == null) {
      return r.values.whereType<bool>().every((g) => g);
    }
    return false;
  }

  Future<void> _initNotifs() async {
    if (_notifInit) return;
    const initSettings = InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'));
    await _notifPlugin.initialize(initSettings);
    _notifInit = true;
  }

  Future<void> _initTts() async {
    if (_ttsInit) return;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5);
    await _tts.setPitch(0.9);
    _ttsInit = true;
  }

  /// Execute a phone tool by registry name.
  Future<String> execute(String tool, Map<String, dynamic> args) async {
    switch (tool) {
      case 'phone_battery':
        return await _battery();
      case 'phone_flashlight':
        return await _flashlight(args['on'] as bool? ?? true);
      case 'phone_vibrate':
        HapticFeedback.heavyImpact();
        await Future.delayed(const Duration(milliseconds: 150));
        HapticFeedback.heavyImpact();
        return 'Vibrated';
      case 'phone_notify':
        return await _notify(args['title']?.toString() ?? 'ZENITH',
            args['body']?.toString() ?? '');
      case 'phone_wifi_status':
        return await _wifiStatus();
      case 'phone_device_info':
        return await _deviceInfo();
      case 'phone_location':
        return await _location();
      case 'phone_camera_photo':
        return await _photo(false);
      case 'phone_selfie':
        return await _photo(true);
      case 'phone_brightness':
        return await _brightness(args);
      case 'phone_volume_media':
        return await _volume(args, stream: 'media');
      case 'phone_volume_ring':
        return await _volume(args, stream: 'ring');
      case 'phone_send_sms':
        return await _sendSms(
            args['number']?.toString() ?? '', args['body']?.toString() ?? '');
      case 'phone_read_sms':
        return await _readSms();
      case 'phone_call_log':
        return await _callLog();
      case 'phone_place_call':
        return await _placeCall(args['number']?.toString() ?? '');
      case 'phone_contacts_search':
        return await _contacts(args['query']?.toString() ?? '');
      case 'phone_bluetooth_status':
        return await _bluetooth();
      case 'phone_installed_apps':
        return await _installedApps();
      case 'phone_open_app':
        return await _openApp(args['name']?.toString() ?? '');
      case 'phone_open_url':
        return await _openUrl(args['url']?.toString() ?? '');
      case 'phone_set_alarm':
        return await _setAlarm(args);
      case 'phone_calendar_add':
        return await _calendarAdd(args);
      case 'phone_calendar_read':
        return await _calendarRead();
      case 'phone_clipboard_get':
        final v = await Clipboard.getData('text/plain');
        return 'Clipboard: ${v?.text ?? "(empty)"}';
      case 'phone_clipboard_set':
        await Clipboard.setData(
            ClipboardData(text: args['text']?.toString() ?? ''));
        return 'Copied to clipboard';
      case 'phone_share_text':
        await Share.share(args['text']?.toString() ?? '',
            subject: args['subject']?.toString());
        return 'Share sheet opened';
      case 'phone_sensors':
        return await _sensors();
      case 'phone_screen_state':
        return await _screenState();
      case 'phone_storage_stats':
        return await _storage();
      case 'phone_record_note':
        return await _recordNote((args['seconds'] as num?)?.toInt() ?? 5);
      case 'phone_network_info':
        return await _networkInfo();
      case 'phone_battery_saver':
        return await _batterySaver();
      case 'phone_tts_speak':
        return await _speak(args['text']?.toString() ?? 'Zenith online.');
      default:
        return 'Unknown phone tool: $tool';
    }
  }

  // ── native-channel backed ──
  Future<String> _battery() async {
    final r = await _native('getBatteryLevel');
    if (r is Map && r['__error'] == null) {
      return 'Battery ${r['level']}% - ${r['charging'] == true ? "charging" : "on battery"}';
    }
    return 'Battery read failed: ${_err(r)}';
  }

  Future<String> _flashlight(bool on) async {
    final r = await _native('toggleFlashlight', {'on': on});
    return r is String
        ? 'Flashlight ${on ? "ON" : "OFF"}'
        : 'Flashlight failed: ${_err(r)}';
  }

  Future<String> _wifiStatus() async {
    final r = await _native('wifiInfo');
    if (r is Map && r['__error'] == null) {
      final ssid = (r['ssid'] as String?) ?? '';
      final ip = (r['ip'] as String?) ?? '';
      final conn = r['connected'] == true;
      return 'Wi-Fi: ${conn ? "connected" : "disconnected"}'
          '${ssid.isNotEmpty ? " ($ssid)" : ""}${ip.isNotEmpty ? " IP $ip" : ""}';
    }
    return 'Wi-Fi check failed: ${_err(r)}';
  }

  Future<String> _sendSms(String number, String body) async {
    if (number.isEmpty || body.isEmpty) {
      return 'Need a number and a message body';
    }
    if (!await _perms(['android.permission.SEND_SMS'])) {
      return 'SEND_SMS permission denied';
    }
    final r = await _native('sendSms', {'number': number, 'body': body});
    return r is String ? 'SMS sent: $r' : 'SMS failed: ${_err(r)}';
  }

  Future<String> _readSms() async {
    if (!await _perms(['android.permission.READ_SMS'])) {
      return 'READ_SMS permission denied';
    }
    final r = await _native('readSms');
    if (r is List) {
      if (r.isEmpty) return 'Inbox empty';
      final b = StringBuffer('Last messages:\n');
      for (final m in r.cast<Map>()) {
        b.writeln('${m['from']}: "${m['body']}" (${m['date']})');
      }
      return b.toString();
    }
    return 'Read SMS failed: ${_err(r)}';
  }

  Future<String> _callLog() async {
    if (!await _perms(['android.permission.READ_CALL_LOG'])) {
      return 'READ_CALL_LOG permission denied';
    }
    final r = await _native('callLog');
    if (r is List) {
      if (r.isEmpty) return 'Call log empty';
      final b = StringBuffer('Recent calls:\n');
      for (final c in r.cast<Map>()) {
        final who = (c['name'] as String?)?.isNotEmpty == true
            ? c['name']
            : c['number'];
        b.writeln('$who (${c['type']}) ${c['date']}');
      }
      return b.toString();
    }
    return 'Call log failed: ${_err(r)}';
  }

  Future<String> _bluetooth() async {
    final r = await _native('bluetoothStatus');
    if (r is Map && r['__error'] == null) {
      if (r['available'] != true) return 'Bluetooth not available on this device';
      return r['enabled'] == true
          ? 'Bluetooth ON - ${r['paired']} paired device(s)'
          : 'Bluetooth OFF';
    }
    return 'Bluetooth check failed: ${_err(r)}';
  }

  Future<String> _installedApps() async {
    final r = await _native('installedApps');
    if (r is List) {
      final names =
          r.cast<Map>().map((m) => m['name']).take(25).join(', ');
      return '${r.length} launchable apps. Some: $names';
    }
    return 'App list failed: ${_err(r)}';
  }

  Future<String> _openApp(String name) async {
    if (name.isEmpty) return 'Say which app to open';
    final r = await _native('openApp', {'label': name});
    return r is String ? '$r' : 'Open app failed: ${_err(r)}';
  }

  Future<String> _screenState() async {
    final r = await _native('screenState');
    if (r is Map && r['__error'] == null) {
      return 'Screen ${r['screen']} - ${r['locked'] == true ? "locked" : "unlocked"}';
    }
    return 'Screen state failed: ${_err(r)}';
  }

  Future<String> _storage() async {
    final r = await _native('storageStats');
    if (r is Map && r['__error'] == null) {
      return 'Storage ${r['used_pct']}% used, ${r['free_gb']} GB free of ${r['total_gb']} GB';
    }
    return 'Storage failed: ${_err(r)}';
  }

  Future<String> _batterySaver() async {
    final r = await _native('batterySaver');
    if (r is Map && r['__error'] == null) {
      return 'Battery saver is ${r['power_save'] == true ? "ON" : "OFF"}';
    }
    return 'Battery saver check failed: ${_err(r)}';
  }

  Future<String> _calendarAdd(Map<String, dynamic> args) async {
    if (!await _perms(['android.permission.WRITE_CALENDAR'])) {
      return 'WRITE_CALENDAR permission denied';
    }
    final title = args['title']?.toString() ?? 'ZENITH Event';
    final minutesAhead = (args['in_minutes'] as num?)?.toInt() ?? 60;
    final r = await _native('addCalendarEvent', {
      'title': title,
      'begin_ms': DateTime.now()
          .add(Duration(minutes: minutesAhead))
          .millisecondsSinceEpoch,
      'duration_min': (args['duration_min'] as num?)?.toInt() ?? 30,
    });
    return r is String ? r : 'Calendar add failed: ${_err(r)}';
  }

  Future<String> _calendarRead() async {
    if (!await _perms(['android.permission.READ_CALENDAR'])) {
      return 'READ_CALENDAR permission denied';
    }
    final r = await _native('readCalendar');
    if (r is List) {
      if (r.isEmpty) return 'No events in the next 7 days';
      final b = StringBuffer('Upcoming events:\n');
      for (final e in r.cast<Map>()) {
        b.writeln('${e['title']} @ ${e['start']}');
      }
      return b.toString();
    }
    return 'Calendar read failed: ${_err(r)}';
  }

  // ── plugin backed ──
  Future<String> _notify(String title, String body) async {
    await _initNotifs();
    const details = NotificationDetails(
        android: AndroidNotificationDetails('zenith_tools', 'Zenith Tools',
            channelDescription: 'Tool results and alerts',
            importance: Importance.high,
            priority: Priority.high));
    await _notifPlugin.show(
        DateTime.now().millisecondsSinceEpoch % 100000, title, body, details);
    return "Notification shown: '$title'${body.isNotEmpty ? " - $body" : ""}";
  }

  Future<String> _deviceInfo() async {
    final info = DeviceInfoPlugin();
    if (Platform.isAndroid) {
      final a = await info.androidInfo;
      return '${a.manufacturer} ${a.model}, Android ${a.version.release} (SDK ${a.version.sdkInt})';
    }
    return '${Platform.operatingSystem} ${Platform.operatingSystemVersion}';
  }

  Future<String> _location() async {
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    if (perm == LocationPermission.denied ||
        perm == LocationPermission.deniedForever) {
      return 'Location permission denied';
    }
    try {
      final p = await Geolocator.getCurrentPosition(
          locationSettings:
              const LocationSettings(accuracy: LocationAccuracy.medium));
      return 'Location: ${p.latitude.toStringAsFixed(5)}, '
          '${p.longitude.toStringAsFixed(5)} (plus-minus ${p.accuracy.round()}m)';
    } catch (e) {
      return 'GPS failed: $e';
    }
  }

  Future<String> _photo(bool selfie) async {
    if (selfie) {
      try {
        final intent = AndroidIntent(
          action: 'android.media.action.IMAGE_CAPTURE_SECURE',
          arguments: <String, Object?>{
            'android.intent.extras.CAMERA_FACING': 1,
            'android.intent.extra.USE_FRONT_CAMERA': true,
          },
        );
        await intent.launch();
        return 'Front camera opened - capture your selfie there';
      } catch (e) {
        return 'Selfie failed: $e';
      }
    }
    try {
      final x = await _picker.pickImage(source: ImageSource.camera);
      if (x == null) return 'Camera cancelled';
      final kb = ((await x.length()) / 1024).round();
      return 'Photo captured (${x.name}, ${kb}KB)';
    } catch (e) {
      return 'Camera failed: $e';
    }
  }

  Future<String> _brightness(Map<String, dynamic> args) async {
    try {
      final setV = (args['value'] as num?)?.toDouble();
      if (setV == null) {
        final cur = await _native('getBrightness');
        if (cur is num) return 'Brightness ${(cur * 100).round()}%';
        return 'Brightness failed: ${_err(cur)}';
      }
      final norm =
          setV > 1 ? (setV / 255).clamp(0.01, 1.0) : setV.clamp(0.01, 1.0);
      final r = await _native('setBrightness', {'value': norm});
      if (r is num) return 'Brightness set to ${(norm * 100).round()}%';
      return 'Brightness failed: ${_err(r)}';
    } catch (e) {
      return 'Brightness failed: $e';
    }
  }

  Future<String> _volume(Map<String, dynamic> args,
      {String stream = 'media'}) async {
    try {
      final setV = (args['value'] as num?)?.toDouble();
      if (setV == null) {
        final r = await _native('getVolume', {'stream': stream});
        if (r is Map && r['__error'] == null) {
          return 'Volume ${(r['percent'] as num?) ?? 0}%';
        }
        return 'Volume failed: ${_err(r)}';
      }
      final pct = (setV > 1 ? (setV / 100).round() : setV.round())
          .clamp(0, 100);
      await _native('setVolume', {'stream': stream, 'pct': pct});
      return 'Volume set to $pct%';
    } catch (e) {
      return 'Volume failed: $e';
    }
  }

  Future<String> _placeCall(String number) async {
    if (number.isEmpty) return 'Say which number to call';
    final uri = Uri(scheme: 'tel', path: number);
    final granted = await _perms(['android.permission.CALL_PHONE']);
    try {
      final ok = await launchUrl(uri,
          mode: LaunchMode.externalApplication);
      return ok
          ? (granted ? 'Calling $number' : 'Dialer opened for $number')
          : 'Could not place call';
    } catch (e) {
      return 'Call failed: $e';
    }
  }

  Future<String> _contacts(String query) async {
    if (!await _perms(['android.permission.READ_CONTACTS'])) {
      return 'READ_CONTACTS permission denied';
    }
    try {
      final contacts = await FlutterContacts.getContacts(
          withProperties: true, withPhoto: false);
      final q = query.toLowerCase().trim();
      final hits = contacts
          .where((c) =>
              q.isEmpty || c.displayName.toLowerCase().contains(q))
          .take(8)
          .toList();
      if (hits.isEmpty) return 'No contacts matching "$query"';
      final b = StringBuffer('Contacts:\n');
      for (final c in hits) {
        final phone = c.phones.isNotEmpty ? c.phones.first.number : '';
        b.writeln('${c.displayName}${phone.isNotEmpty ? " - $phone" : ""}');
      }
      return b.toString();
    } catch (e) {
      return 'Contacts failed: $e';
    }
  }

  Future<String> _openUrl(String url) async {
    var u = url.trim();
    if (!u.startsWith('http')) u = 'https://$u';
    try {
      final ok = await launchUrl(Uri.parse(u),
          mode: LaunchMode.externalApplication);
      return ok ? 'Opened $u' : 'Could not open URL';
    } catch (e) {
      return 'URL open failed: $e';
    }
  }

  Future<String> _setAlarm(Map<String, dynamic> args) async {
    try {
      final hour = (args['hour'] as num?)?.toInt();
      final minute = (args['minute'] as num?)?.toInt() ?? 0;
      if (hour != null && hour >= 0 && hour < 24) {
        final intent = AndroidIntent(
          action: 'android.intent.action.SET_ALARM',
          data: 'content://com.android.deskclock/alarm',
          arguments: <String, Object?>{
            'android.intent.extra.alarm.HOUR': hour,
            'android.intent.extra.alarm.MINUTES': minute,
            'android.intent.extra.alarm.SKIP_UI': true,
            'android.intent.extra.alarm.MESSAGE':
                args['label']?.toString() ?? 'ZENITH alarm',
          },
        );
        await intent.launch();
        return 'Alarm set for $hour:${minute.toString().padLeft(2, '0')}';
      }
      final secs = (args['seconds'] as num?)?.toInt() ?? 300;
      final intent = AndroidIntent(
        action: 'android.intent.action.SET_TIMER',
        arguments: <String, Object?>{
          'android.intent.extra.alarm.LENGTH': secs,
          'android.intent.extra.alarm.SKIP_UI': true,
          'android.intent.extra.alarm.MESSAGE':
              args['label']?.toString() ?? 'ZENITH timer',
        },
      );
      await intent.launch();
      return 'Timer set for $secs seconds';
    } catch (e) {
      return 'Alarm failed: $e';
    }
  }

  Future<String> _sensors() async {
    try {
      AccelerometerEvent? acc;
      GyroscopeEvent? gyro;
      final accSub = accelerometerEventStream().listen((e) => acc ??= e);
      final gyroSub = gyroscopeEventStream().listen((e) => gyro ??= e);
      await Future.delayed(const Duration(milliseconds: 400));
      await accSub.cancel();
      await gyroSub.cancel();
      if (acc == null && gyro == null) return 'No sensor data available';
      final b = StringBuffer('Sensor snapshot:');
      final a = acc;
      if (a != null) {
        b.write(' accel(x:${a.x.toStringAsFixed(2)}, '
            'y:${a.y.toStringAsFixed(2)}, z:${a.z.toStringAsFixed(2)}) m/s2');
      }
      final g = gyro;
      if (g != null) {
        b.write(' gyro(x:${g.x.toStringAsFixed(2)}, '
            'y:${g.y.toStringAsFixed(2)}, z:${g.z.toStringAsFixed(2)}) rad/s');
      }
      return b.toString();
    } catch (e) {
      return 'Sensors failed: $e';
    }
  }

  Future<String> _recordNote(int seconds) async {
    try {
      if (!await _perms(['android.permission.RECORD_AUDIO'])) {
        return 'Microphone permission denied';
      }
      final start = await _native('startAudioRec');
      if (start is Map && start['__error'] != null) {
        return 'Recording failed: ${_err(start)}';
      }
      await Future.delayed(Duration(seconds: seconds.clamp(1, 60)));
      final path = await _native('stopAudioRec');
      if (path is String && path.isNotEmpty) {
        return 'Audio note recorded (${seconds}s): ${path.split('/').last}';
      }
      return 'Recording failed: ${path is Map ? _err(path) : "no file"}';
    } catch (e) {
      return 'Recording failed: $e';
    }
  }

  Future<String> _networkInfo() async {
    final conn = await _wifiStatus();
    try {
      final connectivity = await Connectivity().checkConnectivity();
      final kind = connectivity.contains(ConnectivityResult.wifi)
          ? 'Wi-Fi'
          : connectivity.contains(ConnectivityResult.mobile)
              ? 'Mobile data'
              : connectivity.contains(ConnectivityResult.ethernet)
                  ? 'Ethernet'
                  : 'None';
      return 'Network: $kind. $conn'.replaceAll('Wi-Fi: ', '');
    } catch (_) {
      return conn;
    }
  }

  Future<String> _speak(String text) async {
    await _initTts();
    await _tts.setQueueMode(1);
    await _tts.speak(text);
    return 'Speaking: $text';
  }
}
