import XCTest
import SwiftData
@testable import Bewerbungstracker

class EndToEndTests: XCTestCase {
    var applicationsViewModel: ApplicationsViewModel!
    var emailsViewModel: EmailsViewModel!
    var notificationsViewModel: NotificationsViewModel!
    var modelContext: ModelContext!

    override func setUp() {
        super.setUp()

        // Setup in-memory SwiftData container for testing
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(
            for: ApplicationModel.self, EmailModel.self, NotificationModel.self,
            configurations: config
        )
        modelContext = ModelContext(container)

        // Initialize ViewModels
        applicationsViewModel = ApplicationsViewModel(modelContext: modelContext)
        emailsViewModel = EmailsViewModel(modelContext: modelContext)
        notificationsViewModel = NotificationsViewModel(modelContext: modelContext)
    }

    // MARK: - Application Workflow Tests

    func testApplicationWorkflow() {
        // Test: Create → View in list → Filter → Search → Delete

        // Create application
        applicationsViewModel.createApplication(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date()
        )
        XCTAssertEqual(applicationsViewModel.applications.count, 1)
        XCTAssertEqual(applicationsViewModel.applications[0].company, "Google")

        // View in list (should be in filtered list)
        applicationsViewModel.setFilter(.applied)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Filter by status
        applicationsViewModel.setFilter(.applied)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Search by company
        applicationsViewModel.updateSearch("Google")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Search with no match
        applicationsViewModel.updateSearch("Meta")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 0)

