import SwiftUI
import SwiftData

struct NotificationsView: View {
    @StateObject private var viewModel: NotificationsViewModel
    @Environment(\.modelContext) private var modelContext

    init() {
        _viewModel = StateObject(wrappedValue: NotificationsViewModel(modelContext: ModelContext(ModelConfiguration())))
    }

    var body: some View {
        NavigationStack {
            ZStack {
                AppColors.background
                    .ignoresSafeArea()

                VStack(spacing: 0) {
                    // Search Bar
                    SearchBar(text: $viewModel.searchText, onSearch: viewModel.updateSearch)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)

                    if viewModel.filteredNotifications.isEmpty {
                        // Empty State
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
                    } else {
                        // Notifications List
                        ScrollView(.vertical, showsIndicators: true) {
                            VStack(spacing: 12) {
                                // Timeline Header with Unread Count
                                HStack {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("Activity Timeline")
                                            .font(AppFonts.title)
                                            .foregroundColor(AppColors.textPrimary)
                                        if viewModel.unreadCount > 0 {
                                            Text("\(viewModel.unreadCount) unread")
                                                .font(AppFonts.label)
                                                .foregroundColor(AppColors.primary)
                                        }
                                    }

                                    Spacer()

                                    // Actions Menu
                                    Menu {
                                        if viewModel.unreadCount > 0 {
                                            Button(action: viewModel.markAllAsRead) {
                                                Label("Mark all as read", systemImage: "checkmark.circle")
                                            }
                                        }
                                        if !viewModel.notifications.isEmpty {
                                            Button(action: viewModel.deleteAllNotifications, label: {
                                                Label("Clear all", systemImage: "trash")
                                            })
                                        }
                                    } label: {
                                        Image(systemName: "ellipsis.circle")
                                            .foregroundColor(AppColors.primary)
                                    }
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)

                                // Notification Rows
                                ForEach(viewModel.filteredNotifications, id: \.id) { notification in
                                    NotificationRow(
                                        notification: notification,
                                        onDelete: {
                                            viewModel.deleteNotification(notification)
                                        },
                                        onMarkAsRead: {
                                            viewModel.markAsRead(notification)
                                        }
                                    )
                                }
                                .padding(.horizontal, 12)
                            }
                            .padding(.vertical, 8)
                        }
                    }
                }
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                viewModel.fetchNotifications()
            }
        }
    }
}

// MARK: - Search Bar Component
struct SearchBar: View {
    @Binding var text: String
    var onSearch: (String) -> Void

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(AppColors.textTertiary)

            TextField("Search notifications", text: $text)
                .font(AppFonts.body)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .onChange(of: text) { _, newValue in
                    onSearch(newValue)
                }

            if !text.isEmpty {
                Button(action: {
                    text = ""
                    onSearch("")
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(AppColors.textTertiary)
                }
            }
        }
        .padding(8)
        .background(AppColors.sectionBackground)
        .cornerRadius(8)
    }
}

#Preview {
    NotificationsView()
}
