import Foundation

/// API Client for REST communication with Bewerbungstracker backend
class APIClient {
    static let shared = APIClient()

    private let baseURL = "http://localhost:8080/api"
    private let session = URLSession.shared

    // MARK: - Token Management

    private var accessToken: String? {
        get {
            UserDefaults.standard.string(forKey: "accessToken")
        }
        set {
            if let newValue = newValue {
                UserDefaults.standard.set(newValue, forKey: "accessToken")
            } else {
                UserDefaults.standard.removeObject(forKey: "accessToken")
            }
        }
    }

    private var refreshToken: String? {
        get {
            UserDefaults.standard.string(forKey: "refreshToken")
        }
        set {
            if let newValue = newValue {
                UserDefaults.standard.set(newValue, forKey: "refreshToken")
            } else {
                UserDefaults.standard.removeObject(forKey: "refreshToken")
            }
        }
    }

    // MARK: - Initialization

    private init() {}

    // MARK: - Authentication

    /// Register new user
    /// - Parameters:
    ///   - email: User email
    ///   - password: User password
    /// - Returns: AuthResponse with tokens
    func register(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["email": email, "password": password]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        self.refreshToken = authResponse.refreshToken

        return authResponse
    }

    /// Login user
    /// - Parameters:
    ///   - email: User email
    ///   - password: User password
    /// - Returns: AuthResponse with tokens
    func login(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["email": email, "password": password]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        self.refreshToken = authResponse.refreshToken

        return authResponse
    }

    /// Logout user (clear tokens)
    func logout() async throws {
        self.accessToken = nil
        self.refreshToken = nil

        let url = URL(string: "\(baseURL)/auth/logout")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        _ = try await session.data(for: request)
    }

    /// Check if user is logged in
    var isAuthenticated: Bool {
        accessToken != nil
    }

    // MARK: - Applications

    /// Fetch all applications for current user
    /// - Returns: Array of ApplicationResponse objects
    func fetchApplications() async throws -> [ApplicationResponse] {
        let url = URL(string: "\(baseURL)/applications")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.unauthorized
        }

        let responseData = try JSONDecoder().decode(ApplicationsListResponse.self, from: data)
        return responseData.applications
    }

    /// Create new application
    /// - Parameters:
    ///   - company: Company name
    ///   - position: Position title
    ///   - appliedDate: Date of application (optional)
    /// - Returns: Created ApplicationResponse
    func createApplication(company: String, position: String, appliedDate: Date? = nil) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["company": company, "position": position]
        if let appliedDate = appliedDate {
            body["applied_date"] = ISO8601DateFormatter().string(from: appliedDate)
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    /// Get single application
    /// - Parameter id: Application ID
    /// - Returns: ApplicationResponse
    func getApplication(id: String) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.unauthorized
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    /// Update application
    /// - Parameters:
    ///   - id: Application ID
    ///   - updates: Dictionary of fields to update
    /// - Returns: Updated ApplicationResponse
    func updateApplication(id: String, updates: [String: Any]) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        request.httpBody = try JSONSerialization.data(withJSONObject: updates)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    /// Delete application
    /// - Parameter id: Application ID
    func deleteApplication(id: String) async throws {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Emails

    /// Fetch all emails for current user
    /// - Parameter applicationId: Filter by application (optional)
    /// - Returns: Array of EmailResponse objects
    func fetchEmails(applicationId: String? = nil) async throws -> [EmailResponse] {
        var url = URL(string: "\(baseURL)/emails")!
        if let applicationId = applicationId {
            url.append(queryItems: [URLQueryItem(name: "application_id", value: applicationId)])
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.unauthorized
        }

        let responseData = try JSONDecoder().decode(EmailsListResponse.self, from: data)
        return responseData.emails
    }

    /// Get full email content
    /// - Parameter id: Email ID
    /// - Returns: EmailResponse with full body
    func getEmail(id: String) async throws -> EmailResponse {
        let url = URL(string: "\(baseURL)/emails/\(id)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.unauthorized
        }

        return try JSONDecoder().decode(EmailResponse.self, from: data)
    }

    // MARK: - Claude Integration

    /// Analyze email using Claude
    /// - Parameter emailId: Email ID to analyze
    /// - Returns: AnalysisResponse with extracted metadata
    func analyzeEmail(emailId: String) async throws -> AnalysisResponse {
        let url = URL(string: "\(baseURL)/claude/analyze-email")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["email_id": emailId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(AnalysisResponse.self, from: data)
    }

    /// Match email to application using Claude
    /// - Parameter emailId: Email ID to match
    /// - Returns: MatchResponse with matched application and confidence
    func matchApplicationForEmail(emailId: String) async throws -> MatchResponse {
        let url = URL(string: "\(baseURL)/claude/match-application")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["email_id": emailId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(MatchResponse.self, from: data)
    }
}

// MARK: - Response Models

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct ApplicationResponse: Codable {
    let id: String
    let company: String
    let position: String
    let status: String
    let appliedDate: String?
    let createdAt: String
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, company, position, status
        case appliedDate = "applied_date"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ApplicationsListResponse: Codable {
    let count: Int
    let applications: [ApplicationResponse]
}

struct EmailResponse: Codable {
    let id: String
    let subject: String
    let from: String
    let body: String?
    let matchedApplicationId: String?
    let timestamp: String
    let messageId: String?

    enum CodingKeys: String, CodingKey {
        case id, subject, from, body, timestamp
        case matchedApplicationId = "matched_application_id"
        case messageId = "message_id"
    }
}

struct EmailsListResponse: Codable {
    let count: Int
    let emails: [EmailResponse]
}

struct AnalysisResponse: Codable {
    let emailId: String
    let analysis: [String: AnyCodable]
    let modelUsed: String
    let cost: Double

    enum CodingKeys: String, CodingKey {
        case emailId = "email_id"
        case analysis
        case modelUsed = "model_used"
        case cost
    }
}

struct MatchResponse: Codable {
    let emailId: String
    let matchedApplicationId: String?
    let confidence: Double
    let modelUsed: String
    let cost: Double

    enum CodingKeys: String, CodingKey {
        case emailId = "email_id"
        case matchedApplicationId = "matched_application_id"
        case confidence
        case modelUsed = "model_used"
        case cost
    }
}

// MARK: - Error Handling

enum APIError: LocalizedError {
    case invalidResponse
    case unauthorized
    case networkError(Error)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .unauthorized:
            return "Unauthorized. Please login again."
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        }
    }
}

// MARK: - AnyCodable Helper

enum AnyCodable: Codable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([AnyCodable])
    case object([String: AnyCodable])

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if container.decodeNil() {
            self = .null
        } else if let bool = try? container.decode(Bool.self) {
            self = .bool(bool)
        } else if let int = try? container.decode(Int.self) {
            self = .int(int)
        } else if let double = try? container.decode(Double.self) {
            self = .double(double)
        } else if let string = try? container.decode(String.self) {
            self = .string(string)
        } else if let array = try? container.decode([AnyCodable].self) {
            self = .array(array)
        } else if let object = try? container.decode([String: AnyCodable].self) {
            self = .object(object)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode AnyCodable"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()

        switch self {
        case .null:
            try container.encodeNil()
        case .bool(let bool):
            try container.encode(bool)
        case .int(let int):
            try container.encode(int)
        case .double(let double):
            try container.encode(double)
        case .string(let string):
            try container.encode(string)
        case .array(let array):
            try container.encode(array)
        case .object(let object):
            try container.encode(object)
        }
    }
}
