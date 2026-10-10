package com.netquota.agent

import android.app.Application
import com.netquota.agent.work.WorkScheduler

/**
 * Application entrypoint. Schedules the periodic usage worker only when the
 * user has enrolled and consented — the agent never reports before consent.
 */
class NetQuotaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        WorkScheduler.ensureScheduled(this)
    }
}