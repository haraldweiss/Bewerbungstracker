import SwiftUI
import SwiftData

@main
struct BewerbungstrackerApp: App {
    @StateObject private var settingsViewModel = SettingsViewModel(
        modelContext: ModelContext(try! ModelContainer(for: [UserModel.self, ApplicationModel.self, EmailModel.self, NotificationModel.self]))
    )

    var body: some Scene {
        WindowGroup {
            MainTabView()
                .environmentObject(settingsViewModel)
                .preferredColorScheme(settingsViewModel.preferredColorScheme)
                .modelContainer(for: [ApplicationModel.self, EmailModel.self, NotificationModel.self])
        }
    }
}
