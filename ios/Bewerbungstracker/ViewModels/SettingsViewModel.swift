import SwiftUI
import SwiftData

@MainActor
class SettingsViewModel: ObservableObject {
    let apiClient: APIClientProtocol
    @Published var user: UserModel?
    @Published var lastSyncTime: String = "Never"
    @Published var isSyncing: Bool = false
    @Published var showLogoutAlert: Bool = false
    @Published var isLoggedOut: Bool = false
    @Published var appearanceMode: String = "system" {
        didSet {
            UserDefaults.standard.setValue(appearanceMode, forKey: "darkModePreference")
        }
    }

    private let modelContext: ModelContext

    init(modelContext: ModelContext, apiClient: APIClientProtocol = URLSessionAPIClient()) {
        self.modelContext = modelContext
        self.apiClient = apiClient
        // Load saved appearance preference from UserDefaults
        if let saved = UserDefaults.standard.string(forKey: "darkModePreference") {
            self.appearanceMode = saved
        } else {
            self.appearanceMode = "system"
        }
        fetchUser()
        updateLastSyncTime()
    }

    func fetchUser() {
        do {
            let descriptor = FetchDescriptor<UserModel>()
            let users = try modelContext.fetch(descriptor)
            user = users.first
        } catch {
            print("Failed to fetch user: \(error)")
        }
    }

    func updateLastSyncTime() {
        if let lastSync = user?.lastSyncAt {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            lastSyncTime = formatter.localizedString(for: lastSync, relativeTo: Date())
        } else {
            lastSyncTime = "Never"
        }
    }

    func manualSync() {
        isSyncing = true
        // Simulate sync operation
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            if var currentUser = self.user {
                currentUser.lastSyncAt = Date()
                try? self.modelContext.save()
                self.fetchUser()
                self.updateLastSyncTime()
            }
            self.isSyncing = false
        }
    }

    func updateProfile(name: String, email: String) {
        if let currentUser = user {
            currentUser.name = name
            currentUser.email = email
            try? modelContext.save()
            fetchUser()
        } else {
            let newUser = UserModel(name: name, email: email)
            modelContext.insert(newUser)
            try? modelContext.save()
            fetchUser()
        }
    }

    func changePassword(oldPassword: String, newPassword: String) {
        // Placeholder for password change logic
        // In a real app, this would validate and update the password
        print("Password change requested (old: \(oldPassword), new: \(newPassword))")
    }

    func logout() {
        Task {
            do {
                try await apiClient.logout()
                // Clear user session
                if let currentUser = user {
                    modelContext.delete(currentUser)
                    try? modelContext.save()
                }
                isLoggedOut = true
            } catch {
                print("Logout error: \(error)")
                // Clear session anyway even if API call fails
                if let currentUser = user {
                    modelContext.delete(currentUser)
                    try? modelContext.save()
                }
                isLoggedOut = true
            }
        }
    }

    var preferredColorScheme: ColorScheme? {
        switch appearanceMode {
        case "light":
            return .light
        case "dark":
            return .dark
        default:
            return nil // System default
        }
    }
}
