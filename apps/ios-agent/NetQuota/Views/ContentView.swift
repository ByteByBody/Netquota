import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: AgentViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    if !model.state.consented {
                        ConsentView(onConsent: model.grantConsent)
                    } else if model.state.deviceId == nil {
                        EnrollView()
                    } else {
                        StatusView()
                    }
                }
                .padding()
                .frame(maxWidth: 560, alignment: .leading)
            }
            .navigationTitle("NetQuota")
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("NetQuota")
                .font(.largeTitle.bold())
            Text("Reports this iPhone's measurable data usage to your household server. Monitoring is visible and can be stopped at any time.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}

private struct ConsentView: View {
    let onConsent: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Before you enroll").font(.headline)

            Group {
                Text("What is collected").font(.subheadline.bold())
                Text("• Data sent and received by this app's network requests.\n• Device name and the time of the last report.")
                Text("What is NOT collected").font(.subheadline.bold())
                Text("• No browsing history, websites, or packet contents.\n• No location, contacts, or passwords.")
                Text("What iOS cannot measure").font(.subheadline.bold())
                Text(PlatformCapability.explanation)
            }
            .font(.subheadline)

            Button("I understand and consent", action: onConsent)
                .buttonStyle(.borderedProminent)
                .frame(maxWidth: .infinity, alignment: .trailing)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct EnrollView: View {
    @EnvironmentObject private var model: AgentViewModel
    @State private var server = "https://netquota.local"
    @State private var code = ""
    @State private var name = "My iPhone"
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Enroll this iPhone").font(.headline)
            TextField("Server URL", text: $server)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)
            TextField("Enrollment code", text: $code)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)
            TextField("Device name", text: $name)
                .textFieldStyle(.roundedBorder)
            if let error {
                Text(error).foregroundStyle(.red).font(.footnote)
            }
            Button {
                Task {
                    busy = true
                    error = nil
                    do {
                        try await model.enroll(server: server, code: code, name: name)
                    } catch {
                        self.error = error.localizedDescription
                    }
                    busy = false
                }
            } label: {
                Text(busy ? "Enrolling…" : "Enroll")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(busy || code.isEmpty)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct StatusView: View {
    @EnvironmentObject private var model: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Circle()
                    .fill(model.state.monitoringEnabled ? .green : .orange)
                    .frame(width: 10, height: 10)
                Text(model.state.monitoringEnabled ? "Monitoring is on" : "Monitoring is paused")
                    .font(.headline)
            }
            LabeledContent("Device", value: model.state.deviceName ?? model.state.deviceId ?? "—")
            LabeledContent("Sequence", value: "\(model.state.sequence)")
            LabeledContent("Last report", value: lastReportText)
            LabeledContent("Result", value: model.state.lastReportOK ? "ok" : "waiting")
            if let err = model.state.lastError {
                Text("Last error: \(err)").foregroundStyle(.red).font(.footnote)
            }

            HStack(spacing: 12) {
                Button(model.state.monitoringEnabled ? "Pause" : "Resume") {
                    model.setMonitoring(!model.state.monitoringEnabled)
                }
                .buttonStyle(.borderedProminent)
                Button("Report now") {
                    Task { await model.reportNow() }
                }
                .buttonStyle(.bordered)
            }

            Button("Forget this device", role: .destructive) {
                model.forgetDevice()
            }

            Text("Stopping monitoring here prevents further reports. Ask the household admin to revoke the device on the server to invalidate its credential.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var lastReportText: String {
        guard let date = model.state.lastReportAt else { return "not yet" }
        return date.formatted(date: .abbreviated, time: .shortened)
    }
}

#Preview {
    ContentView().environmentObject(AgentViewModel())
}