package com.netquota.agent.measure

import android.net.TrafficStats
import com.netquota.agent.data.CollectionResult
import com.netquota.agent.data.InterfaceSample
import com.netquota.agent.data.MeasurementQuality
import com.netquota.agent.data.MeasurementScope

/**
 * Reads Android's built-in [TrafficStats].
 *
 * TrafficStats has no stable per-interface API below API 29's
 * NetworkStatsManager, which would require extra privileges and can expose
 * subscriber identifiers. We therefore use the documented device-wide totals:
 *  - [TrafficStats.getTotalRxBytes] / [TrafficStats.getTotalTxBytes] return the
 *    device's cumulative byte counts since boot, across all interfaces
 *    (mobile + Wi-Fi + others). No permission is required.
 *
 * Limitations (reported honestly to the server):
 *  - Counters are since-boot, so they reset on every device reboot. The server
 *    treats a decrease as a counter reset and re-baselines instead of
 *    double-counting.
 *  - Some traffic (e.g. certain tunnelled or hotspot traffic depending on the
 *    ROM) may not be attributed; scope is reported as android_total and quality
 *    as exact for the total counters the framework exposes.
 *  - TrafficStats cannot attribute bytes per app without per-UID collection.
 *    We only report device totals.
 */
object AndroidTrafficCollector {

    /** Sentinel returned by TrafficStats when a counter is unavailable. */
    private const val UNSUPPORTED = -1L

    fun collect(): CollectionResult {
        val rx = TrafficStats.getTotalRxBytes()
        val tx = TrafficStats.getTotalTxBytes()
        val mobileRx = TrafficStats.getMobileRxBytes()
        val mobileTx = TrafficStats.getMobileTxBytes()

        if (rx == UNSUPPORTED || tx == UNSUPPORTED) {
            return CollectionResult(
                interfaces = emptyList(),
                scope = MeasurementScope.UNSUPPORTED,
                quality = MeasurementQuality.UNKNOWN,
                notes = listOf("TrafficStats returned unsupported counters on this device."),
            )
        }

        val interfaces = buildList {
            add(InterfaceSample(name = "total", rxTotal = rx, txTotal = tx))
            if (mobileRx != UNSUPPORTED && mobileTx != UNSUPPORTED) {
                // Reported for visibility; the server's primary policy counts
                // "total" only to avoid double counting mobile traffic.
                add(InterfaceSample(name = "mobile", rxTotal = mobileRx, txTotal = mobileTx))
            }
        }

        return CollectionResult(
            interfaces = interfaces,
            scope = MeasurementScope.ANDROID_TOTAL,
            quality = MeasurementQuality.EXACT,
            notes = listOf(
                "Counters are device-wide totals since boot and reset on reboot.",
                "Mobile bytes are included in the total counter.",
            ),
        )
    }
}