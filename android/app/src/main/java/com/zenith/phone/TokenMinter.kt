package com.zenith.phone

import android.util.Base64
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Minimal LiveKit access-token (JWT/HS256) minting so the app can join rooms
 * and act as a LiveKit admin (create agent dispatches) without a backend.
 */
object TokenMinter {

    private fun b64url(data: ByteArray): String =
        Base64.encodeToString(data, Base64.NO_WRAP or Base64.URL_SAFE)

    private fun b64url(s: String): String = b64url(s.toByteArray(Charsets.UTF_8))

    private val hex = charArrayOf('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f')
    private fun randomHex(n: Int): String {
        val r = java.security.SecureRandom()
        val sb = StringBuilder(n * 2)
        repeat(n) {
            sb.append(hex[r.nextInt(16)])
        }
        return sb.toString()
    }

    private fun hmac(input: String, secret: String): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        return mac.doFinal(input.toByteArray(Charsets.UTF_8))
    }

    /** Admin token: room join + room admin (enables agent dispatch creation). */
    fun adminToken(apiKey: String, apiSecret: String, room: String, ttlSeconds: Long = 3600): String {
        val header = """{"alg":"HS256","typ":"JWT"}"""
        val now = System.currentTimeMillis() / 1000
        val payload = StringBuilder()
        payload.append('{')
        payload.append("\"iss\":\"").append(apiKey).append("\",")
        payload.append("\"sub\":\"").append(apiKey).append("\",")
        payload.append("\"nbf\":").append(now - 10).append(',')
        payload.append("\"iat\":").append(now - 10).append(',')
        payload.append("\"exp\":").append(now + ttlSeconds).append(',')
        payload.append("\"jti\":\"").append(randomHex(9)).append("\",")
        payload.append("\"name\":\"").append(room).append("\",")
        payload.append("\"vid\":\"").append(randomHex(9)).append("\",")

        val video = "{" +
            "\"room\":\"" + room + "\"," +
            "\"roomJoin\":true," +
            "\"roomAdmin\":true," +
            "\"roomList\":true," +
            "\"canPublish\":true," +
            "\"canSubscribe\":true," +
            "\"canPublishData\":true," +
            "\"canUpdateOwnMetadata\":true" +
            "}"
        payload.append("\"video\":").append(video).append(",")
        payload.append("\"agentAdmin\":true,")
        payload.append("\"ingressAdmin\":true,")
        payload.append("\"pin\":\"\"")
        payload.append('}')
        return sign(header, payload.toString(), apiSecret)
    }

    /** Self join to a room as the phone participant (operator of the live call). */
    fun joinToken(apiKey: String, apiSecret: String, room: String, identity: String, ttlSeconds: Long = 3600): String {
        val header = """{"alg":"HS256","typ":"JWT"}"""
        val now = System.currentTimeMillis() / 1000
        val payload = StringBuilder()
        payload.append('{')
        payload.append("\"iss\":\"").append(apiKey).append("\",")
        payload.append("\"sub\":\"").append(apiKey).append("\",")
        payload.append("\"nbf\":").append(now - 10).append(',')
        payload.append("\"iat\":").append(now - 10).append(',')
        payload.append("\"exp\":").append(now + ttlSeconds).append(',')
        payload.append("\"jti\":\"").append(randomHex(9)).append("\",")
        payload.append("\"name\":\"").append(room).append("\",")
        payload.append("\"identity\":\"").append(identity).append("\",")
        payload.append("\"video\":{\"room\":\"").append(room)
            .append("\",\"roomJoin\":true,\"canPublish\":true,\"canSubscribe\":true,\"canPublishData\":true}")
        payload.append('}')
        return sign(header, payload, apiSecret)
    }

    internal fun sign(header: String, payload: String, secret: String): String {
        val signingInput = b64url(header) + "." + b64url(payload)
        val sig = b64url(hmac(signingInput, secret))
        return signingInput + "." + sig
    }
}