import SwiftData
import Foundation

@Model
final class NotificationModel {
    @Attribute(.unique) var id: UUID = UUID()
    var type: NotificationType
    var title: String
    var description: String
    var timestamp: Date
    var isRead: Bool = false

    @Relationship var application: ApplicationModel?

    init(type: NotificationType, title: String, description: String, timestamp: Date = Date(), application: ApplicationModel? = nil) {
        self.type = type
        self.title = title
        self.description = description
        self.timestamp = timestamp
        self.application = application
    }
}

enum NotificationType: String, Codable {
    case applicationCreated = "application_created"
    case interviewScheduled = "interview_scheduled"
    case offerReceived = "offer_received"
    case emailReceived = "email_received"
    case reminder = "reminder"

    var icon: String {
        switch self {
        case .applicationCreated: return "checkmark.circle"
        case .interviewScheduled: return "calendar"
        case .offerReceived: return "star"
        case .emailReceived: return "envelope"
        case .reminder: return "bell"
        }
    }

    var displayName: String {
        switch self {
        case .applicationCreated: return "Application Created"
        case .interviewScheduled: return "Interview Scheduled"
        case .offerReceived: return "Offer Received"
        case .emailReceived: return "Email Received"
        case .reminder: return "Reminder"
        }
    }
}
