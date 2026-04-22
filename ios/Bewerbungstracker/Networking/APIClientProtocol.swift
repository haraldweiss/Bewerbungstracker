import Foundation

// MARK: - Response Models

struct AuthResponse: Codable {
    let userId: String
    let email: String
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case email
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
    }
}

struct ApplicationResponse: Codable {
    let id: String
    let company: String
    let position: String
    let location: String
    let status: String
    let appliedDate: String
    let createdAt: String
    let updatedAt: String
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case id
        case company
        case position
        case location
        case status
        case appliedDate = "applied_date"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case notes
    }
}

struct ApplicationsListResponse: Codable {
    let total: Int
    let hasMore: Bool
    let items: [ApplicationResponse]

    enum CodingKeys: String, CodingKey {
        case total
        case hasMore = "has_more"
        case items
    }
}

struct EmailResponse: Codable {
    let id: String
    let subject: String
    let from: String
    let bodyPreview: String?
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case from
        case bodyPreview = "body_preview"
        case timestamp
    }
}

struct EmailDetailResponse: Codable {
    let id: String
    let subject: String
    let from: String
    let to: String
    let timestamp: String
    let body: String

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case from
        case to
        case timestamp
        case body
    }
}

struct SyncResponse: Codable {
    let syncedCount: Int
    let newEmails: Int
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case syncedCount = "synced_count"
        case newEmails = "new_emails"
        case timestamp
    }
}

struct SyncStatusResponse: Codable {
    let lastSync: String
    let status: String
    let emailCount: Int
    let nextSyncInSeconds: Int

    enum CodingKeys: String, CodingKey {
        case lastSync = "last_sync"
        case status
        case emailCount = "email_count"
        case nextSyncInSeconds = "next_sync_in_seconds"
    }
}

struct ErrorResponse: Codable {
    let error: String
    let code: Int
}

struct MatchResult: Codable {
    let matched: Bool
    let confidence: Double?
}

struct EmailsListResponse: Codable {
    let total: Int
    let groups: [EmailGroup]

    enum CodingKeys: String, CodingKey {
        case total
        case groups
    }
}

struct EmailGroup: Codable {
    let applicationId: String
    let company: String
    let status: String
    let emails: [EmailResponse]

    enum CodingKeys: String, CodingKey {
        case applicationId = "application_id"
        case company
        case status
        case emails
    }
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
    let appliedDate: String
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case company
        case position
        case location
        case appliedDate = "applied_date"
        case notes
    }
}

struct UpdateApplicationRequest: Codable {
    let company: String
    let position: String
    let location: String?
    let appliedDate: String
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case company
        case position
        case location
        case appliedDate = "applied_date"
        case notes
    }
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
    func listApplications() async throws -> ApplicationsListResponse
    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse
    func getApplication(id: String) async throws -> ApplicationResponse
    func updateApplication(id: String, request: UpdateApplicationRequest) async throws -> ApplicationResponse
    func deleteApplication(id: String) async throws -> Void

    // Emails endpoints
    func listEmails() async throws -> EmailsListResponse
    func getEmail(id: String) async throws -> EmailDetailResponse
    func matchEmail(id: String, applicationId: String) async throws -> MatchResult
    func syncEmails() async throws -> SyncResponse
    func syncStatus() async throws -> SyncStatusResponse
}
