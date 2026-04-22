import Foundation
import SwiftData
import SwiftUI

/// Application (Bewerbung) model for local SwiftData persistence
@Model
final class ApplicationModel {
    @Attribute(.unique) var id: UUID
    var company: String
    var position: String
    var location: String?
    var status: String // "applied", "interview", "offer", "rejected", "archived"
    var appliedDate: Date?
    var createdAt: Date
    var updatedAt: Date
    var notes: String?

    @Relationship(deleteRule: .cascade, inverse: \EmailModel.matchedApplication)
    var emails: [EmailModel] = []

    init(
        id: UUID = UUID(),
        company: String,
        position: String,
        location: String? = nil,
        status: String = "applied",
        appliedDate: Date? = nil,
        notes: String? = nil
    ) {
        self.id = id
        self.company = company
        self.position = position
        self.location = location
        self.status = status
        self.appliedDate = appliedDate
        self.notes = notes
        self.createdAt = Date()
        self.updatedAt = Date()
    }
}

// MARK: - Status Enum
enum ApplicationStatus: String, CaseIterable, Codable {
    case applied = "applied"
    case interview = "interview"
    case offer = "offer"
    case rejected = "rejected"
    case archived = "archived"

    var displayName: String {
        switch self {
        case .applied:
            return "Applied"
        case .interview:
            return "Interview"
        case .offer:
            return "Offer"
        case .rejected:
            return "Rejected"
        case .archived:
            return "Archived"
        }
    }

    var color: Color {
        switch self {
        case .applied: return AppColors.statusApplied
        case .interview: return AppColors.statusInterview
        case .offer: return AppColors.statusOffer
        case .rejected: return AppColors.danger
        case .archived: return AppColors.textTertiary
        }
    }
}

// MARK: - API Compatibility Extension
extension ApplicationModel {
    /// Initialize from API response
    convenience init(from response: ApplicationResponse) {
        let dateFormatter = ISO8601DateFormatter()
        let appliedDate = response.appliedDate.flatMap { dateFormatter.date(from: $0) }
        let createdAt = dateFormatter.date(from: response.createdAt) ?? Date()

        self.init(
            id: UUID(uuidString: response.id) ?? UUID(),
            company: response.company,
            position: response.position,
            status: response.status,
            appliedDate: appliedDate
        )
        self.createdAt = createdAt
    }

    /// Convert to API payload
    func toAPIPayload() -> [String: Any] {
        var payload: [String: Any] = [
            "company": company,
            "position": position,
            "status": status
        ]

        if let appliedDate = appliedDate {
            let formatter = ISO8601DateFormatter()
            payload["applied_date"] = formatter.string(from: appliedDate)
        }

        return payload
    }
}
