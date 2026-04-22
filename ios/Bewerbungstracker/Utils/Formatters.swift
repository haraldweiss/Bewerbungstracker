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

// MARK: - String Extensions for HTML Parsing
extension String {
    /// Convert HTML string to plain text while preserving structure
    func htmlToPlainText() -> String {
        var html = self

        // Remove script and style elements
        html = html.replacingOccurrences(of: "<script[^>]*>.*?</script>", with: "", options: .regularExpression)
        html = html.replacingOccurrences(of: "<style[^>]*>.*?</style>", with: "", options: .regularExpression)

        // Replace block elements with newlines
        html = html.replacingOccurrences(of: "</p>", with: "\n\n")
        html = html.replacingOccurrences(of: "</div>", with: "\n")
        html = html.replacingOccurrences(of: "</blockquote>", with: "\n")
        html = html.replacingOccurrences(of: "<br>", with: "\n")
        html = html.replacingOccurrences(of: "<br/>", with: "\n")
        html = html.replacingOccurrences(of: "<br />", with: "\n")
        html = html.replacingOccurrences(of: "</li>", with: "\n")

        // Remove remaining HTML tags
        html = html.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)

        // Decode HTML entities
        html = html.replacingOccurrences(of: "&nbsp;", with: " ")
        html = html.replacingOccurrences(of: "&lt;", with: "<")
        html = html.replacingOccurrences(of: "&gt;", with: ">")
        html = html.replacingOccurrences(of: "&amp;", with: "&")
        html = html.replacingOccurrences(of: "&quot;", with: "\"")
        html = html.replacingOccurrences(of: "&#39;", with: "'")
        html = html.replacingOccurrences(of: "&apos;", with: "'")

        // Remove extra whitespace while preserving structure
        let lines = html.components(separatedBy: "\n")
        let trimmedLines = lines.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }

        return trimmedLines.joined(separator: "\n")
    }
}
