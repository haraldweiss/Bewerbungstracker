import SwiftData
import Foundation

@Model
final class UserModel {
    @Attribute(.unique) var id: UUID = UUID()
    var name: String
    var email: String
    var createdAt: Date = Date()
    var lastSyncAt: Date?

    init(name: String, email: String) {
        self.name = name
        self.email = email
    }
}
