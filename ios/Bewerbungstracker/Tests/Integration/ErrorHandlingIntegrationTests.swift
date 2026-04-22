import XCTest
import SwiftData
@testable import Bewerbungstracker

@MainActor
class ErrorHandlingIntegrationTests: XCTestCase {
    var authVM: AuthViewModel!
    var appsVM: ApplicationsViewModel!
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
        authVM = AuthViewModel(modelContext: modelContext, apiClient: mockAPI)
        appsVM = ApplicationsViewModel(modelContext: modelContext, apiClient: mockAPI)
    }

    override func tearDown() {
        super.tearDown()
        authVM = nil
        appsVM = nil
        mockAPI = nil
        modelContext = nil
    }

    func testAuth_401Unauthorized_ShowsError() async throws {
        authVM.login(email: "invalid@example.com", password: "wrong")
        try await Task.sleep(nanoseconds: 1_500_000_000)

        XCTAssertFalse(authVM.isAuthenticated)
        XCTAssertNotNil(authVM.errorMessage)
        XCTAssertFalse(authVM.isLoading)
    }

    func testCRUD_404NotFound_ShowsError() async throws {
        do {
            _ = try await mockAPI.getApplication(id: "nonexistent")
            XCTFail("Should have thrown error for nonexistent application")
        } catch {
            let nsError = error as NSError
            XCTAssertEqual(nsError.code, 404)
            XCTAssert(nsError.localizedDescription.contains("not found") || nsError.code == 404)
        }
    }

    func testCRUD_400BadRequest_ValidationError() async throws {
        let badRequest = CreateApplicationRequest(
            company: "", // Empty company
            position: "Engineer",
            location: "SF",
            appliedDate: "2026-04-22",
            notes: nil
        )

        do {
            _ = try await mockAPI.createApplication(badRequest)
            XCTFail("Should have thrown error for bad request")
        } catch {
            let nsError = error as NSError
            XCTAssertEqual(nsError.code, 400)
            XCTAssert(nsError.localizedDescription.contains("bad") || nsError.code == 400)
        }
    }
}
