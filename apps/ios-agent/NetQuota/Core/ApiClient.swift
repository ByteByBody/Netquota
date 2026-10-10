import Foundation

/// Authenticated client for the NetQuota agent API (protocol schema_version 1).
/// Uses URLSession; captures task metrics so app-only byte counts stay accurate.
final class ApiClient {
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.waitsForConnectivity = true
        config.timeoutIntervalForRequest = 20
        session = URLSession(configuration: config)
    }

    struct ApiError: LocalizedError {
        let status: Int
        let message: String
        var errorDescription: String? { "\(status): \(message)" }
    }

    func enroll(server: String, code: String, name: String, collection: CollectionResult) async throws -> EnrollResponse {
        let body: [String: Any] = [
            "enrollment_code": code,
            "name": name,
            "platform": "ios",
            "agent_version": "0.1.0",
            "measurement_scope": collection.scope.rawValue,
            "measurement_quality": collection.quality.rawValue,
            "capabilities": ["urlsession_metrics": true],
        ]
        let data = try await post("\(server)/api/v1/enroll", body: body)
        return try JSONDecoder().decode(EnrollResponse.self, from: data)
    }

    func reportUsage(server: String, state: AgentState, collection: CollectionResult) async throws -> UsageReportResponse {
        let interfaces = collection.interfaces.map { iface -> [String: Any] in
            [
                "name": iface.name,
                "bytes_received_total": iface.bytesReceivedTotal,
                "bytes_sent_total": iface.bytesSentTotal,
                "reset": iface.reset,
            ]
        }
        let body: [String: Any] = [
            "schema_version": 1,
            "sequence": state.sequence,
            "observed_at": ISO8601DateFormatter().string(from: Date()),
            "measurement_scope": collection.scope.rawValue,
            "measurement_quality": collection.quality.rawValue,
            "interfaces": interfaces,
        ]
        let data = try await post("\(server)/api/v1/agent/usage", body: body, state: state)
        return try JSONDecoder().decode(UsageReportResponse.self, from: data)
    }

    private func post(_ url: String, body: [String: Any], state: AgentState? = nil) async throws -> Data {
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let state, let deviceId = state.deviceId, let credential = state.credential {
            request.setValue(deviceId, forHTTPHeaderField: "X-Device-Id")
            request.setValue(credential, forHTTPHeaderField: "X-Device-Credential")
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw ApiError(status: 0, message: "no response")
        }
        if http.statusCode >= 400 {
            throw ApiError(status: http.statusCode, message: String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }
}