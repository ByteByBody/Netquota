import Foundation
import SwiftUI

/// Coordinates UI, Keychain state, and API calls. All UI state changes happen
/// on the main actor.
@MainActor
final class AgentViewModel: ObservableObject {
    @Published var state = AgentState()

    private let keychain = KeychainStore.shared
    private let api = ApiClient()

    func load() {
        let stored = keychain.loadState()
        var merged = stored
        if let credential = keychain.loadCredential() {
            merged.deviceId = credential.deviceId
            merged.credential = credential.credential
        }
        state = merged
    }

    func persist(_ next: AgentState) {
        state = next
        keychain.saveState(next)
    }

    func grantConsent() {
        persist(toggle(state, consented: true))
    }

    func setMonitoring(_ enabled: Bool) {
        persist(toggle(state, monitoringEnabled: enabled))
        if enabled { BackgroundScheduler.shared.scheduleRefresh() }
    }

    func enroll(server: String, code: String, name: String) async throws {
        let collection = MeasurementCollector.shared.collect()
        let response = try await api.enroll(
            server: server.trimmingCharacters(in: CharacterSet(charactersIn: "/")),
            code: code,
            name: name,
            collection: collection,
        )
        keychain.saveCredential(response.credential, deviceId: response.device_id)
        var next = state
        next.serverURL = server
        next.deviceId = response.device_id
        next.credential = response.credential
        next.deviceName = name
        next.sequence = 0
        next.monitoringEnabled = true
        persist(next)
        BackgroundScheduler.shared.scheduleRefresh()
    }

    func reportNow() async {
        guard let server = state.serverURL, state.deviceId != nil else { return }
        let collection = MeasurementCollector.shared.collect()
        let next = state.nextSequence()
        do {
            _ = try await api.reportUsage(server: server, state: next, collection: collection)
            var updated = next
            updated.lastReportAt = Date()
            updated.lastReportOK = true
            updated.lastError = nil
            persist(updated)
        } catch {
            var updated = state
            updated.lastReportOK = false
            updated.lastError = error.localizedDescription
            persist(updated)
        }
    }

    func forgetDevice() {
        keychain.deleteCredential()
        var next = state
        next.deviceId = nil
        next.credential = nil
        next.sequence = 0
        next.monitoringEnabled = false
        next.lastError = nil
        next.lastReportOK = false
        persist(next)
    }

    private func toggle(_ s: AgentState, consented: Bool? = nil, monitoringEnabled: Bool? = nil) -> AgentState {
        var next = s
        if let consented { next.consented = consented }
        if let monitoringEnabled { next.monitoringEnabled = monitoringEnabled }
        return next
    }
}