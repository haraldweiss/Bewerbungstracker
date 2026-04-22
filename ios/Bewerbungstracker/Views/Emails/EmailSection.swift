import SwiftUI

struct EmailSection: View {
    let application: ApplicationModel?
    let emails: [EmailModel]
    let onSelectEmail: (EmailModel) -> Void
    @Environment(\.colorScheme) var colorScheme

    @State private var isExpanded: Bool = true

    var sectionTitle: String {
        if let app = application {
            return "\(app.company) - \(ApplicationStatus(rawValue: app.status)?.displayName ?? app.status)"
        }
        return "Unmatched Emails"
    }

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)

        let sectionColor: Color = {
            guard let app = application else {
                return colors.textTertiary
            }
            return ApplicationStatus(rawValue: app.status)?.color ?? colors.textTertiary
        }()
        VStack(spacing: 0) {
            // Section Header
            Button(action: { withAnimation { isExpanded.toggle() } }) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(sectionTitle)
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)

                        HStack(spacing: 4) {
                            Circle()
                                .fill(sectionColor)
                                .frame(width: 6, height: 6)
                            Text("\(emails.count) \(emails.count == 1 ? "email" : "emails")")
                                .font(AppFonts.secondary)
                                .foregroundColor(colors.textTertiary)
                        }
                    }

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(colors.textSecondary)
                }
                .padding(12)
                .background(colors.sectionBackground)
            }

            // Section Content
            if isExpanded {
                VStack(spacing: 0) {
                    ForEach(emails, id: \.id) { email in
                        Button(action: { onSelectEmail(email) }) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(email.subject)
                                    .font(AppFonts.heading)
                                    .foregroundColor(colors.textPrimary)
                                    .lineLimit(2)

                                HStack(spacing: 8) {
                                    Text(email.fromAddress)
                                        .font(AppFonts.secondary)
                                        .foregroundColor(colors.textSecondary)
                                        .lineLimit(1)

                                    Spacer()

                                    Text(DateFormatters.relativeDate(from: email.timestamp))
                                        .font(AppFonts.secondary)
                                        .foregroundColor(colors.textTertiary)
                                }
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(colors.cardBackground)
                            .borderBottom(color: colors.border, width: 1)
                        }
                    }
                }
            }
        }
        .background(colors.sectionBackground)
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
    .background(colors.background)
}
