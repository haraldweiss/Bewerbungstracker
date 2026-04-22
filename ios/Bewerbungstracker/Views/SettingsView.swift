import SwiftUI
import SwiftData

struct SettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.colorScheme) var colorScheme
    @StateObject private var viewModel: SettingsViewModel
    @State private var showLogoutConfirmation = false

    init() {
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(for: UserModel.self, configurations: config)
        let context = ModelContext(container)
        _viewModel = StateObject(wrappedValue: SettingsViewModel(modelContext: context))
    }

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Profile Card
                    ProfileCard(user: viewModel.user)

                    // Account Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Account")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .padding(.horizontal, 12)

                        NavigationLink(destination: Text("Edit Profile")) {
                            HStack {
                                Image(systemName: "person.fill")
                                    .foregroundColor(colors.primary)
                                Text("Edit Profile")
                                    .foregroundColor(colors.textPrimary)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .foregroundColor(colors.textTertiary)
                            }
                            .padding(12)
                            .background(colors.sectionBackground)
                            .cornerRadius(6)
                        }

                        NavigationLink(destination: Text("Change Password")) {
                            HStack {
                                Image(systemName: "lock.fill")
                                    .foregroundColor(colors.primary)
                                Text("Change Password")
                                    .foregroundColor(colors.textPrimary)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .foregroundColor(colors.textTertiary)
                            }
                            .padding(12)
                            .background(colors.sectionBackground)
                            .cornerRadius(6)
                        }
                    }
                    .padding(.horizontal, 12)

                    // Sync Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Sync")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .padding(.horizontal, 12)

                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Last Sync")
                                    .font(AppFonts.body)
                                    .foregroundColor(colors.textSecondary)
                                Text(viewModel.lastSyncTime)
                                    .font(AppFonts.body)
                                    .foregroundColor(colors.textTertiary)
                            }
                            Spacer()
                        }
                        .padding(12)
                        .background(colors.sectionBackground)
                        .cornerRadius(6)

                        Button(action: {
                            viewModel.manualSync()
                        }) {
                            HStack {
                                if viewModel.isSyncing {
                                    ProgressView()
                                        .tint(colors.primary)
                                } else {
                                    Image(systemName: "arrow.clockwise")
                                }
                                Text(viewModel.isSyncing ? "Syncing..." : "Manual Sync")
                                Spacer()
                            }
                            .foregroundColor(colors.primary)
                            .padding(12)
                            .background(colors.sectionBackground)
                            .cornerRadius(6)
                        }
                        .disabled(viewModel.isSyncing)
                    }
                    .padding(.horizontal, 12)

                    // Appearance Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Appearance")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .padding(.horizontal, 12)

                        VStack(alignment: .leading, spacing: 8) {
                            Text("Theme")
                                .font(AppFonts.body)
                                .foregroundColor(colors.textSecondary)

                            Picker("Theme", selection: $viewModel.appearanceMode) {
                                Text("System").tag("system")
                                Text("Light").tag("light")
                                Text("Dark").tag("dark")
                            }
                            .pickerStyle(.segmented)
                            .tint(colors.primary)
                        }
                        .padding(12)
                        .background(colors.sectionBackground)
                        .cornerRadius(6)
                    }
                    .padding(.horizontal, 12)

                    // Export Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Export")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .padding(.horizontal, 12)

                        NavigationLink(destination: Text("Export Data")) {
                            HStack {
                                Image(systemName: "arrow.down.doc")
                                    .foregroundColor(colors.primary)
                                Text("Export Applications")
                                    .foregroundColor(colors.textPrimary)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .foregroundColor(colors.textTertiary)
                            }
                            .padding(12)
                            .background(colors.sectionBackground)
                            .cornerRadius(6)
                        }
                    }
                    .padding(.horizontal, 12)

                    // App Info Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("App Information")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textPrimary)
                            .padding(.horizontal, 12)

                        HStack {
                            Text("Version")
                                .font(AppFonts.body)
                                .foregroundColor(colors.textSecondary)
                            Spacer()
                            Text("1.0.0")
                                .font(AppFonts.body)
                                .foregroundColor(colors.textTertiary)
                        }
                        .padding(12)
                        .background(colors.sectionBackground)
                        .cornerRadius(6)

                        HStack {
                            Text("Build")
                                .font(AppFonts.body)
                                .foregroundColor(colors.textSecondary)
                            Spacer()
                            Text("1")
                                .font(AppFonts.body)
                                .foregroundColor(colors.textTertiary)
                        }
                        .padding(12)
                        .background(colors.sectionBackground)
                        .cornerRadius(6)
                    }
                    .padding(.horizontal, 12)

                    // Logout Section
                    VStack(alignment: .leading, spacing: 12) {
                        Button(action: {
                            showLogoutConfirmation = true
                        }) {
                            HStack {
                                Image(systemName: "arrowshape.turn.up.left")
                                    .foregroundColor(colors.danger)
                                Text("Logout")
                                    .foregroundColor(colors.danger)
                                Spacer()
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(colors.sectionBackground)
                            .cornerRadius(6)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 20)
                }
            }
            .background(colors.background)
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .alert("Logout", isPresented: $showLogoutConfirmation) {
                Button("Cancel", role: .cancel) {}
                Button("Logout", role: .destructive) {
                    viewModel.logout()
                }
            } message: {
                Text("Are you sure you want to logout? Your local data will be cleared.")
            }
        }
    }
}

#Preview {
    SettingsView()
}
