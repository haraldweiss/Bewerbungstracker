import SwiftUI

struct ProfileCard: View {
    let user: UserModel?
    @Environment(\.colorScheme) var colorScheme

    var initials: String {
        guard let user = user else { return "?" }
        let components = user.name.split(separator: " ")
        if components.count >= 2 {
            return String(components[0].prefix(1)) + String(components[1].prefix(1))
        }
        return String(user.name.prefix(1))
    }

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)

        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 16) {
                // Initials circle
                ZStack {
                    Circle()
                        .fill(colors.primary)
                        .frame(width: 56, height: 56)

                    Text(initials)
                        .font(AppFonts.heading)
                        .foregroundColor(.white)
                }

                // User info
                VStack(alignment: .leading, spacing: 4) {
                    Text(user?.name ?? "Unknown User")
                        .font(AppFonts.heading)
                        .foregroundColor(colors.textPrimary)

                    Text(user?.email ?? "no-email@example.com")
                        .font(AppFonts.body)
                        .foregroundColor(colors.textSecondary)
                }

                Spacer()
            }
            .padding(16)
            .background(colors.sectionBackground)
            .cornerRadius(8)
        }
        .padding(12)
    }
}

#Preview {
    ProfileCard(user: UserModel(name: "John Doe", email: "john@example.com"))
}
