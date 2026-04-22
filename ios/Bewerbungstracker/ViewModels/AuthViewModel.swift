import SwiftUI
import SwiftData

@MainActor
class AuthViewModel: ObservableObject {
    let apiClient: APIClientProtocol
    @Published var isAuthenticated: Bool = false
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var currentUser: AuthResponse? = nil

    private let modelContext: ModelContext

    init(modelContext: ModelContext, apiClient: APIClientProtocol = URLSessionAPIClient()) {
        self.modelContext = modelContext
        self.apiClient = apiClient
    }

    func register(email: String, password: String) {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let response = try await apiClient.register(email: email, password: password)
                self.currentUser = response
                self.isAuthenticated = true
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    func login(email: String, password: String) {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let response = try await apiClient.login(email: email, password: password)
                self.currentUser = response
                self.isAuthenticated = true
                self.isLoading = false
            } catch {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    func refreshToken() {
        Task {
            do {
                let response = try await apiClient.refreshToken()
                self.currentUser = response
                self.isAuthenticated = true
            } catch {
                self.errorMessage = error.localizedDescription
                self.isAuthenticated = false
            }
        }
    }

    func logout() {
        Task {
            do {
                try await apiClient.logout()
                self.currentUser = nil
                self.isAuthenticated = false
                self.errorMessage = nil
            } catch {
                print("Logout error: \(error)")
                // Clear authentication anyway even if API call fails
                self.currentUser = nil
                self.isAuthenticated = false
            }
        }
    }
}
