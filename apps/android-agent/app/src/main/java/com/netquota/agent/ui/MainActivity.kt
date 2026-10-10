package com.netquota.agent.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import com.netquota.agent.work.WorkScheduler
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val model = AgentViewModel(applicationContext)
        setContent {
            MaterialTheme {
                NetQuotaApp(model)
            }
        }
    }
}

@Composable
private fun NetQuotaApp(model: AgentViewModel) {
    val state by model.state.collectAsState()
    Surface(Modifier.fillMaxSize()) {
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("NetQuota", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(
                "Reports this phone's data usage to your household server. Monitoring is visible and can be stopped at any time.",
                style = MaterialTheme.typography.bodyMedium,
            )

            when {
                !state.consented -> ConsentCard(onConsent = model::grantConsent)
                state.deviceId == null -> EnrollCard(model)
                else -> StatusCard(model)
            }
        }
    }
}

@Composable
private fun ConsentCard(onConsent: () -> Unit) {
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Before you enroll", fontWeight = FontWeight.SemiBold)
            Text("What is collected:", fontWeight = FontWeight.Medium)
            Text("• Total bytes received and sent by this device (since boot), from Android's TrafficStats.\n• Device name, Android version info, and the time of the last report.")
            Text("What is NOT collected:", fontWeight = FontWeight.Medium)
            Text("• No browsing history, websites, packet contents, or app usage.\n• No location. No contacts. No passwords.")
            Text(
                "Android controls background timing: reports are batched and may be delayed, and counters reset when the phone reboots.",
                style = MaterialTheme.typography.bodySmall,
            )
            Button(onClick = onConsent, modifier = Modifier.align(Alignment.End)) {
                Text("I understand and consent")
            }
        }
    }
}

@Composable
private fun EnrollCard(model: AgentViewModel) {
    var server by remember { mutableStateOf("http://10.0.0.10:8000") }
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf(android.os.Build.MODEL) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Enroll this phone", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(server, { server = it }, label = { Text("Server URL") }, Modifier.fillMaxWidth())
            OutlinedTextField(code, { code = it }, label = { Text("Enrollment code") }, Modifier.fillMaxWidth())
            OutlinedTextField(name, { name = it }, label = { Text("Device name") }, Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                enabled = !busy && code.isNotBlank(),
                onClick = {
                    busy = true
                    error = null
                    model.enroll(server, code, name) { err -> error = err; busy = false }
                },
                modifier = Modifier.align(Alignment.End),
            ) { Text(if (busy) "Enrolling…" else "Enroll") }
        }
    }
}

@Composable
private fun StatusCard(model: AgentViewModel) {
    val state by model.state.collectAsState()
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (state.monitoringEnabled) "Monitoring is on" else "Monitoring is paused", fontWeight = FontWeight.SemiBold)
            Text("Device: ${state.deviceName ?: state.deviceId}")
            Text("Sequence: ${state.sequence}")
            Text("Last report: ${state.lastReportAt?.let { java.text.DateFormat.getDateTimeInstance().format(it) } ?: "not yet"}")
            Text("Result: ${if (state.lastReportOk) "ok" else "waiting"}")
            state.lastError?.let { Text("Last error: $it", color = MaterialTheme.colorScheme.error) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { model.setMonitoring(!state.monitoringEnabled) }) {
                    Text(if (state.monitoringEnabled) "Pause" else "Resume")
                }
                OutlinedButton(onClick = model::reportNow) { Text("Report now") }
            }
            TextButton(onClick = model::revokeLocal, modifier = Modifier.align(Alignment.Start)) {
                Text("Forget this device")
            }
            Text(
                "This screen is always available. Stopping monitoring here prevents further reports; ask the household admin to revoke the device on the server to invalidate its credential.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}