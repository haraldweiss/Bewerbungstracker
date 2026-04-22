import XCTest
import SwiftData
@testable import Bewerbungstracker

@MainActor
class AuthIntegrationTests: XCTestCase {
    var sut: AuthViewModel!
    var mockAPI: MockAPIClient!
    var modelContext: ModelContext!

    override func setUp() {
        super.setUp()
        mockAPI = MockAPIClient()
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(
            for: ApplicationModel.self,
            configurations: config
        )
        modelContext = ModelContext(container)
        sut = AuthViewModel(modelContext: modelContext, apiClient: mockAPI)
    }

    override func tearDown() {
        super.tearDown()
        sut = nil
        mockAPI = nil
        modelContext = nil
    }

    func testRegisterFlow_Success() async throws {
        sut.register(email: "newuser@example.com", password: "SecurePass123")
        try await Task.sleep(nanoseconds: 1_500_000_000) // Wait for async

        XCTAssertTrue(sut.isAuthenticated)
        XCTAssertEqual(sut.currentUser?.email, "test@example.com")
        XCTAssertNil(sut.errorMessage)
    }

    func testLoginFlow_Success() async throws {
        sut.login(email: "test@example.com", password: "password123")
        try await Task.sleep(nanoseconds: 1_500_000_000)

        XCTAssertTrue(sut.isAuthenticated)
        XCTAssertEqual(sut.currentUser?.email, "test@example.com")
        XCTAssertFalse(sut.isLoading)
    }

    func testLoginFlow_InvalidCredentials() async throws {
        sut.login(email: "invalid@example.com", password: "wrong")
        try await Task.sleep(nanoseconds: 1_500_000_000)

        XCTAssertFalse(sut.isAuthenticated)
        XCTAssertNotNil(sut.errorMessage)
        XCTAssert(sut.errorMessage?.contains("Invalid") ?? false)
    }

    func testTokenRefresh_Success() async throws {
        // First login
        sut.login(email: "test@example.com", password: "password123")
        try await Task.sleep(nanoseconds: 1_500_000_000)

        let oldToken = UserDefaults.standard.string(forKey: "accessToken")

        // Refresh
        sut.refreshToken()
        try await Task.sleep(nanoseconds: 1_500_000_000)

        let newToken = UserDefaults.standard.string(forKey: "accessToken")
        XCTAssertNotEqual(oldToken, newToken)
        XCTAssertNotNil(newToken)
    }

    func testLogout_ClearsAuth() async throws {
        // First login
        sut.login(email: "test@example.com", password: "password123")
        try await Task.sleep(nanoseconds: 1_500_000_000)
        XCTAssertTrue(sut.isAuthenticated)

        // Logout
        sut.logout()
        try await Task.sleep(nanoseconds: 1_500_000_000)

        XCTAssertFalse(sut.isAuthenticated)
        XCTAssertNil(UserDefaults.standard.string(forKey: "accessToken"))
    }
}
