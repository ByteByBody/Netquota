import Foundation

/// What a counter measures. Mirrors the server's MeasurementScope values.
enum MeasurementScope: String, Codable {
    /// Whole-device traffic. Not available to third-party apps on iOS.
    case deviceTotal = "device_total"
    /// Only this app's own URLSession traffic.
    case appOnly = "app_only"
    case partial
    case unsupported
}

enum MeasurementQuality: String, Codable {
    case exact
    case estimated
    case partial
    case unknown
}

struct InterfaceSample: Codable {
    let name: String
    let bytesReceivedTotal: Int64
    let bytesSentTotal: Int64
    let reset: Bool
}

struct CollectionResult {
    let interfaces: [InterfaceSample]
    let scope: MeasurementScope
    let quality: MeasurementQuality
    let notes: [String]
}

struct AgentState {
    var deviceId: String?
    var credential: String?
    var sequence: Int = 0
    var serverURL: String?
    var deviceName: String?
    var consented: Bool = false
    var monitoringEnabled: Bool = false
    var lastReportAt: Date?
    var lastReportOK: Bool = false
    var lastError: String?

    func nextSequence() -> AgentState {
        var copy = self
        copy.sequence += 1
        return copy
    }
}

struct EnrollResponse: Decodable {
    let device_id: String
    let credential: String
    let heartbeat_interval_seconds: Int
    let reporting_interval_seconds: Int
}

struct UsageReportResponse: Decodable {
    let accepted: Bool
    let duplicate: Bool?
    let acknowledged_sequence: Int?
}

enum PlatformCapability {
    /// iOS third-party apps cannot read whole-device byte counters with public
    /// APIs. Network Extension (packet tunnel / NEFilter) can observe traffic
    /// but requires the VPN entitlement and presents as a VPN, which this
    /// project deliberately does not use. So device-wide totals are unavailable.
    static let wholeDeviceUsageAvailable = false

    static let explanation = """
    iOS does not give ordinary apps access to whole-device network counters. \
    This agent therefore reports only its own URLSession traffic and clearly \
    marks it as app-only and partial. iPhone usage figures are NOT comparable \
    to Windows, Linux, or Android device-wide totals.
    """
}