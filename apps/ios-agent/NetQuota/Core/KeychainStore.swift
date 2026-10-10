import Foundation
import Security

/// Keychain-backed storage for the device credential and agent state.
/// Credentials never touch UserDefaults or the filesystem in plaintext.
final class KeychainStore {
    static let shared = KeychainStore()

    private let service = "com.netquota.agent"
    private let credentialAccount = "device-credential"
    private let stateAccount = "agent-state"

    func saveCredential(_ credential: String, deviceId: String) {
        let payload = "\(deviceId)|\(credential)"
        set(payload, account: credentialAccount)
    }

    func loadCredential() -> (deviceId: String, credential: String)? {
        guard let value = get(account: credentialAccount) else { return nil }
        let parts = value.split(separator: "|", maxSplits: 1).map(String.init)
        guard parts.count == 2 else { return nil }
        return (parts[0], parts[1])
    }

    func deleteCredential() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: credentialAccount,
        ]
        SecItemDelete(query as CFDictionary)
    }

    func saveState(_ state: AgentState) {
        guard let data = try? JSONEncoder().encode(StateDTO(state)),
              let text = String(data: data, encoding: .utf8) else { return }
        set(text, account: stateAccount)
    }

    func loadState() -> AgentState {
        guard let text = get(account: stateAccount),
              let data = text.data(using: .utf8),
              let dto = try? JSONDecoder().decode(StateDTO.self, from: data) else {
            return AgentState()
        }
        return dto.toState()
    }

    // MARK: - Keychain primitives

    private func set(_ value: String, account: String) {
        let data = value.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(attributes as CFDictionary, nil)
    }

    private func get(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private struct StateDTO: Codable {
        var deviceId: String?
        var sequence: Int
        var serverURL: String?
        var deviceName: String?
        var consented: Bool
        var monitoringEnabled: Bool
        var lastReportAt: Date?
        var lastReportOK: Bool
        var lastError: String?

        init(_ s: AgentState) {
            deviceId = s.deviceId
            sequence = s.sequence
            serverURL = s.serverURL
            deviceName = s.deviceName
            consented = s.consented
            monitoringEnabled = s.monitoringEnabled
            lastReportAt = s.lastReportAt
            lastReportOK = s.lastReportOK
            lastError = s.lastError
        }

        func toState() -> AgentState {
            var s = AgentState()
            s.deviceId = deviceId
            s.sequence = sequence
            s.serverURL = serverURL
            s.deviceName = deviceName
            s.consented = consented
            s.monitoringEnabled = monitoringEnabled
            s.lastReportAt = lastReportAt
            s.lastReportOK = lastReportOK
            s.lastError = lastError
            return s
        }
    }
}