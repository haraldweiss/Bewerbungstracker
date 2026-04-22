import Foundation

class URLSessionAPIClient: APIClientProtocol {
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

    init() {}

    // MARK: - Authentication

    func register(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = RegisterRequest(email: email, password: password)
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        self.refreshToken = authResponse.refreshToken

        return authResponse
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = LoginRequest(email: email, password: password)
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        self.refreshToken = authResponse.refreshToken

        return authResponse
    }

    func refreshToken() async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/refresh")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(refreshToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        self.refreshToken = authResponse.refreshToken

        return authResponse
    }

    func logout() async throws {
        let url = URL(string: "\(baseURL)/auth/logout")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        self.accessToken = nil
        self.refreshToken = nil
    }

    func getCurrentUser() async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/me")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(AuthResponse.self, from: data)
    }

    // MARK: - Applications

    func listApplications() async throws -> ApplicationsListResponse {
        let url = URL(string: "\(baseURL)/applications")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationsListResponse.self, from: data)
    }

    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    func getApplication(id: String) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    func updateApplication(id: String, request: UpdateApplicationRequest) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "PATCH"
        urlRequest.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }

    func deleteApplication(id: String) async throws {
        let url = URL(string: "\(baseURL)/applications/\(id)")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }
    }

    // MARK: - Emails

    func listEmails() async throws -> EmailsListResponse {
        let url = URL(string: "\(baseURL)/emails")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(EmailsListResponse.self, from: data)
    }

    func getEmail(id: String) async throws -> EmailDetailResponse {
        let url = URL(string: "\(baseURL)/emails/\(id)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(EmailDetailResponse.self, from: data)
    }

    func matchEmail(id: String, applicationId: String) async throws -> MatchResult {
        let url = URL(string: "\(baseURL)/emails/\(id)/match")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["application_id": applicationId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(MatchResult.self, from: data)
    }

    func syncEmails() async throws -> SyncResponse {
        let url = URL(string: "\(baseURL)/emails/sync")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(SyncResponse.self, from: data)
    }

    func syncStatus() async throws -> SyncStatusResponse {
        let url = URL(string: "\(baseURL)/emails/sync/status")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIClientError.invalidResponse
        }

        return try JSONDecoder().decode(SyncStatusResponse.self, from: data)
    }
}

// MARK: - Error Handling

enum APIClientError: LocalizedError {
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
