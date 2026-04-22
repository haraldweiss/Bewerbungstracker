import SwiftUI

struct EmailDetailView: View {
    let email: EmailModel
    @Environment(\.dismiss) var dismiss
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    // Subject
                    Text(email.subject)
                        .font(AppFonts.title)
                        .foregroundColor(colorScheme == .dark ? .white : Color(red: 0.2, green: 0.2, blue: 0.2))
                        .padding(.top, 12)

                    // Metadata section
                    VStack(alignment: .leading, spacing: 4) {
                        Text("From: \(email.fromAddress)")
                            .font(AppFonts.secondary)
                            .foregroundColor(colorScheme == .dark ? Color(red: 0.8, green: 0.8, blue: 0.8) : Color(red: 0.4, green: 0.4, blue: 0.4))

                        Text(DateFormatters.relativeDate(from: email.timestamp))
                            .font(AppFonts.label)
                            .foregroundColor(Color(red: 0.6, green: 0.6, blue: 0.6))
                    }

                    Divider()
                        .background(colorScheme == .dark ? Color(red: 0.25, green: 0.25, blue: 0.25) : Color(red: 0.88, green: 0.88, blue: 0.88))
                        .padding(.vertical, 8)

                    // Email body
                    if let body = email.body, !body.isEmpty {
                        Text(body.htmlToPlainText())
                            .font(AppFonts.body)
                            .foregroundColor(colorScheme == .dark ? .white : Color(red: 0.2, green: 0.2, blue: 0.2))
                            .lineSpacing(6)
                            .textSelection(.enabled)
                    } else {
                        VStack(spacing: 8) {
                            Image(systemName: "envelope.open")
                                .font(.system(size: 32))
                                .foregroundColor(Color(red: 0.6, green: 0.6, blue: 0.6))
                            Text("No email body available")
                                .font(AppFonts.secondary)
                                .foregroundColor(Color(red: 0.6, green: 0.6, blue: 0.6))
                        }
                        .frame(maxHeight: .infinity)
                    }

                    Spacer(minLength: 20)
                }
                .padding(16)
            }
            .background(colorScheme == .dark ? Color(red: 0.1, green: 0.1, blue: 0.1) : .white)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("Back")
                        }
                        .foregroundColor(Color(red: 0.0, green: 0.478, blue: 1.0))
                    }
                }
            }
        }
    }
}

#Preview {
    let sampleEmail = EmailModel(
        subject: "Interview Confirmation - Senior Developer Position",
        fromAddress: "hr@company.com",
        body: "<html><body><p>Thank you for your interest in our Senior Developer position.</p><p>We are pleased to invite you to an interview on March 15th at 2 PM.</p><p>Please confirm your availability.</p><p>Best regards,<br>HR Team</p></body></html>"
    )

    EmailDetailView(email: sampleEmail)
}
