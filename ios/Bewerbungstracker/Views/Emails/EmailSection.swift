import SwiftUI

struct EmailSection: View {
    let application: ApplicationModel?
    let emails: [EmailModel]
    let onSelectEmail: (EmailModel) -> Void

    @State private var isExpanded: Bool = true

    var sectionTitle: String {
        if let app = application {
            return "\(app.company) - \(ApplicationStatus(rawValue: app.status)?.displayName ?? app.status)"
        }
        return "Unmatched Emails"
    }

    var sectionColor: Color {
        guard let app = application else {
            return AppColors.textTertiary
        }
        return ApplicationStatus(rawValue: app.status)?.color ?? AppColors.textTertiary
    }

    var body: some View {
        VStack(spacing: 0) {
            // Section Header
            Button(action: { withAnimation { isExpanded.toggle() } }) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(sectionTitle)
                            .font(AppFonts.heading)
                            .foregroundColor(AppColors.textPrimary)

                        HStack(spacing: 4) {
                            Circle()
                                .fill(sectionColor)
                                .frame(width: 6, height: 6)
                            Text("\(emails.count) \(emails.count == 1 ? "email" : "emails")")
                                .font(AppFonts.secondary)
                                .foregroundColor(AppColors.textTertiary)
                        }
                    }

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(AppColors.textSecondary)
                }
                .padding(12)
                .background(AppColors.sectionBackground)
            }

            // Section Content
            if isExpanded {
                VStack(spacing: 0) {
                    ForEach(emails, id: \.id) { email in
                        Button(action: { onSelectEmail(email) }) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(email.subject)
                                    .font(AppFonts.heading)
                                    .foregroundColor(AppColors.textPrimary)
                                    .lineLimit(2)

                                HStack(spacing: 8) {
                                    Text(email.fromAddress)
                                        .font(AppFonts.secondary)
                                        .foregroundColor(AppColors.textSecondary)
                                        .lineLimit(1)

                                    Spacer()

                                    Text(DateFormatters.relativeDate(from: email.timestamp))
                                        .font(AppFonts.secondary)
                                        .foregroundColor(AppColors.textTertiary)
                                }
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(AppColors.cardBackground)
                            .borderBottom(color: AppColors.border, width: 1)
                        }
                    }
                }
            }
        }
        .background(AppColors.sectionBackground)
        .cornerRadius(6)
    }
}

// MARK: - Helper View Modifier
extension View {
    func borderBottom(color: Color, width: CGFloat) -> some View {
        VStack(spacing: 0) {
            self
            Divider()
                .background(color)
        }
    }
}

#Preview {
    let sampleApp = ApplicationModel(
        company: "Tech Corp",
        position: "Senior Developer",
        status: "interview"
    )

    let sampleEmails = [
        EmailModel(
            subject: "Interview Confirmation",
            fromAddress: "hr@techcorp.com"
        ),
        EmailModel(
            subject: "Follow-up: Your Application",
            fromAddress: "recruiter@techcorp.com"
        )
    ]

    VStack {
        EmailSection(
            application: sampleApp,
            emails: sampleEmails,
            onSelectEmail: { _ in }
        )
        .padding(12)

        Spacer()
    }
    .background(AppColors.background)
}
