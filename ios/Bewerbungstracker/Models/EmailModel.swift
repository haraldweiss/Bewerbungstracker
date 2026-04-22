import Foundation
import SwiftData

/// Email model for local SwiftData persistence
@Model
final class EmailModel {
    @Attribute(.unique) var id: UUID
    var subject: String
    var fromAddress: String
    var body: String?
    var timestamp: Date
    var createdAt: Date
    var messageId: String? // IMAP Message-ID
    var matchScore: Double? // Score for matching to applications (0.0-1.0)

    @Relationship(deleteRule: .noAction)
    var matchedApplication: ApplicationModel?

    init(
        id: UUID = UUID(),
        subject: String,
        fromAddress: String,
        body: String? = nil,
        timestamp: Date = Date(),
        matchScore: Double? = nil
    ) {
        self.id = id
        self.subject = subject
        self.fromAddress = fromAddress
        self.body = body
        self.timestamp = timestamp
        self.createdAt = Date()
        self.matchScore = matchScore
    }
}

// MARK: - API Compatibility Extension
extension EmailModel {
    /// Initialize from API response
    convenience init(from response: EmailResponse) {
        let dateFormatter = ISO8601DateFormatter()
        let timestamp = dateFormatter.date(from: response.timestamp) ?? Date()
        let createdAt = dateFormatter.date(from: response.timestamp) ?? Date()

        self.init(
            id: UUID(uuidString: response.id) ?? UUID(),
            subject: response.subject,
            fromAddress: response.from,
            body: nil, // Body is fetched separately
            timestamp: timestamp
        )
        self.createdAt = createdAt
        self.messageId = response.messageId
    }

    /// Convert to API payload for matching
    func toAPIPayload() -> [String: Any] {
        var payload: [String: Any] = [
            "email_id": id.uuidString
        ]

        if let appId = matchedApplication?.id {
            payload["application_id"] = appId.uuidString
        }

        return payload
    }
}
