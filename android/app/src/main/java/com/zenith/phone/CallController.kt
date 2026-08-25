package com.zenith.phone

import android.telecom.Call
import android.telecom.InCallService
import android.telecom.VideoProfile
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Process-wide holder for the currently managed telecom Call(s), so both the
 * InCallService (which receives them) and the UI / AI layer can act on them.
 */
object CallController {

    var callService: CallService? = null

    private val calls = CopyOnWriteArrayList<Call>()

    @Volatile
    var activeCall: Call? = null
        private set

    interface Listener {
        fun onCallChanged()
    }

    private val listeners = CopyOnWriteArrayList<Listener>()

    @Suppress("DEPRECATION")
    private val callback = object : Call.Callback() {
        override fun onStateChanged(call: Call, state: Int) {
            notifyChanged()
        }

        override fun onCallRingbackTone(call: Call) {
            super.onCallRingbackTone(call)
        }
    }

    fun addCall(call: Call) {
        if (calls.contains(call)) return
        calls.add(call)
        activeCall = call
        call.registerCallback(callback)
        notifyChanged()
    }

    fun removeCall(call: Call) {
        call.unregisterCallback(callback)
        calls.remove(call)
        activeCall = calls.firstOrNull()
        if (activeCall == null) clear()
        notifyChanged()
    }

    fun canManage(call: Call?): Boolean =
        call != null && (call.state == Call.STATE_RINGING ||
            call.state == Call.STATE_ACTIVE ||
            call.state == Call.STATE_DIALING)

    fun answer(call: Call): Boolean {
        if (!canManage(call)) return false
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            call.answer(VideoProfile.STATE_AUDIO_ONLY)
        }
        notifyChanged()
        return true
    }

    fun decline(call: Call): Boolean {
        if (!canManage(call)) return false
        call.disconnect()
        removeCall(call)
        return true
    }

    /** Decline and auto-reply with a short text (Android may fall back gracefully). */
    fun declineWithSms(call: Call, message: String): Boolean {
        if (!canManage(call)) return false
        return try {
            val args = android.os.Bundle()
            args.putString(android.telecom.Call.Details.EXTRA_SMS_MESSAGE, message)
            call.sendCallRequest(Call.Details.REQUEST_SEND_SMS, args)
            decline(call)
            true
        } catch (_: Exception) {
            decline(call)
            true
        }
    }

    fun phoneNumber(call: Call?): String? = call?.details?.let { details ->
        details.handle?.let { handle ->
            val raw = handle.toString()
            raw.removePrefix("tel:").takeIf { it.isNotBlank() }
        }
    }

    fun addListener(l: Listener) = listeners.add(l)
    fun removeListener(l: Listener) = listeners.remove(l)

    fun clear() {
        calls.clear()
        activeCall = null
    }

    internal fun notifyChanged() {
        listeners.forEach { it.onCallChanged() }
    }
}