package com.netquota.agent.net

import com.netquota.agent.data.AgentState
import com.netquota.agent.data.CollectionResult
import com.netquota.agent.data.EnrollResponse
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONTokener

/**
 * Minimal authenticated HTTP client for the NetQuota agent API. Mirrors the
 * versioned protocol used by the desktop agent (schema_version = 1).
 */
class ApiClient(
    private val client: OkHttpClient = defaultClient(),
) {
    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    class ApiException(val status: Int, message: String) : IOException(message)

    fun enroll(serverUrl: String, code: String, name: String, scope: String, quality: String): EnrollResponse {
        val body = JSONObject()
            .put("enrollment_code", code)
            .put("name", name)
            .put("platform", "android")
            .put("agent_version", "0.1.0")
            .put("measurement_scope", scope)
            .put("measurement_quality", quality)
            .put("capabilities", JSONObject().put("trafficstats", true))
            .toString()
        val json = post("$serverUrl/api/v1/enroll", body, null, null)
        return EnrollResponse(
            deviceId = json.getString("device_id"),
            credential = json.getString("credential"),
            heartbeatIntervalSeconds = json.optInt("heartbeat_interval_seconds", 300),
            reportingIntervalSeconds = json.optInt("reporting_interval_seconds", 300),
        )
    }

    fun heartbeat(serverUrl: String, state: AgentState): JSONObject {
        val body = JSONObject()
            .put("schema_version", 1)
            .put("agent_version", "0.1.0")
            .put("status", if (state.monitoringEnabled) "online" else "paused")
            .put("last_sequence", state.sequence)
            .toString()
        return post("$serverUrl/api/v1/agent/heartbeat", body, state.deviceId, state.credential)
    }

    fun reportUsage(
        serverUrl: String,
        state: AgentState,
        collection: CollectionResult,
    ): JSONObject {
        val interfaces = JSONArray()
        collection.interfaces.forEach { iface ->
            interfaces.put(
                JSONObject()
                    .put("name", iface.name)
                    .put("bytes_received_total", iface.rxTotal)
                    .put("bytes_sent_total", iface.txTotal)
                    .put("reset", iface.reset),
            )
        }
        val body = JSONObject()
            .put("schema_version", 1)
            .put("sequence", state.sequence)
            .put("observed_at", Iso8601.now())
            .put("measurement_scope", collection.scope.wire)
            .put("measurement_quality", collection.quality.wire)
            .put("interfaces", interfaces)
            .toString()
        return post("$serverUrl/api/v1/agent/usage", body, state.deviceId, state.credential)
    }

    private fun post(url: String, body: String, deviceId: String?, credential: String?): JSONObject {
        val builder = Request.Builder().url(url).post(body.toRequestBody(JSON))
        if (deviceId != null && credential != null) {
            builder.header("X-Device-Id", deviceId)
            builder.header("X-Device-Credential", credential)
        }
        client.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw ApiException(response.code, text)
            }
            return if (text.isBlank()) JSONObject() else JSONObject(JSONTokener(text))
        }
    }
}

object Iso8601 {
    fun now(): String {
        val fmt = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US)
        fmt.timeZone = java.util.TimeZone.getTimeZone("UTC")
        return fmt.format(java.util.Date())
    }
}