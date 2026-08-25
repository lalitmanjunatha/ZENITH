package com.zenith.phone

import android.content.Context
import android.content.SharedPreferences

/**
 * Central config for LiveKit and per-call behavior.
 *
 * Defaults mirror the desktop Zenith .env so the app works out of the box
 * for a single LiveKit Cloud project. Users can override at runtime.
 */
object ConfigStore {

    const val PREF_NAME = "zenith_phone"
    const val KEY_URL = "lk_url"
    const val KEY_KEY = "lk_key"
    const val KEY_SECRET = "lk_secret"
    const val KEY_AI_MODE = "ai_mode"         // auto | ask | off
    const val KEY_SCREEN_MSG = "screen_msg"   // decline-with-SMS default text

    // Defaults mirror .env
    const val DEFAULT_URL = "wss://nova-iezs0u48.livekit.cloud"
    const val DEFAULT_KEY = "APIdTAS9xXXKpUB"
    const val DEFAULT_SECRET = "biut0M8OLG7v1JYh6vqB2y2YDtmSFHpXWfgTi6dsDgF"

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    fun url(ctx: Context): String =
        prefs(ctx).getString(KEY_URL, null).orEmpty().let {
            if (it.isEmpty()) DEFAULT_URL else it
        }

    fun apiKey(ctx: Context): String =
        prefs(ctx).getString(KEY_KEY, null).orEmpty().let {
            if (it.isEmpty()) DEFAULT_KEY else it
        }

    fun apiSecret(ctx: Context): String =
        prefs(ctx).getString(KEY_SECRET, null).orEmpty().let {
            if (it.isEmpty()) DEFAULT_SECRET else it
        }

    fun aiMode(ctx: Context): String =
        prefs(ctx).getString(KEY_AI_MODE, "auto") ?: "auto"

    fun screenMessage(ctx: Context): String =
        prefs(ctx).getString(KEY_SCREEN_MSG, "Can't talk right now. I'll call you back.")!!

    fun setUrl(ctx: Context, v: String) = prefs(ctx).edit().putString(KEY_URL, v).apply()
    fun setKey(ctx: Context, v: String) = prefs(ctx).edit().putString(KEY_KEY, v).apply()
    fun setSecret(ctx: Context, v: String) = prefs(ctx).edit().putString(KEY_SECRET, v).apply()
    fun setAiMode(ctx: Context, v: String) = prefs(ctx).edit().putString(KEY_AI_MODE, v).apply()
    fun setScreenMessage(ctx: Context, v: String) = prefs(ctx).edit().putString(KEY_SCREEN_MSG, v).apply()

    fun httpOrigin(url: String): String = url
        .replaceFirst("wss://", "https://")
        .replaceFirst("ws://", "http://")