import SwiftUI

struct ApplicationListItem: View {
    let application: ApplicationModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(application.company)
                        .font(AppFonts.heading)
                        .foregroundColor(AppColors.textPrimary)

                    Text(application.position + (application.location.map { ", \($0)" } ?? ""))
                        .font(AppFonts.body)
                        .foregroundColor(AppColors.textSecondary)
                }

                Spacer()

                VStack {
                    Text(application.status.displayName)
                        .font(AppFonts.label)
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(application.status.color)
                        .cornerRadius(4)
                }
            }

            HStack(spacing: 12) {
                Image(systemName: "calendar")
                    .font(.caption)
                Text(DateFormatters.relativeDate(from: application.appliedDate))
                    .font(AppFonts.secondary)

                Image(systemName: "envelope")
                    .font(.caption)
                Text("\(application.emails.count) emails")
                    .font(AppFonts.secondary)
            }
            .foregroundColor(AppColors.textTertiary)
        }
        .padding(12)
        .background(AppColors.cardBackground)
        .border(AppColors.border, width: 1)
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .frame(width: 3, height: .infinity, alignment: .leading)
                .foregroundColor(application.status.color)
        )
    }
}

#Preview {
    ApplicationListItem(
        application: ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date.now.addingTimeInterval(-86400 * 5)
        )
    )
}