        // Reset search and delete
        applicationsViewModel.updateSearch("")
        if let app = applicationsViewModel.applications.first {
            applicationsViewModel.deleteApplication(app)
        }
        XCTAssertEqual(applicationsViewModel.applications.count, 0)
    }

    func testMultipleApplicationsFiltering() {
        // Create multiple applications with different statuses
        applicationsViewModel.createApplication(
            company: "Google",
            position: "SWE",
            location: "Mountain View",
            appliedDate: Date()
        )

        applicationsViewModel.createApplication(
            company: "Apple",
            position: "Engineer",
            location: "Cupertino",
            appliedDate: Date()
        )

        // Update second app to interview status
        if let secondApp = applicationsViewModel.applications.last {
            applicationsViewModel.updateApplication(
                secondApp,
                company: "Apple",
                position: "Engineer",
                location: "Cupertino",
                status: "interview"
            )
        }

        XCTAssertEqual(applicationsViewModel.applications.count, 2)

        // Filter by applied
        applicationsViewModel.setFilter(.applied)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Filter by interview
        applicationsViewModel.setFilter(.interview)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Clear filter
        applicationsViewModel.setFilter(nil)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 2)
    }

    func testApplicationSearch() {
        // Create applications
        applicationsViewModel.createApplication(company: "Google", position: "SWE", appliedDate: Date())
        applicationsViewModel.createApplication(company: "Apple", position: "Engineer", appliedDate: Date())
        applicationsViewModel.createApplication(company: "Meta", position: "SWE", appliedDate: Date())

        XCTAssertEqual(applicationsViewModel.applications.count, 3)

        // Search for SWE
        applicationsViewModel.updateSearch("SWE")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 2)

        // Search for Google
        applicationsViewModel.updateSearch("Google")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Search for non-existent
        applicationsViewModel.updateSearch("Amazon")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 0)
    }

    // MARK: - Email Workflow Tests

    func testEmailWorkflow() {
        // Test: Fetch → Filter by status → Search → Mark as matched

        // Create emails
        let email1 = EmailModel(
            subject: "Interview Opportunity",
            fromAddress: "recruiter@google.com",
            body: "We're interested in your profile",
            timestamp: Date(),
            matchScore: 0.95
        )

        let email2 = EmailModel(
            subject: "Profile Update",
            fromAddress: "noreply@linkedin.com",
            body: "Your profile has been updated",
            timestamp: Date(),
            matchScore: 0.2
        )

        modelContext.insert(email1)
        modelContext.insert(email2)
        try? modelContext.save()

        emailsViewModel.fetchEmails()
        XCTAssertEqual(emailsViewModel.emails.count, 2)

        // Filter high match score
        emailsViewModel.filterByMatchScore(0.8)
        XCTAssertEqual(emailsViewModel.filteredEmails.count, 1)
        XCTAssertEqual(emailsViewModel.filteredEmails[0].fromAddress, "recruiter@google.com")
    }

    func testEmailSearch() {
        // Create emails
        let email1 = EmailModel(
            subject: "Interview Opportunity",
            fromAddress: "recruiter@google.com",
            body: "We're interested in your profile",
            timestamp: Date(),
            matchScore: 0.95
        )

        let email2 = EmailModel(
            subject: "Account Confirmation",
            fromAddress: "support@company.com",
            body: "Please confirm your email",
            timestamp: Date(),
            matchScore: 0.3
        )

        modelContext.insert(email1)
        modelContext.insert(email2)
        try? modelContext.save()

        emailsViewModel.fetchEmails()

        // Search for Interview
        emailsViewModel.updateSearch("Interview")
        XCTAssertGreaterThan(emailsViewModel.groupedEmails.count, 0)

        // Search for google
        emailsViewModel.updateSearch("google")
        XCTAssertGreaterThan(emailsViewModel.groupedEmails.count, 0)

        // Search for non-existent
        emailsViewModel.updateSearch("rejected")
        XCTAssertEqual(emailsViewModel.groupedEmails.count, 0)
    }

    // MARK: - Notification Workflow Tests

    func testNotificationWorkflow() {
        // Test: Create → View → Mark as read → Delete

        let notification = NotificationModel(
            type: .interviewScheduled,
            title: "Interview Scheduled",
            description: "Google Interview on Monday",
            timestamp: Date()
        )

        modelContext.insert(notification)
        try? modelContext.save()

        notificationsViewModel.fetchNotifications()
        XCTAssertEqual(notificationsViewModel.notifications.count, 1)
        XCTAssertEqual(notificationsViewModel.unreadCount, 1)

        // Mark as read
        if let firstNotification = notificationsViewModel.notifications.first {
            notificationsViewModel.markAsRead(firstNotification)
        }

        notificationsViewModel.fetchNotifications()
        XCTAssertEqual(notificationsViewModel.unreadCount, 0)

        // Delete notification
        if let firstNotification = notificationsViewModel.notifications.first {
            notificationsViewModel.deleteNotification(firstNotification)
        }

        notificationsViewModel.fetchNotifications()
        XCTAssertEqual(notificationsViewModel.notifications.count, 0)
    }

    func testNotificationFiltering() {
        // Create notifications with different types
        let interviewNotif = NotificationModel(
            type: .interviewScheduled,
            title: "Interview Scheduled",
            description: "Google Interview",
            timestamp: Date()
        )

        let offerNotif = NotificationModel(
            type: .offerReceived,
            title: "Offer Received",
            description: "Congratulations! You received an offer",
            timestamp: Date()
        )

        modelContext.insert(interviewNotif)
        modelContext.insert(offerNotif)
        try? modelContext.save()

        notificationsViewModel.fetchNotifications()
        XCTAssertEqual(notificationsViewModel.notifications.count, 2)
        XCTAssertEqual(notificationsViewModel.unreadCount, 2)

        // Filter by type
        notificationsViewModel.filterByType("interview_scheduled")
        XCTAssertEqual(notificationsViewModel.filteredNotifications.count, 1)

        notificationsViewModel.filterByType("offer_received")
        XCTAssertEqual(notificationsViewModel.filteredNotifications.count, 1)
    }

    // MARK: - Cross-Feature Integration Tests

    func testApplicationEmailIntegration() {
        // Create application
        applicationsViewModel.createApplication(
            company: "Google",
            position: "SWE",
            location: "Mountain View",
            appliedDate: Date()
        )

        guard let application = applicationsViewModel.applications.first else {
            XCTFail("Failed to create application")
            return
        }

        // Create related email
        let email = EmailModel(
            subject: "Interview Opportunity",
            fromAddress: "recruiter@google.com",
            body: "We're interested in your Google application",
            timestamp: Date(),
            matchScore: 0.95
        )

        email.matchedApplication = application
        modelContext.insert(email)
        try? modelContext.save()

        emailsViewModel.fetchEmails()
        XCTAssertEqual(emailsViewModel.emails.count, 1)
        XCTAssertEqual(emailsViewModel.emails[0].matchedApplication?.company, "Google")
    }

    func testApplicationNotificationIntegration() {
        // Create application
        applicationsViewModel.createApplication(
            company: "Apple",
            position: "Engineer",
            location: "Cupertino",
            appliedDate: Date()
        )

        guard let application = applicationsViewModel.applications.first else {
            XCTFail("Failed to create application")
            return
        }

        // Create related notification
        let notification = NotificationModel(
            type: .interviewScheduled,
            title: "Interview Scheduled",
            description: "Interview scheduled for Apple position",
            timestamp: Date(),
            application: application
        )

        modelContext.insert(notification)
        try? modelContext.save()

        notificationsViewModel.fetchNotifications()
        XCTAssertEqual(notificationsViewModel.notifications.count, 1)
        XCTAssertEqual(
            notificationsViewModel.notifications[0].application?.company,
            "Apple"
        )
    }

    // MARK: - Stress Tests

    func testLargeDataset() {
        // Create 50 applications
        for i in 0..<50 {
            applicationsViewModel.createApplication(
                company: "Company \(i)",
                position: "Position \(i % 5)",
                location: "Location \(i % 10)",
                appliedDate: Date()
            )
        }

        XCTAssertEqual(applicationsViewModel.applications.count, 50)

        // Search should still work
        applicationsViewModel.updateSearch("Company 25")
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)

        // Filter should still work
        applicationsViewModel.setFilter(.applied)
        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 50)
    }

    func testCombinedSearchAndFilter() {
        // Create multiple applications
        applicationsViewModel.createApplication(company: "Google", position: "SWE", appliedDate: Date())
        applicationsViewModel.createApplication(company: "Apple", position: "Engineer", appliedDate: Date())
        applicationsViewModel.createApplication(company: "Meta", position: "SWE", appliedDate: Date())

        // Update one to interview status
        if let app = applicationsViewModel.applications.last {
            applicationsViewModel.updateApplication(
                app,
                company: "Meta",
                position: "SWE",
                location: nil,
                status: "interview"
            )
        }

        // Apply both filter and search
        applicationsViewModel.setFilter(.applied)
        applicationsViewModel.updateSearch("SWE")

        XCTAssertEqual(applicationsViewModel.filteredApplications.count, 1)
        XCTAssertEqual(applicationsViewModel.filteredApplications[0].company, "Google")
    }
}
