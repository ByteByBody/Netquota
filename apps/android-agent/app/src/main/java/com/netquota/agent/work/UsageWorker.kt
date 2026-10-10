package com.netquota.agent.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.netquota.agent.data.SecureStore
import com.netquota.agent.measure.AndroidTrafficCollector
import com.netquota.agent.net.ApiClient

/**
 * Periodic worker: collects TrafficStats totals, reports them with the next
 * monotonic sequence number, and persists state. On success and failure the
 * outcome is recorded so the UI can show the last report time and any error.
 */
class UsageWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val store = SecureStore(applicationContext)
        val state = store.load()
        val serverUrl = state.serverUrl
        if (!state.consented || !state.monitoringEnabled || state.deviceId == null || serverUrl == null) {
            return Result.success()
        }

        val collection = AndroidTrafficCollector.collect()
        val client = ApiClient()
        // Reserve the next sequence; if the call fails we roll it back so the
        // retry reuses the same number (server-side idempotency makes it safe).
        val next = state.nextSequence()
        return try {
            val result = client.reportUsage(serverUrl, next, collection)
            store.save(
                next.copy(
                    lastReportAt = System.currentTimeMillis(),
                    lastReportOk = true,
                    lastError = null,
                ),
            )
            // A duplicate is still a success.
            if (result.optBoolean("accepted", true)) Result.success() else Result.retry()
        } catch (exc: Exception) {
            store.save(
                state.copy(
                    lastReportAt = state.lastReportAt,
                    lastReportOk = false,
                    lastError = exc.message ?: "report failed",
                ),
            )
            Result.retry()
        }
    }
}