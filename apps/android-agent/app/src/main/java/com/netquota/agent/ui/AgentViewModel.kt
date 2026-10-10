package com.netquota.agent.ui

import android.content.Context
import com.netquota.agent.data.AgentState
import com.netquota.agent.data.SecureStore
import com.netquota.agent.measure.AndroidTrafficCollector
import com.netquota.agent.net.ApiClient
import com.netquota.agent.work.WorkScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Drives the UI and coordinates with the encrypted store and the worker.
 * All network calls run off the main thread.
 */
class AgentViewModel(private val context: Context) {

    private val store = SecureStore(context)
    private val scope = CoroutineScope(Dispatchers.Main)
    private val _state = MutableStateFlow(store.load())
    val state: StateFlow<AgentState> = _state

    private fun persist(next: AgentState) {
        store.save(next)
        _state.value = next
    }

    fun grantConsent() {
        persist(_state.value.copy(consented = true))
    }

    fun setMonitoring(enabled: Boolean) {
        persist(_state.value.copy(monitoringEnabled = enabled))
        WorkScheduler.ensureScheduled(context)
    }

    fun enroll(server: String, code: String, name: String, onError: (String) -> Unit) {
        scope.launch {
            try {
                val collection = AndroidTrafficCollector.collect()
                val response = withContext(Dispatchers.IO) {
                    ApiClient().enroll(
                        server.trimEnd('/'),
                        code,
                        name,
                        collection.scope.wire,
                        collection.quality.wire,
                    )
                }
                persist(
                    _state.value.copy(
                        serverUrl = server.trimEnd('/'),
                        deviceId = response.deviceId,
                        credential = response.credential,
                        deviceName = name,
                        sequence = 0,
                        monitoringEnabled = true,
                    ),
                )
                WorkScheduler.ensureScheduled(context)
                onError("")
            } catch (exc: Exception) {
                onError(exc.message ?: "Enrollment failed")
            }
        }
    }

    fun reportNow() {
        scope.launch {
            val current = _state.value
            val server = current.serverUrl ?: return@launch
            try {
                val collection = AndroidTrafficCollector.collect()
                val next = current.nextSequence()
                withContext(Dispatchers.IO) {
                    ApiClient().reportUsage(server, next, collection)
                }
                persist(
                    next.copy(
                        lastReportAt = System.currentTimeMillis(),
                        lastReportOk = true,
                        lastError = null,
                    ),
                )
            } catch (exc: Exception) {
                persist(
                    current.copy(
                        lastReportOk = false,
                        lastError = exc.message ?: "report failed",
                    ),
                )
            }
        }
    }

    fun revokeLocal() {
        store.clearCredentials()
        persist(store.load())
        WorkScheduler.ensureScheduled(context)
    }
}