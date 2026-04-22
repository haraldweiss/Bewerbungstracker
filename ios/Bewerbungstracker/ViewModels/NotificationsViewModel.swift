import SwiftUI
import SwiftData

@MainActor
class NotificationsViewModel: ObservableObject {
    @Published var notifications: [NotificationModel] = []
    @Published var filteredNotifications: [NotificationModel] = []
    @Published var searchText: String = ""
    @Published var selectedTypeFilter: NotificationType? = nil

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchNotifications()
    }

    func fetchNotifications() {
        do {
            let descriptor = FetchDescriptor<NotificationModel>(
                sortBy: [SortDescriptor(\.timestamp, order: .reverse)]
            )
            notifications = try modelContext.fetch(descriptor)
            applyFilters()
        } catch {
            print("Failed to fetch notifications: \(error)")
        }
    }

    func applyFilters() {
        var filtered = notifications

        if let typeFilter = selectedTypeFilter {
            filtered = filtered.filter { $0.type == typeFilter }
        }

        if !searchText.isEmpty {
            filtered = filtered.filter { notification in
                notification.title.localizedCaseInsensitiveContains(searchText) ||
                notification.description.localizedCaseInsensitiveContains(searchText)
            }
        }

        filteredNotifications = filtered
    }

    func updateSearch(_ text: String) {
        searchText = text
        applyFilters()
    }

    func setTypeFilter(_ type: NotificationType?) {
        selectedTypeFilter = type
        applyFilters()
    }

    func addNotification(type: NotificationType, title: String, description: String, application: ApplicationModel? = nil) {
        let newNotification = NotificationModel(
            type: type,
            title: title,
            description: description,
            timestamp: Date(),
            application: application
        )
        modelContext.insert(newNotification)
        try? modelContext.save()
        fetchNotifications()
    }

    func markAsRead(_ notification: NotificationModel) {
        notification.isRead = true
        try? modelContext.save()
        fetchNotifications()
    }

    func markAllAsRead() {
        notifications.forEach { $0.isRead = true }
        try? modelContext.save()
        fetchNotifications()
    }

    func deleteNotification(_ notification: NotificationModel) {
        modelContext.delete(notification)
        try? modelContext.save()
        fetchNotifications()
    }

    func deleteAllNotifications() {
        notifications.forEach { modelContext.delete($0) }
        try? modelContext.save()
        fetchNotifications()
    }

    var unreadCount: Int {
        notifications.filter { !$0.isRead }.count
    }

    func filterByType(_ typeString: String) {
        if let type = NotificationType(rawValue: typeString) {
            selectedTypeFilter = type
        } else {
            // Handle custom type string matching
            selectedTypeFilter = NotificationType.reminder
        }
        applyFilters()
    }
}
