import SwiftUI
import SwiftData

@MainActor
class EmailsViewModel: ObservableObject {
    @Published var emails: [EmailModel] = []
    @Published var groupedEmails: [(application: ApplicationModel?, emails: [EmailModel])] = []
    @Published var searchText: String = ""
    @Published var selectedEmail: EmailModel? = nil
    @Published var showDetailView: Bool = false

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchEmails()
    }

    func fetchEmails() {
        do {
            let descriptor = FetchDescriptor<EmailModel>(
                sortBy: [SortDescriptor(\.timestamp, order: .reverse)]
            )
            emails = try modelContext.fetch(descriptor)
            groupEmailsByApplication()
        } catch {
            print("Failed to fetch emails: \(error)")
        }
    }

    func groupEmailsByApplication() {
        var filtered = emails

        // Apply search filter
        if !searchText.isEmpty {
            filtered = filtered.filter { email in
                email.subject.localizedCaseInsensitiveContains(searchText) ||
                email.fromAddress.localizedCaseInsensitiveContains(searchText) ||
                email.body?.localizedCaseInsensitiveContains(searchText) ?? false
            }
        }

        // Group by application and status
        var groups: [String: (application: ApplicationModel?, emails: [EmailModel])] = [:]

        for email in filtered {
            if let app = email.matchedApplication {
                let key = "\(app.id)-\(app.status)"
                if groups[key] == nil {
                    groups[key] = (application: app, emails: [])
                }
                groups[key]?.emails.append(email)
            } else {
                // Unmatched emails
                let key = "unmatched"
                if groups[key] == nil {
                    groups[key] = (application: nil, emails: [])
                }
                groups[key]?.emails.append(email)
            }
        }

        // Sort groups by application company name and collect
        groupedEmails = groups.values.sorted { (group1, group2) in
            let name1 = group1.application?.company ?? "Unmatched"
            let name2 = group2.application?.company ?? "Unmatched"
            return name1.localizedCaseInsensitiveCompare(name2) == .orderedAscending
        }

        // Sort emails within each group by timestamp descending
        groupedEmails = groupedEmails.map { group in
            let sortedEmails = group.emails.sorted { $0.timestamp > $1.timestamp }
            return (application: group.application, emails: sortedEmails)
        }
    }

    func updateSearch(_ text: String) {
        searchText = text
        groupEmailsByApplication()
    }

    func selectEmail(_ email: EmailModel) {
        selectedEmail = email
        showDetailView = true
    }

    func linkEmail(_ email: EmailModel, to application: ApplicationModel) {
        email.matchedApplication = application
        try? modelContext.save()
        fetchEmails()
    }

    func deleteEmail(_ email: EmailModel) {
        modelContext.delete(email)
        try? modelContext.save()
        fetchEmails()
    }
}
