import SwiftUI

@main
struct NetQuotaApp: App {
    @StateObject private var model = AgentViewModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .task { model.load() }
                .onChange(of: scenePhase) { phase in
                    if phase == .background {
                        BackgroundScheduler.shared.scheduleRefresh()
                    }
                }
        }
    }
}