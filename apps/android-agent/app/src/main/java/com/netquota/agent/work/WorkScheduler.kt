package com.netquota.agent.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.netquota.agent.data.SecureStore
import java.util.concurrent.TimeUnit

/**
 * Schedules the periodic reporting worker. Android does not guarantee exact
 * execution times; WorkManager runs when constraints are met and the system
 * allows. This is documented in the UI rather than promising real-time reports.
 */
object WorkScheduler {
    const val WORK_NAME = "netquota-usage-report"

    fun ensureScheduled(context: Context) {
        val state = SecureStore(context).load()
        if (!state.consented || !state.monitoringEnabled || state.deviceId == null) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            return
        }
        schedule(context, intervalMinutes = 15)
    }

    fun schedule(context: Context, intervalMinutes: Long = 15) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = PeriodicWorkRequestBuilder<UsageWorker>(
            intervalMinutes.coerceAtLeast(15),
            TimeUnit.MINUTES,
        )
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }
}