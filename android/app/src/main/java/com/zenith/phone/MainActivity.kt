package com.zenith.phone

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.telecom.TelecomManager
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Setup & status screen for the call-control + AI dialer. */
class MainActivity : Activity() {

    private lateinit var dialerStatus: TextView
    private lateinit var urlEdt: EditText
    private lateinit var keyEdt: EditText
    private lateinit var secretEdt: EditText
    private lateinit var smsEdt: EditText
    private lateinit var modeEdt: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        dialerStatus = TextView(this).apply {
            textSize = 15f
            gravity = Gravity.CENTER
            setPadding(0, 24, 0, 24)
        }

        urlEdt = field("LiveKit URL", ConfigStore.url(this))
        keyEdt = field("API Key", ConfigStore.apiKey(this))
        secretEdt = field("API Secret", ConfigStore.apiSecret(this))
        smsEdt = field("Decline SMS text", ConfigStore.screenMessage(this))
        modeEdt = field("AI mode (auto / ask / off)", ConfigStore.aiMode(this))

        val dialerBtn = Button(this).apply { text = "Make default dialer" }
        dialerBtn.setOnClickListener { makeDefaultDialer() }

        val grantBtn = Button(this).apply { text = "Grant permissions" }
        grantBtn.setOnClickListener { requestPermissions() }

        val saveBtn = Button(this).apply { text = "Save config" }
        saveBtn.setOnClickListener {
            ConfigStore.setUrl(this, urlEdt.text.toString().trim())
            ConfigStore.setKey(this, keyEdt.text.toString().trim())
            ConfigStore.setSecret(this, secretEdt.text.toString().trim())
            ConfigStore.setScreenMessage(this, smsEdt.text.toString().ifBlank { ConfigStore.screenMessage(this) })
            ConfigStore.setAiMode(this, modeEdt.text.toString().ifBlank { ConfigStore.aiMode(this) })
            dialerStatus.text = "Saved"
        }

        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addView(dialerStatus)
            addView(dialerBtn)
            addView(gap(8))
            addView(grantBtn)
            addView(gap(16))
            addView(urlEdt); addView(gap(10))
            addView(keyEdt); addView(gap(10))
            addView(secretEdt); addView(gap(10))
            addView(smsEdt); addView(gap(10))
            addView(modeEdt); addView(gap(16))
            addView(saveBtn)
        }

        setContentView(ScrollView(this).apply { addView(col) })
    }

    override fun onResume() {
        super.onResume()
        refreshDialerStatus()
    }

    private fun refreshDialerStatus() {
        val tm = getSystemService(TELECOM_SERVICE) as TelecomManager
        val isDefault = tm.defaultDialerApplication == packageName
        dialerStatus.text = if (isDefault)
            "Default dialer: active — incoming calls will be handled by Zenith"
        else "Zenith is NOT the default dialer yet"
        dialerStatus.setTextColor(if (isDefault) Color.parseColor("#2EBD85") else Color.parseColor("#E5484D"))
    }

    private fun makeDefaultDialer() {
        val tm = getSystemService(TELECOM_SERVICE) as TelecomManager
        val i = Intent(TelecomManager.ACTION_CHANGE_DEFAULT_DIALER)
            .putExtra(TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, packageName)
        startActivity(i)
    }

    private fun requestPermissions() {
        val needed = listOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.POST_NOTIFICATIONS,
        ).filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (needed.isNotEmpty()) {
            requestPermissions(needed.toTypedArray(), 1000)
        }
    }

    private fun field(label: String, value: String): EditText =
        EditText(this).apply {
            hint = label
            setText(value)
            setSingleLine(true)
        }

    private fun gap(h: Int): View =
        View(this).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, h) }
}