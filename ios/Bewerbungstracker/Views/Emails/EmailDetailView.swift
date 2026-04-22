import SwiftUI

struct EmailDetailView: View {
    let email: EmailModel
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Text(email.subject)
                        .font(AppFonts.title)
                        .foregroundColor(AppColors.textPrimary)
                        .lineLimit(2)

                    HStack {
                        Text("From: \(email.fromAddress)")
                            .font(AppFonts.secondary)
                            .foregroundColor(AppColors.textSecondary)
                        Spacer()
                    }

                    HStack {
                        Text(DateFormatters.relativeDate(from: email.timestamp))
                            .font(AppFonts.secondary)
                            .foregroundColor(AppColors.textTertiary)
                        Spacer()
                    }
                }
                .padding(12)
                .background(AppColors.sectionBackground)

                // Body
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        if let body = email.body, !body.isEmpty {
                            Text(body)
                                .font(AppFonts.body)
                                .foregroundColor(AppColors.textPrimary)
                                .lineSpacing(2)
                                .padding(12)
                        } else {
                            VStack(spacing: 8) {
                                Image(systemName: "envelope.open")
                                    .font(.system(size: 32))
                                    .foregroundColor(AppColors.textTertiary)
                                Text("No email body available")
                                    .font(AppFonts.secondary)
                                    .foregroundColor(AppColors.textTertiary)
                            }
                            .frame(maxHeight: .infinity)
                            .padding(12)
                        }
                    }
                }

                // Footer Button
                VStack {
                    Button(action: { dismiss() }) {
                        Text("Done")
                            .font(AppFonts.heading)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(12)
                            .background(AppColors.primary)
                            .cornerRadius(6)
                    }
                    .padding(12)
                }
                .background(AppColors.background)
            }
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    let sampleEmail = EmailModel(
        subject: "Interview Confirmation - Senior Developer Position",
        fromAddress: "hr@company.com",
        body: "Thank you for your interest in our Senior Developer position.\n\nWe are pleased to invite you to an interview on March 15th at 2 PM.\n\nPlease confirm your availability.\n\nBest regards,\nHR Team"
    )

    EmailDetailView(email: sampleEmail)
}
