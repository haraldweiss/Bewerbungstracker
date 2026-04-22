import Foundation

// MARK: - Response Models

struct AuthResponse: Codable {
    let user_id: String
    let email: String
    let access_token: String
    let refresh_token: String
    let expires_in: Int
}

struct ApplicationResponse: Codable {
    let id: String
    let company: String
    let position: String
    let location: String
    let status: String
    let applied_date: String
    let created_at: String
    let updated_at: String
    let notes: String?
}

struct ApplicationsListResponse: Codable {
    let total: Int
    let has_more: Bool
    let items: [ApplicationResponse]
}

struct EmailResponse: Codable {
    let id: String
    let subject: String
    let from: String
    let body_preview: String?
    let timestamp: String
}

struct EmailDetailResponse: Codable {
    let id: String
    let subject: String
    let from: String
    let to: String
    let timestamp: String
    let body: String
}

struct SyncResponse: Codable {
    let synced_count: Int
    let new_emails: Int
    let timestamp: String
}

struct SyncStatusResponse: Codable {
    let last_sync: String
    let status: String
    let email_count: Int
    let next_sync_in_seconds: Int
}

struct ErrorResponse: Codable {
    let error: String
    let code: Int
}

struct MatchResult: Codable {
    let matched: Bool
    let confidence: Double?
}

// MARK: - Request Models

struct RegisterRequest: Codable {
    let email: String
    let password: String
}

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct CreateApplicationRequest: Codable {
    let company: String
    let position: String
    let location: String?
    let applied_date: String
    let notes: String?
}

struct UpdateApplicationRequest: Codable {
    let company: String
    let position: String
    let location: String?
    let applied_date: String
    let notes: String?
}

// MARK: - API Client Protocol

protocol APIClientProtocol {
    // Auth endpoints
    func register(email: String, password: String) async throws -> AuthResponse
    func login(email: String, password: String) async throws -> AuthResponse
    func refreshToken() async throws -> AuthResponse
    func logout() async throws -> Void
    func getCurrentUser() async throws -> AuthResponse

    // Applications endpoints
    func listApplications() async throws -> [ApplicationResponse]
    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse
    func getApplication(id: UUID) async throws -> ApplicationResponse
    func updateApplication(id: UUID, request: UpdateApplicationRequest) async throws -> ApplicationResponse
    func deleteApplication(id: UUID) async throws -> Void

    // Emails endpoints
    func listEmails() async throws -> [EmailResponse]
    func getEmail(id: UUID) async throws -> EmailDetailResponse
    func matchEmail(id: UUID, applicationId: UUID) async throws -> MatchResult
    func syncEmails() async throws -> SyncResponse
    func syncStatus() async throws -> SyncStatusResponse
}
