import Foundation

class MockAPIClient: APIClientProtocol {
    let fixtureBundle: Bundle
    private let decoder = JSONDecoder()

    init(bundle: Bundle = Bundle.main) {
        self.fixtureBundle = bundle
    }

    // MARK: - Helper: Load Fixture

    private func loadFixture<T: Decodable>(_ path: String) throws -> T {
        guard let url = fixtureBundle.url(forResource: path, withExtension: "json", subdirectory: "Fixtures") else {
            throw NSError(domain: "MockAPIClient", code: -1, userInfo: [NSLocalizedDescriptionKey: "Fixture not found: \(path)"])
        }

        let data = try Data(contentsOf: url)
        return try decoder.decode(T.self, from: data)
    }

    private func simulateDelay() async {
        let delayMs = UInt64.random(in: 500...1000) * 1_000_000 // 500-1000ms in nanoseconds
        try? await Task.sleep(nanoseconds: delayMs)
    }

    // MARK: - Authentication

    func register(email: String, password: String) async throws -> AuthResponse {
        await simulateDelay()
        return try loadFixture("auth/register_success")
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        await simulateDelay()

        // Simulate invalid credentials error
        if email == "invalid@example.com" {
            let errorResponse: ErrorResponse = try loadFixture("auth/error_401_unauthorized")
            throw NSError(domain: "APIError", code: 401, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        return try loadFixture("auth/login_success")
    }

    func refreshToken() async throws -> AuthResponse {
        await simulateDelay()
        return try loadFixture("auth/refresh_token")
    }

    func logout() async throws {
        await simulateDelay()
        // No response needed for logout
    }

    func getCurrentUser() async throws -> AuthResponse {
        await simulateDelay()
        return try loadFixture("auth/login_success")
    }

    // MARK: - Applications

    func listApplications() async throws -> ApplicationsListResponse {
        await simulateDelay()
        return try loadFixture("applications/list_3_items")
    }

    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse {
        await simulateDelay()

        // Simulate validation error
        if request.company.isEmpty {
            let errorResponse: ErrorResponse = try loadFixture("error_responses/400_bad_request")
            throw NSError(domain: "APIError", code: 400, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        return try loadFixture("applications/create_response")
    }

    func getApplication(id: String) async throws -> ApplicationResponse {
        await simulateDelay()

        // Simulate not found error
        if id == "nonexistent" {
            let errorResponse: ErrorResponse = try loadFixture("applications/error_404_not_found")
            throw NSError(domain: "APIError", code: 404, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        return try loadFixture("applications/create_response")
    }

    func updateApplication(id: String, request: UpdateApplicationRequest) async throws -> ApplicationResponse {
        await simulateDelay()

        // Simulate not found error
        if id == "nonexistent" {
            let errorResponse: ErrorResponse = try loadFixture("applications/error_404_not_found")
            throw NSError(domain: "APIError", code: 404, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        return try loadFixture("applications/update_response")
    }

    func deleteApplication(id: String) async throws {
        await simulateDelay()

        // Simulate not found error
        if id == "nonexistent" {
            let errorResponse: ErrorResponse = try loadFixture("applications/error_404_not_found")
            throw NSError(domain: "APIError", code: 404, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        // Success: no response needed
    }

    // MARK: - Emails

    func listEmails() async throws -> EmailsListResponse {
        await simulateDelay()
        return try loadFixture("emails/list_grouped")
    }

    func getEmail(id: String) async throws -> EmailDetailResponse {
        await simulateDelay()

        // Simulate not found error
        if id == "nonexistent" {
            let errorResponse: ErrorResponse = try loadFixture("applications/error_404_not_found")
            throw NSError(domain: "APIError", code: 404, userInfo: [NSLocalizedDescriptionKey: errorResponse.error])
        }

        return try loadFixture("emails/detail_full_body")
    }

    func matchEmail(id: String, applicationId: String) async throws -> MatchResult {
        await simulateDelay()

        // Simulate successful match
        return MatchResult(matched: true, confidence: 0.95)
    }

    func syncEmails() async throws -> SyncResponse {
        await simulateDelay()
        return try loadFixture("emails/sync_response")
    }

    func syncStatus() async throws -> SyncStatusResponse {
        await simulateDelay()
        return try loadFixture("emails/sync_status")
    }
}
