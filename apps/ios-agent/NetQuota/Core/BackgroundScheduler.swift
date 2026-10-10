import Foundation
import BackgroundTasks

/// Registers and schedules background refresh tasks. iOS decides when (and
/// whether) these run — typically opportunistically, often on charge or when
/// the app is used. We do not promise fixed intervals.
final class BackgroundScheduler {
    static let shared = BackgroundScheduler()
    static let refreshIdentifier = "com.netquota.agent.refresh"

    func register() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.refreshIdentifier,
            using: nil,
        ) { task in
            self.handle(task: task as! BGAppRefreshTask)
        }
    }

    func scheduleRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: Self.refreshIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }

    private func handle(task: BGAppRefreshTask) {
        scheduleRefresh() // chain the next one
        let operation = Task {
            let model = await AgentViewModel()
            await model.reportNow()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = { operation.cancel() }
    }
}