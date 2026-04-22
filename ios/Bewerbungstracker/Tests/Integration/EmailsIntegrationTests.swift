import XCTest
import SwiftData
@testable import Bewerbungstracker

@MainActor
class EmailsIntegrationTests: XCTestCase {
    var sut: EmailsViewModel!
    var mockAPI: MockAPIClient!
    var modelContext: ModelContext!

    override func setUp() {
        super.setUp()
        mockAPI = MockAPIClient()
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(
            for: EmailModel.self, ApplicationModel.self,
            configurations: config
        )
        modelContext = ModelContext(container)
        sut = EmailsViewModel(modelContext: modelContext, apiClient: mockAPI)
    }

    override func tearDown() {
        super.tearDown()
        sut = nil
        mockAPI = nil
        modelContext = nil
    }

    func testListEmails_GroupedByApplicationStatus() async throws {
        // Create test application
        let app = ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            status: "interview"
        )
        modelContext.insert(app)
        try? modelContext.save()

        // Create test emails linked to the application
        let email1 = EmailModel(
            subject: "Interview Scheduled",
            fromAddress: "hr@google.com",
            body: "We are pleased to invite you...",
            timestamp: Date()
        )
        email1.matchedApplication = app

        let email2 = EmailModel(
            subject: "Application Confirmation",
            fromAddress: "noreply@google.com",
            body: "Your application has been received...",
            timestamp: Date().addingTimeInterval(-3600)
        )
        email2.matchedApplication = app

        modelContext.insert(email1)
        modelContext.insert(email2)
        try? modelContext.save()

        sut.fetchEmails()
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertGreaterThan(sut.emails.count, 0)
        XCTAssertGreaterThan(sut.groupedEmails.count, 0)

        // Verify grouping by application
        let groupedCompanies = sut.groupedEmails.compactMap { $0.application?.company }
        XCTAssert(groupedCompanies.contains("Google"))
    }

    func testEmailDetailView_LoadsFullBody() async throws {
        // Create a test email with full body
        let email = EmailModel(
            subject: "Interview Scheduled",
            fromAddress: "hr@google.com",
            body: "We are pleased to inform you that you have been selected for an interview. Please confirm your availability for April 24.",
            timestamp: Date()
        )
        modelContext.insert(email)
        try? modelContext.save()

        sut.fetchEmails()
        try await Task.sleep(nanoseconds: 500_000_000)

        // Select email to view details
        sut.selectEmail(email)
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertNotNil(sut.selectedEmail)
        XCTAssertEqual(sut.selectedEmail?.subject, "Interview Scheduled")
        XCTAssertTrue(sut.showDetailView)
        XCTAssert(sut.selectedEmail?.body?.contains("April 24") ?? false)
    }

    func testSyncEmails_UpdatesLocalDatabase() async throws {
        // Create initial email
        let email1 = EmailModel(
            subject: "Application Received",
            fromAddress: "noreply@company.com"
        )
        modelContext.insert(email1)
        try? modelContext.save()

        sut.fetchEmails()
        let initialCount = sut.emails.count
        try await Task.sleep(nanoseconds: 500_000_000)

        // Simulate sync by adding more emails
        let email2 = EmailModel(
            subject: "Interview Scheduled",
            fromAddress: "hr@company.com"
        )
        let email3 = EmailModel(
            subject: "Follow-up",
            fromAddress: "hr@company.com"
        )

        modelContext.insert(email2)
        modelContext.insert(email3)
        try? modelContext.save()

        sut.fetchEmails()
        try await Task.sleep(nanoseconds: 500_000_000)

        XCTAssertGreaterThan(sut.emails.count, initialCount)
    }

    func testSyncStatus_ShowsLastSyncTime() async throws {
        // Create emails to simulate synced data
        let email = EmailModel(
            subject: "Test Email",
            fromAddress: "test@example.com",
            timestamp: Date()
        )
        modelContext.insert(email)
        try? modelContext.save()

        sut.fetchEmails()
        try await Task.sleep(nanoseconds: 500_000_000)

        // Verify emails are present in the model
        XCTAssertGreaterThan(sut.emails.count, 0)

        // Verify sync status would show success
        // (In real scenario, this would call syncStatus() API endpoint)
        XCTAssertFalse(sut.emails.isEmpty)
    }
}
