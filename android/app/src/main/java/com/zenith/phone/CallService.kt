package com.zenith.phone

import android.content.Intent
import android.telecom.Call
import android.telecom.InCallService

/**
 * The Telecom hook that gives us incoming/outgoing call lifecycle events.
 * Because Zenith Phone is the default dialer, this is bound by the OS.
 */
class CallService : InCallService() {

    override fun onCreate() {
        super.onCreate()
        CallController.callService = this
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        CallController.addCall(call)
        if (call.state == Call.STATE_RINGING) {
            val i = Intent(this, IncomingCallActivity::class.java)
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS)
            startActivity(i)
        }
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        CallController.removeCall(call)
    }

    override fun onDestroy() {
        CallController.callService = null
        CallController.clear()
        super.onDestroy()
    }
}