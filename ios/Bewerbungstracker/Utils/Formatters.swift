import Foundation
import SwiftUI

struct DateFormatters {
    static let relativeDateFormatter: DateComponentsFormatter = {
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .abbreviated
        formatter.maximumUnitCount = 1
        return formatter
    }()

    static func relativeDate(from date: Date) -> String {
        let calendar = Calendar.current
        let now = Date()
        let components = calendar.dateComponents([.day, .hour, .minute], from: date, to: now)

        if let days = components.day, days > 0 {
            return days == 1 ? "1 day ago" : "\(days) days ago"
        } else if let hours = components.hour, hours > 0 {
            return hours == 1 ? "1 hour ago" : "\(hours) hours ago"
        } else if let minutes = components.minute, minutes >= 0 {
            return minutes == 0 ? "just now" : "\(minutes) minutes ago"
        }
        return "just now"
    }
}

struct StatusFormatters {
    static func statusColor(_ status: ApplicationStatus) -> Color {
        status.color
    }
}
