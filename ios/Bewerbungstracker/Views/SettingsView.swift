import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("App Information")
                        .font(AppFonts.heading)
                        .foregroundColor(AppColors.textPrimary)

                    HStack {
                        Text("Version")
                            .font(AppFonts.body)
                            .foregroundColor(AppColors.textSecondary)
                        Spacer()
                        Text("1.0.0")
                            .font(AppFonts.body)
                            .foregroundColor(AppColors.textTertiary)
                    }
                    .padding(12)
                    .background(AppColors.sectionBackground)
                    .cornerRadius(6)
                }
                .padding(12)

                Spacer()
            }
            .background(AppColors.background)
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    SettingsView()
}
