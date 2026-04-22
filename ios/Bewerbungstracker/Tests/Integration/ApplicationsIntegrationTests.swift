import XCTest
import SwiftData
@testable import Bewerbungstracker

@MainActor
class ApplicationsIntegrationTests: XCTestCase {
    var sut: ApplicationsViewModel!
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
        sut = ApplicationsViewModel(modelContext: modelContext, apiClient: mockAPI)
    }

    override func tearDown() {
        super.tearDown()
        sut = nil
        mockAPI = nil
        modelContext = nil
    }

    func testListApplications_ReturnsThreeItems() async throws {
        // Create sample applications in the model context
        let app1 = ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View, CA",
            status: "interview",
            appliedDate: Date(timeIntervalSince1970: 1713340800)
        )
        let app2 = ApplicationModel(
            company: "Meta",
            position: "Product Manager",
            location: "Boston, MA",
            status: "applied",
            appliedDate: Date(timeIntervalSince1970: 1712880000)
        )
        let app3 = ApplicationModel(
            company: "Microsoft",
            position: "Data Scientist",
            location: "Seattle, WA",
            status: "offer",
            appliedDate: Date(timeIntervalSince1970: 1712707200)
        )

        modelContext.insert(app1)
        modelContext.insert(app2)
        modelContext.insert(app3)
        try? modelContext.save()

        sut.fetchApplications()
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertEqual(sut.applications.count, 3)
        XCTAssertEqual(sut.applications[2].company, "Google")
        XCTAssertEqual(sut.applications[1].company, "Meta")
        XCTAssertEqual(sut.applications[0].company, "Microsoft")
    }

    func testCreateApplication_AddsToList() async throws {
        let initialCount = sut.applications.count

        sut.createApplication(
            company: "Apple",
            position: "iOS Engineer",
            location: "Cupertino, CA",
            appliedDate: Date()
        )
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertEqual(sut.applications.count, initialCount + 1)
        XCTAssert(sut.applications.contains { $0.company == "Apple" })
    }

    func testFilterByStatus_ShowsOnlyInterview() async throws {
        // Create test applications with different statuses
        let app1 = ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            status: "interview"
        )
        let app2 = ApplicationModel(
            company: "Meta",
            position: "Product Manager",
            status: "applied"
        )
        let app3 = ApplicationModel(
            company: "Microsoft",
            position: "Data Scientist",
            status: "interview"
        )

        modelContext.insert(app1)
        modelContext.insert(app2)
        modelContext.insert(app3)
        try? modelContext.save()

        sut.fetchApplications()
        try await Task.sleep(nanoseconds: 500_000_000)

        sut.setFilter(.interview)
        let filtered = sut.filteredApplications

        XCTAssert(filtered.allSatisfy { $0.status == "interview" })
        XCTAssertEqual(filtered.count, 2)
    }

    func testSearchByCompany_ReturnsMatches() async throws {
        // Create test applications
        let app1 = ApplicationModel(
            company: "Google",
            position: "Software Engineer"
        )
        let app2 = ApplicationModel(
            company: "Meta",
            position: "Product Manager"
        )
        let app3 = ApplicationModel(
            company: "Google",
            position: "Data Scientist"
        )

        modelContext.insert(app1)
        modelContext.insert(app2)
        modelContext.insert(app3)
        try? modelContext.save()

        sut.fetchApplications()
        try await Task.sleep(nanoseconds: 500_000_000)

        sut.updateSearch("Google")
        let filtered = sut.filteredApplications

        XCTAssert(filtered.allSatisfy { $0.company.contains("Google") })
        XCTAssertEqual(filtered.count, 2)
    }

    func testUpdateApplication_RefreshesUI() async throws {
        // Create a test application
        let app = ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            status: "applied"
        )

        modelContext.insert(app)
        try? modelContext.save()

        sut.fetchApplications()
        try await Task.sleep(nanoseconds: 500_000_000)

        let originalCount = sut.applications.count

        // Update the application
        sut.updateApplication(
            app,
            company: "Google",
            position: "Senior Software Engineer",
            location: "Mountain View",
            status: "interview"
        )
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertEqual(sut.applications.count, originalCount)
        let updatedApp = sut.applications.first { $0.id == app.id }
        XCTAssertEqual(updatedApp?.position, "Senior Software Engineer")
        XCTAssertEqual(updatedApp?.status, "interview")
    }

    func testDeleteApplication_RemovesFromList() async throws {
        // Create test applications
        let app1 = ApplicationModel(company: "Google", position: "Software Engineer")
        let app2 = ApplicationModel(company: "Meta", position: "Product Manager")

        modelContext.insert(app1)
        modelContext.insert(app2)
        try? modelContext.save()

        sut.fetchApplications()
        try await Task.sleep(nanoseconds: 500_000_000)

        let originalCount = sut.applications.count
        XCTAssertGreaterThan(originalCount, 0)

        let appToDelete = sut.applications[0]
        sut.deleteApplication(appToDelete)
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertLessThan(sut.applications.count, originalCount)
        XCTAssertFalse(sut.applications.contains { $0.id == appToDelete.id })
    }
}
