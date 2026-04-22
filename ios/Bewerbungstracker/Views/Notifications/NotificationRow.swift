import SwiftUI

struct NotificationRow: View {
    let notification: NotificationModel
    var onDelete: (() -> Void)?
    var onMarkAsRead: (() -> Void)?
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                // Icon
                Image(systemName: notification.type.icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(colors.primary)
                    .frame(width: 28, height: 28)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(6)

                // Content
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(notification.title)
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .lineLimit(1)

                        if !notification.isRead {
                            Circle()
                                .fill(colors.primary)
                                .frame(width: 8, height: 8)
                        }
                    }

                    Text(notification.description)
                        .font(AppFonts.body)
                        .foregroundColor(colors.textSecondary)
                        .lineLimit(2)

                    HStack(spacing: 12) {
                        Text(DateFormatters.relativeDate(from: notification.timestamp))
                            .font(AppFonts.label)
                            .foregroundColor(colors.textTertiary)

                        if let application = notification.application {
                            Text(application.company)
                                .font(AppFonts.label)
                                .foregroundColor(colors.statusApplied)
                        }
                    }
                }

                Spacer()

                // Actions
                VStack(spacing: 8) {
                    if !notification.isRead {
                        Button(action: { onMarkAsRead?() }) {
                            Image(systemName: "circle.fill")
                                .font(.system(size: 8))
                                .foregroundColor(colors.primary)
                        }
                    }

                    Button(action: { onDelete?() }) {
                        Image(systemName: "xmark")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(colors.textTertiary)
                    }
                }
                .frame(width: 24)
            }
        }
        .padding(12)
        .background(colors.cardBackground)
        .border(colors.border, width: 0.5)
        .cornerRadius(8)
        .contentShape(Rectangle())
    }
}

#Preview {
    NotificationRow(
        notification: NotificationModel(
            type: .applicationCreated,
            title: "Application Submitted",
            description: "Your application to Senior iOS Developer has been submitted successfully.",
            timestamp: Date().addingTimeInterval(-3600)
        )
    )
    .padding()
    .background(colors.sectionBackground)
}
