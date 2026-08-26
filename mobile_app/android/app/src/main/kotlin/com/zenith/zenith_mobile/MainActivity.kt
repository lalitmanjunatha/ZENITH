package com.zenith.zenith_mobile

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.PowerManager
import android.os.StatFs
import android.provider.CallLog
import android.provider.CalendarContract
import android.provider.Telephony
import android.telephony.SmsManager
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONArray
import org.json.JSONObject
import java.net.InetAddress
import java.net.NetworkInterface
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : FlutterActivity() {
    private val channelName = "zenith_native"
    private val permReqCode = 4242
    private var pendingPermResult: MethodChannel.Result? = null
    private var cameraFlashId: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "requestPermissions" -> requestPerms(call.arguments, result)
                        "getBatteryLevel" -> result.success(batteryJson())
                        "toggleFlashlight" -> {
                            setTorch(call.argument<Boolean>("on") ?: true)
                            result.success(if ((call.argument<Boolean>("on") ?: true)) "ON" else "OFF")
                        }
                        "sendSms" -> result.success(sendSms(
                            call.argument<String>("number") ?: "",
                            call.argument<String>("body") ?: ""))
                        "readSms" -> result.success(readSms())
                        "callLog" -> result.success(callLogJson())
                        "bluetoothStatus" -> result.success(bluetoothJson())
                        "installedApps" -> result.success(installedAppsJson())
                        "openApp" -> result.success(openApp(call.arguments))
                        "screenState" -> result.success(screenStateJson())
                        "storageStats" -> result.success(storageJson())
                        "batterySaver" -> result.success(powerSaveJson())
                        "wifiInfo" -> result.success(wifiJson())
                        "getBrightness" -> result.success(window.attributes.screenBrightness)
                        "setBrightness" -> {
                            val v = ((call.argument<Number>("value") ?: 0.5).toDouble())
                                .coerceIn(0.01, 1.0)
                            val attrs = window.attributes
                            attrs.screenBrightness = v.toFloat()
                            window.attributes = attrs
                            result.success(v)
                        }
                        "getVolume" -> result.success(volumeJson(
                            call.argument<String>("stream") ?: "media"))
                        "setVolume" -> {
                            val pct = ((call.argument<Number>("pct") ?: 50).toInt()).coerceIn(0, 100)
                            setVolume(call.argument<String>("stream") ?: "media", pct)
                            result.success(pct)
                        }
                        "startAudioRec" -> { startRec(); result.success("recording") }
                        "stopAudioRec" -> result.success(stopRec())
                        "addCalendarEvent" -> result.success(addEvent(call.arguments))
                        "readCalendar" -> result.success(readEvents())
                        else -> result.notImplemented()
                    }
                } catch (e: Exception) {
                    result.error("NATIVE_ERR", e.message ?: e.toString(), null)
                }
            }
    }

    private fun json(a: JSONObject): Map<String, Any?> {
        val m = HashMap<String, Any?>()
        for (k in a.keys()) m[k] = a.opt(k)
        return m
    }

    // ── permissions ──
    private fun requestPerms(args: Any?, result: MethodChannel.Result) {
        val wanted = ((args as? Map<*, *>)?.get("permissions") as? List<*>)
            ?.filterIsInstance<String>() ?: emptyList()
        val missing = wanted.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            result.success(wanted.associateWith { true })
            return
        }
        pendingPermResult = result
        ActivityCompat.requestPermissions(this, missing.toTypedArray(), permReqCode)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == permReqCode) {
            val map = HashMap<String, Boolean>()
            for (i in permissions.indices) map[permissions[i]] =
                grantResults[i] == PackageManager.PERMISSION_GRANTED
            pendingPermResult?.success(map)
            pendingPermResult = null
        }
    }

    // ── battery ──
    @SuppressLint("BatteryLife")
    private fun batteryJson(): Map<String, Any?> {
        val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val intent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                status == BatteryManager.BATTERY_STATUS_FULL
        val o = JSONObject()
        o.put("level", level)
        o.put("charging", charging)
        return json(o)
    }

    // ── flashlight ──
    private fun flashCameraId(): String? {
        cameraFlashId?.let { return it }
        val cm = getSystemService(Context.CAMERA_SERVICE) as CameraManager
        for (id in cm.cameraIdList) {
            val hasFlash = cm.getCameraCharacteristics(id)
                .get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            if (hasFlash) {
                cameraFlashId = id
                return id
            }
        }
        return null
    }

    private fun setTorch(on: Boolean) {
        val id = flashCameraId() ?: throw IllegalStateException("No flashlight unit found")
        (getSystemService(Context.CAMERA_SERVICE) as CameraManager).setTorchMode(id, on)
    }

    // ── sms ──
    private fun smsManager(): SmsManager =
        if (Build.VERSION.SDK_INT >= 31)
            applicationContext.getSystemService(SmsManager::class.java)
        else @Suppress("DEPRECATION") SmsManager.getDefault()

    private fun sendSms(number: String, body: String): String {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("SEND_SMS permission not granted")
        smsManager().sendTextMessage(number, null, body, null, null)
        return "SMS sent to $number"
    }

    private fun readSms(): List<Map<String, Any?>> {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("READ_SMS permission not granted")
        val out = JSONArray()
        val cur = contentResolver.query(
            Telephony.Sms.CONTENT_URI,
            arrayOf(Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE),
            null, null, "${Telephony.Sms.DATE} DESC"
        )
        cur?.use { c ->
            var n = 0
            while (c.moveToNext() && n < 10) {
                val o = JSONObject()
                o.put("from", c.getString(0) ?: "?")
                o.put("body", c.getString(1) ?: "")
                o.put("date", fmt(c.getLong(2)))
                out.put(o)
                n++
            }
        }
        val list = ArrayList<Map<String, Any?>>()
        for (i in 0 until out.length()) list.add(json(out.getJSONObject(i)))
        return list
    }

    // ── call log ──
    private fun callLogJson(): List<Map<String, Any?>> {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("READ_CALL_LOG permission not granted")
        val out = JSONArray()
        val cur = contentResolver.query(
            CallLog.Calls.CONTENT_URI,
            arrayOf(
                CallLog.Calls.NUMBER, CallLog.Calls.CACHED_NAME,
                CallLog.Calls.TYPE, CallLog.Calls.DATE, CallLog.Calls.DURATION
            ),
            null, null, "${CallLog.Calls.DATE} DESC"
        )
        cur?.use { c ->
            var n = 0
            while (c.moveToNext() && n < 12) {
                val o = JSONObject()
                o.put("number", c.getString(0) ?: "?")
                o.put("name", c.getString(1) ?: "")
                o.put("type", when (c.getInt(2)) {
                    CallLog.Calls.INCOMING_TYPE -> "incoming"
                    CallLog.Calls.OUTGOING_TYPE -> "outgoing"
                    CallLog.Calls.MISSED_TYPE -> "missed"
                    else -> "other"
                })
                o.put("date", fmt(c.getLong(3)))
                o.put("duration_sec", c.getString(4) ?: "0")
                out.put(o)
                n++
            }
        }
        val list = ArrayList<Map<String, Any?>>()
        for (i in 0 until out.length()) list.add(json(out.getJSONObject(i)))
        return list
    }

    // ── bluetooth ──
    @SuppressLint("MissingPermission")
    private fun bluetoothJson(): Map<String, Any?> {
        val o = JSONObject()
        try {
            val ad = BluetoothAdapter.getDefaultAdapter()
            if (ad == null) {
                o.put("available", false)
                o.put("enabled", false)
                o.put("paired", 0)
            } else {
                o.put("available", true)
                o.put("enabled", ad.isEnabled)
                o.put("paired",
                    if (ad.isEnabled) ad.bondedDevices.size else 0)
            }
        } catch (e: SecurityException) {
            o.put("error", "BLUETOOTH_CONNECT permission needed")
        }
        return json(o)
    }

    // ── apps ──
    private fun launcherApps(): MutableList<JSONObject> {
        val pm = packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val ris = pm.queryIntentActivities(intent, 0)
        val seen = HashSet<String>()
        val out = ArrayList<JSONObject>()
        for (ri in ris) {
            val pkg = ri.activityInfo.packageName
            if (!seen.add(pkg)) continue
            val o = JSONObject()
            o.put("name", ri.loadLabel(pm).toString())
            o.put("pkg", pkg)
            out.add(o)
        }
        out.sortWith(compareBy { it.optString("name").lowercase(Locale.ROOT) })
        return out
    }

    private fun installedAppsJson(): List<Map<String, Any?>> =
        launcherApps().map { json(it) }

    private fun openApp(args: Any?): String {
        @Suppress("UNCHECKED_CAST")
        val m = args as? Map<*, *>
        val label = m?.get("label") as? String ?: ""
        val pkg = m?.get("pkg") as? String ?: ""
        if (pkg.isNotEmpty()) {
            val i = packageManager.getLaunchIntentForPackage(pkg)
            if (i != null) {
                startActivity(i)
                return "Opened $pkg"
            }
        }
        if (label.isNotEmpty()) {
            for (o in launcherApps()) {
                if (o.optString("name").equals(label, ignoreCase = true)) {
                    packageManager.getLaunchIntentForPackage(o.optString("pkg"))
                        ?.let { startActivity(it); return "Opened ${o.optString("name")}" }
                }
            }
            for (o in launcherApps()) {
                if (o.optString("name").contains(label, ignoreCase = true)) {
                    packageManager.getLaunchIntentForPackage(o.optString("pkg"))
                        ?.let { startActivity(it); return "Opened ${o.optString("name")}" }
                }
            }
            throw IllegalArgumentException("No app matching '$label'")
        }
        throw IllegalArgumentException("Provide app name")
    }

    // ── screen / power / storage ──
    private fun screenStateJson(): Map<String, Any?> {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val km = getSystemService(Context.KEYGUARD_SERVICE) as android.app.KeyguardManager
        val o = JSONObject()
        o.put("screen", if (pm.isInteractive) "on" else "off")
        o.put("locked", km.isKeyguardLocked)
        return json(o)
    }

    private fun storageJson(): Map<String, Any?> {
        val stat = StatFs(Environment.getDataDirectory().path)
        val totalG = stat.totalBytes / 1073741824.0
        val freeG = stat.availableBytes / 1073741824.0
        val o = JSONObject()
        o.put("total_gb", Math.round(totalG * 10) / 10.0)
        o.put("free_gb", Math.round(freeG * 10) / 10.0)
        o.put("used_pct", Math.round((totalG - freeG) / totalG * 100))
        return json(o)
    }

    private fun powerSaveJson(): Map<String, Any?> {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val o = JSONObject()
        o.put("power_save", pm.isPowerSaveMode)
        return json(o)
    }

    // ── network ──
    private fun wifiJson(): Map<String, Any?> {
        val o = JSONObject()
        var ip = ""
        try {
            val en = NetworkInterface.getNetworkInterfaces()
            while (en.hasMoreElements()) {
                val ni = en.nextElement()
                if (!ni.isUp || ni.isLoopback) continue
                for (ea in ni.inetAddresses) {
                    if (!ea.isLoopbackAddress && ea is InetAddress &&
                        ea.hostAddress?.contains(':') != true
                    ) {
                        ip = ea.hostAddress ?: ""
                        if (ni.name.startsWith("wlan")) break
                    }
                }
            }
        } catch (_: Exception) {}
        o.put("ip", ip)
        o.put("connected", ip.isNotEmpty())
        try {
            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val info = wm.connectionInfo
            val ssid = info?.ssid ?: "<unknown>"
            o.put("ssid", if (ssid.startsWith("\"")) ssid.trim('"') else
                if (ssid == "<unknown ssid>") "" else ssid)
        } catch (_: Exception) {}
        return json(o)
    }

    // ── calendar ──
    private fun addEvent(args: Any?): String {
        @Suppress("UNCHECKED_CAST")
        val m = args as? Map<*, *> ?: throw IllegalArgumentException("args")
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CALENDAR)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("WRITE_CALENDAR permission not granted")
        val calCur = contentResolver.query(
            CalendarContract.Calendars.CONTENT_URI,
            arrayOf(CalendarContract.Calendars._ID), null, null, null
        )
        val calId = calCur?.use { c -> if (c.moveToFirst()) c.getLong(0) else null }
            ?: throw IllegalStateException("No calendar account found on phone")
        val title = m["title"] as? String ?: "ZENITH Event"
        val begin = (m["begin_ms"] as? Number)?.toLong()
            ?: System.currentTimeMillis() + 3600000
        val durMs = ((m["duration_min"] as? Number)?.toLong() ?: 30L) * 60000
        val cv = android.content.ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calId)
            put(CalendarContract.Events.TITLE, title)
            put(CalendarContract.Events.DTSTART, begin)
            put(CalendarContract.Events.DTEND, begin + durMs)
            put(CalendarContract.Events.EVENT_TIMEZONE,
                java.util.TimeZone.getDefault().id)
        }
        val uri = contentResolver.insert(CalendarContract.Events.CONTENT_URI, cv)
        return "Event '$title' added"
    }

    private fun readEvents(): List<Map<String, Any?>> {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALENDAR)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("READ_CALENDAR permission not granted")
        val now = System.currentTimeMillis()
        val out = JSONArray()
        val cur = contentResolver.query(
            CalendarContract.Instances.CONTENT_URI,
            arrayOf(
                CalendarContract.Instances.TITLE,
                CalendarContract.Instances.BEGIN,
                CalendarContract.Instances.END
            ),
            "${CalendarContract.Instances.BEGIN} >= ? AND ${CalendarContract.Instances.BEGIN} <= ?",
            arrayOf(now.toString(), (now + 604800000L).toString()),
            "${CalendarContract.Instances.BEGIN} ASC"
        )
        cur?.use { c ->
            var n = 0
            while (c.moveToNext() && n < 10) {
                val o = JSONObject()
                o.put("title", c.getString(0) ?: "(untitled)")
                o.put("start", fmt(c.getLong(1)))
                o.put("end", fmt(c.getLong(2)))
                out.put(o)
                n++
            }
        }
        val list = ArrayList<Map<String, Any?>>()
        for (i in 0 until out.length()) list.add(json(out.getJSONObject(i)))
        return list
    }

    private fun fmt(ms: Long): String =
        SimpleDateFormat("dd MMM hh:mm a", Locale.getDefault()).format(Date(ms))

    // ── volume ──
    private fun streamFor(name: String): Int =
        if (name == "ring")
            android.media.AudioManager.STREAM_RING
        else android.media.AudioManager.STREAM_MUSIC

    private fun volumeJson(stream: String): Map<String, Any?> {
        val am = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
        val max = am.getStreamMaxVolume(streamFor(stream))
        val cur = am.getStreamVolume(streamFor(stream))
        val o = JSONObject()
        o.put("stream", stream)
        o.put("max", max)
        o.put("level", cur)
        o.put("percent", Math.round(cur * 100.0 / max))
        return json(o)
    }

    private fun setVolume(stream: String, pct: Int) {
        val am = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
        val max = am.getStreamMaxVolume(streamFor(stream))
        am.setStreamVolume(streamFor(stream), Math.round(max * pct / 100.0).toInt(), 0)
    }

    // ── audio recorder ──
    private var recorder: android.media.MediaRecorder? = null
    private var recPath: String? = null

    @SuppressLint("WrongConstant")
    private fun startRec() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) throw SecurityException("RECORD_AUDIO permission not granted")
        stopRec()
        val path = "${externalCacheDir?.absolutePath ?: cacheDir.absolutePath}" +
                "/zenith_note_${System.currentTimeMillis()}.m4a"
        @Suppress("DEPRECATION")
        val mr = if (Build.VERSION.SDK_INT >= 31)
            android.media.MediaRecorder(applicationContext)
        else android.media.MediaRecorder()
        mr.setAudioSource(android.media.MediaRecorder.AudioSource.MIC)
        mr.setOutputFormat(android.media.MediaRecorder.OutputFormat.MPEG_4)
        mr.setAudioEncoder(android.media.MediaRecorder.AudioEncoder.AAC)
        mr.setAudioEncodingBitRate(128000)
        mr.setAudioSamplingRate(44100)
        mr.setOutputFile(path)
        mr.prepare()
        mr.start()
        recorder = mr
        recPath = path
    }

    private fun stopRec(): String {
        val mr = recorder ?: throw IllegalStateException("Not recording")
        return try {
            mr.stop()
            recPath ?: ""
        } finally {
            mr.release()
            recorder = null
        }
    }
}
