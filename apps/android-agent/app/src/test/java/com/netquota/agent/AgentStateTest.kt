package com.netquota.agent

import com.netquota.agent.data.AgentState
import com.netquota.agent.data.MeasurementQuality
import com.netquota.agent.data.MeasurementScope
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Unit tests for the platform-independent agent logic. */
class AgentStateTest {

    @Test
    fun sequenceIsMonotonic() {
        var state = AgentState(deviceId = "d", credential = "c")
        repeat(5) { state = state.nextSequence() }
        assertEquals(5, state.sequence)
    }

    @Test
    fun wireValuesMatchServerEnum() {
        assertEquals("android_total", MeasurementScope.ANDROID_TOTAL.wire)
        assertEquals("unsupported", MeasurementScope.UNSUPPORTED.wire)
        assertEquals("exact", MeasurementQuality.EXACT.wire)
        assertEquals("partial", MeasurementQuality.PARTIAL.wire)
    }

    @Test
    fun monitoringDefaultsOffUntilConsent() {
        val state = AgentState()
        assertFalse(state.consented)
        assertFalse(state.monitoringEnabled)
        assertEquals(0, state.sequence)
    }

    @Test
    fun copyPreservesIdentity() {
        val state = AgentState(deviceId = "abc", credential = "secret", sequence = 3)
        val next = state.nextSequence()
        assertEquals("abc", next.deviceId)
        assertEquals("secret", next.credential)
        assertTrue(next.sequence > state.sequence)
    }
}