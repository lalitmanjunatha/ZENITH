package com.zenith.phone

import android.graphics.Color
import android.os.Bundle
import android.telecom.Call
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Full-screen incoming call UI shown by [CallService] for a ringing call. */
class IncomingCallActivity : android.app.Activity() {

    private lateinit var title: TextView
    private lateinit var caller: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setTheme(R.style.Theme_ZenithPhone_IncomingCall)

        title = text(getString(R.string.call_from), 18f, Color.DKGRAY)
        caller = text("", 34f, Color.BLACK)

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 140, 48, 48)
            addView(title)
            addView(caller)
            addView(space(36))
            addView(buttonRow())
        }

        setContentView(ScrollView(this).apply { addView(content) })
        CallController.addListener(listener)
    }

    override fun onResume() { super.onResume(); refresh() }

    override fun onDestroy() {
        CallController.removeListener(listener)
        super.onDestroy()
    }

    private val listener = object : CallController.Listener {
        override fun onCallChanged() { runOnUiThread { refresh() } }
    }

    private fun refresh() {
        val c = CallController.activeCall
        if (c == null || c.state == Call.STATE_DISCONNECTED) { finish(); return }
        title.text = if (c.state == Call.STATE_RINGING)
            getString(R.string.call_from) else if (c.state == Call.STATE_DIALING)
            "Calling..." else "On call"
        caller.text = CallController.phoneNumber(c) ?: getString(R.string.call_unknown)
    }

    private fun buttonRow(): LinearLayout {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
        }
        row.addView(wideButton(getString(R.string.action_answer), Color.parseColor("#2EBD85")) {
            CallController.activeCall?.let { CallController.answer(it) }
            finish()
        })
        row.addView(space(18))
        row.addView(wideButton(getString(R.string.action_decline), Color.parseColor("#E5484D")) {
            CallController.activeCall?.let { CallController.decline(it) }
            finish()
        })
        row.addView(space(18))
        row.addView(wideButton(getString(R.string.action_ai), Color.parseColor("#4C8DFF")) {
            aiAnswer()
        })
        if (ConfigStore.aiMode(this) != "off") {
            row.addView(space(18))
            row.addView(wideButton(getString(R.string.action_decline_sms), Color.parseColor("#6b7280")) {
                CallController.activeCall?.let { c ->
                    CallController.declineWithSms(c, ConfigStore.screenMessage(this))
                }
                finish()
            })
        }
        row.addView(space(18))
        row.addView(wideButton(getString(R.string.action_take_over), Color.parseColor("#111827")) {
            // user answers normally; AI not used
            CallController.activeCall?.let { CallController.answer(it) }
            finish()
        })
        return row
    }

    private fun aiActive() {
        val c = CallController.activeCall ?: return
        CallController.answer(c)
        AiCallService.start(this, CallController.phoneNumber(c), "inbound")
        finish()
    }

    private fun wideButton(label: String, color: Int, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 18f
            setTextColor(Color.WHITE)
            setBackgroundColor(color)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 190)
            setOnClickListener { action() }
        }

    private fun text(s: String, size: Float, color: Int): TextView =
        TextView(this).apply {
            text = s
            textSize = size
            setTextColor(color)
            gravity = Gravity.CENTER
        }

    private fun space(h: Int): View =
        View(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, h)
        }
}