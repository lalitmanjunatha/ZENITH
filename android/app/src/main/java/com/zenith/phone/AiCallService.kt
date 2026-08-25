package com.zenith.phone

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Build
import android.os.IBinder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import io.livekit.android.LiveKit
import io.livekit.android.room.Room
import io.livekit.android.room.RoomEvent
import io.livekit.android.room.track.Track
import java.util.UUID

/**
 * Foreground service hosting the AI call. It:
 *  1. dispatches the desktop Zenith worker into a fresh room (AgentDispatch),
 *  2. joins that room publishing the phone mic (so the agent "hears" the caller),
 *  3. auto-plays the agent's spoken replies out the speaker into the live call.
 */
class AiCallService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var room: Room? = null
    private var audioManager: AudioManager? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager?
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, getString(R.string.app_name), NotificationManager.IMPORTANCE_LOW))
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val caller = intent?.getStringExtra(EXTRA_CALLER) ?: ""
        val direction = intent?.getStringExtra(EXTRA_DIRECTION) ?: "inbound"

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForeground(1, buildNotification(caller))
        }

        routeAudioToSpeaker()

        val roomName = "zenith-phone-${UUID.randomUUID().toString().take(8)}"
        scope.launch {
            // 1) Spawn the desktop agent first so the room is ready.
            AgentDispatcher.dispatchAgent(this@AiCallService, roomName, caller, direction)

            // 2) Join the room as the handset participant with the mic on.
            try {
                val r = LiveKit.create(applicationContext)
                room = r
                val token = TokenMinter.joinToken(
                    ConfigStore.apiKey(this@AiCallService),
                    ConfigStore.apiSecret(this@AiCallService),
                    roomName,
                    "zenithphone-" + caller.replace(Regex("[^0-9]"), "") + "-" + UUID.randomUUID().toString().take(4))
                r.connect(ConfigStore.url(this@AiCallService), token)
                r.localParticipant?.setMicrophoneEnabled(true)
                try {
                    val meta = org.json.JSONObject()
                        .put("zenith_call", true)
                        .put("caller", caller)
                        .put("direction", direction)
                    r.localParticipant?.setMetadata(meta.toString())
                } catch (_: Exception) {}
            } catch (e: Exception) {
                e.printStackTrace()
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun buildNotification(caller: String): Notification {
        val builder = Notification.Builder(this, CHANNEL)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.ai_thinking) + " " +
                (if (caller.isBlank()) "" else "($caller)"))
            .setPriority(Notification.PRIORITY_HIGH)
            .setOngoing(false)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            builder.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
        }
        return builder.build()
    }

    // Route the AI audio so the caller can be heard through the phone speaker
    // and the phone mic picks them up (hands-free during the live call).
    private fun routeAudioToSpeaker() {
        audioManager?.apply {
            try {
                mode = AudioManager.MODE_IN_COMMUNICATION
                isSpeakerphoneOn = true
            } catch (_: Exception) { }
        }
    }

    override fun onDestroy() {
        scope.cancel()
        room?.disconnect()
        room = null
        audioManager?.apply {
            try { mode = AudioManager.MODE_NORMAL; isSpeakerphoneOn = false } catch (_: Exception) {}
        }
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "zenith_call_channel"
        private const val EXTRA_CALLER = "caller"
        private const val EXTRA_DIRECTION = "direction"

        fun start(ctx: Context, caller: String?, direction: String) {
            val i = Intent(ctx, AiCallService::class.java)
                .putExtra(EXTRA_CALLER, caller ?: "")
                .putExtra(EXTRA_DIRECTION, direction)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(i)
            } else {
                ctx.startService(i)
            }
        }
    }
}