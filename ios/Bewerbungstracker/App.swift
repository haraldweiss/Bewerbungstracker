import SwiftUI
import SwiftData

@main
struct BewerbungstrackerApp: App {
    var body: some Scene {
        WindowGroup {
            MainTabView()
                .modelContainer(for: [ApplicationModel.self, EmailModel.self, NotificationModel.self])
        }
    }
}
