import XCTest
@testable import NetQuota

final class AgentStateTests: XCTestCase {

    func testSequenceIsMonotonic() {
        var state = AgentState()
        for _ in 0..<4 { state = state.nextSequence() }
        XCTAssertEqual(state.sequence, 4)
    }

    func testNextSequencePreservesIdentity() {
        var state = AgentState()
        state.deviceId = "abc"
        state.credential = "secret"
        let next = state.nextSequence()
        XCTAssertEqual(next.deviceId, "abc")
        XCTAssertEqual(next.credential, "secret")
        XCTAssertEqual(next.sequence, 1)
    }

    func testMonitoringDefaultsOffUntilConsent() {
        let state = AgentState()
        XCTAssertFalse(state.consented)
        XCTAssertFalse(state.monitoringEnabled)
    }

    func testDeviceWideMeasurementIsUnavailable() {
        // This assertion documents a deliberate product decision: iPhone
        // reports app-only usage because iOS exposes no device-wide counter.
        XCTAssertFalse(PlatformCapability.wholeDeviceUsageAvailable)
    }

    func testCollectorReportsAppOnlyPartial() {
        let result = MeasurementCollector.shared.collect()
        XCTAssertEqual(result.scope, .appOnly)
        XCTAssertEqual(result.quality, .partial)
        XCTAssertEqual(result.interfaces.first?.name, "urlsession")
    }

    func testWireValuesMatchServerProtocol() {
        XCTAssertEqual(MeasurementScope.appOnly.rawValue, "app_only")
        XCTAssertEqual(MeasurementScope.deviceTotal.rawValue, "device_total")
        XCTAssertEqual(MeasurementQuality.partial.rawValue, "partial")
        XCTAssertEqual(MeasurementQuality.exact.rawValue, "exact")
    }
}