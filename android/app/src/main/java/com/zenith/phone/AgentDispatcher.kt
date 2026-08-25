package com.zenith.phone

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Tells the LiveKit cloud project to dispatch the desktop Zenith worker into
 * a per-call room. Uses the LiveKit admin token minted locally.
 */
object AgentDispatcher {

    suspend fun dispatchAgent(
        ctx: Context,
        room: String,
        caller: String?,
        direction: String,
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val url = ConfigStore.url(ctx)
            val apiKey = ConfigStore.apiKey(ctx)
            val apiSecret = ConfigStore.apiSecret(ctx)
            val token = TokenMinter.adminToken(apiKey, apiSecret, room)

            val metadata = JSONObject()
                .put("zenith_call", true)
                .put("caller", caller ?: "")
                .put("direction", direction)

            val body = JSONObject()
                .put("room", room)
                .put("agent_name", "")
                .put("metadata", metadata.toString())

            val endpoint = ConfigStore.httpOrigin(url) +
                "/twirp/livekit.AgentDispatchService/CreateAgentDispatch"

            val conn = URL(endpoint).openConnection() as HttpURLConnection
            try {
                conn.requestMethod = "POST"
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 10_000
                conn.readTimeout = 10_000
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }

                val code = conn.responseCode
                val text = if (code in 200..299) {
                    conn.inputStream.bufferedReader().use { it.readText() }
                } else {
                    conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                }
                if (code in 200..299) {
                    val id = try { JSONObject(text).optString("dispatch_id", "") } catch (_: Exception) { "" }
                    Result.success(id)
                } else {
                    Result.failure(RuntimeException("Dispatch failed ($code): $text"))
                }
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}