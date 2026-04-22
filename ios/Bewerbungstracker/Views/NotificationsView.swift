import SwiftUI

struct NotificationsView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                Image(systemName: "bell.slash")
                    .font(.system(size: 48))
                    .foregroundColor(AppColors.textTertiary)
                Text("No notifications")
                    .font(AppFonts.heading)
                    .foregroundColor(AppColors.textSecondary)
                Text("You'll see important updates here")
                    .font(AppFonts.secondary)
                    .foregroundColor(AppColors.textTertiary)
            }
            .frame(maxHeight: .infinity)
            .background(AppColors.background)
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    NotificationsView()
}
