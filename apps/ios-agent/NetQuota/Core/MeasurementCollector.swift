import Foundation

/// Measures network usage that iOS actually exposes to third-party apps.
///
/// There is no public API for whole-device byte counters. `URLSession`'s
/// `URLSessionTaskMetrics` reports bytes per request the app itself makes, so
/// the honest scope is "app-only". We accumulate that into a cumulative counter
/// so it fits the same server protocol as other platforms, and label it clearly.
final class MeasurementCollector {
    static let shared = MeasurementCollector()

    private let key = "netquota.appbytecounters"
    private let lock = NSLock()

    /// Called by the API client after each request with that request's totals.
    func record(bytesReceived: Int64, bytesSent: Int64) {
        lock.lock()
        defer { lock.unlock() }
        var counters = stored()
        counters.received += max(0, bytesReceived)
        counters.sent += max(0, bytesSent)
        UserDefaults.standard.set(
            ["received": counters.received, "sent": counters.sent],
            forKey: key,
        )
    }

    private func stored() -> (received: Int64, sent: Int64) {
        guard let dict = UserDefaults.standard.dictionary(forKey: key) else {
            return (0, 0)
        }
        let received = (dict["received"] as? NSNumber)?.int64Value ?? 0
        let sent = (dict["sent"] as? NSNumber)?.int64Value ?? 0
        return (received, sent)
    }

    func collect() -> CollectionResult {
        let counters = stored()
        return CollectionResult(
            interfaces: [
                InterfaceSample(
                    name: "urlsession",
                    bytesReceivedTotal: counters.received,
                    bytesSentTotal: counters.sent,
                    reset: false,
                ),
            ],
            scope: .appOnly,
            quality: .partial,
            notes: [PlatformCapability.explanation],
        )
    }
}