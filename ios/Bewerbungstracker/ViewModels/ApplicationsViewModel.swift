import SwiftUI
import SwiftData

@MainActor
class ApplicationsViewModel: ObservableObject {
    @Published var applications: [ApplicationModel] = []
    @Published var filteredApplications: [ApplicationModel] = []
    @Published var searchText: String = ""
    @Published var selectedFilter: ApplicationStatus? = nil
    @Published var showCreateSheet: Bool = false

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchApplications()
    }

    func fetchApplications() {
        do {
            let descriptor = FetchDescriptor<ApplicationModel>(
                sortBy: [SortDescriptor(\.appliedDate, order: .reverse)]
            )
            applications = try modelContext.fetch(descriptor)
            applyFilters()
        } catch {
            print("Failed to fetch applications: \(error)")
        }
    }

    func applyFilters() {
        var filtered = applications

        if let filter = selectedFilter {
            filtered = filtered.filter { $0.status == filter.rawValue }
        }

        if !searchText.isEmpty {
            filtered = filtered.filter { app in
                app.company.localizedCaseInsensitiveContains(searchText) ||
                app.position.localizedCaseInsensitiveContains(searchText)
            }
        }

        filteredApplications = filtered
    }

    func updateSearch(_ text: String) {
        searchText = text
        applyFilters()
    }

    func setFilter(_ status: ApplicationStatus?) {
        selectedFilter = status
        applyFilters()
    }

    func createApplication(company: String, position: String, location: String? = nil, appliedDate: Date = Date()) {
        let newApp = ApplicationModel(
            company: company,
            position: position,
            location: location,
            status: "applied",
            appliedDate: appliedDate
        )
        modelContext.insert(newApp)
        try? modelContext.save()
        fetchApplications()
    }

    func deleteApplication(_ app: ApplicationModel) {
        modelContext.delete(app)
        try? modelContext.save()
        fetchApplications()
    }

    func updateApplication(_ app: ApplicationModel, company: String, position: String, location: String?, status: String) {
        app.company = company
        app.position = position
        app.location = location
        app.status = status
        app.updatedAt = Date()
        try? modelContext.save()
        fetchApplications()
    }
}
