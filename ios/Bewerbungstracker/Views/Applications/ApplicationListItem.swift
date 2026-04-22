import SwiftUI

struct ApplicationListItem: View {
    let application: ApplicationModel
    @ObservedObject var viewModel: ApplicationsViewModel

    @State private var showingEditSheet = false
    @State private var showingDeleteConfirmation = false

    var body: some View {
        ZStack(alignment: .trailing) {
            // Background action buttons (revealed on swipe)
            HStack(spacing: 0) {
                Spacer()

                // Edit button
                Button(action: {
                    showingEditSheet = true
                }) {
                    Label("Edit", systemImage: "pencil")
                        .labelStyle(.iconOnly)
                        .foregroundColor(.white)
                        .frame(maxHeight: .infinity)
                        .frame(width: 70)
                        .background(Color.blue)
                }

                // Delete button
                Button(action: {
                    showingDeleteConfirmation = true
                }) {
                    Label("Delete", systemImage: "trash")
                        .labelStyle(.iconOnly)
                        .foregroundColor(.white)
                        .frame(maxHeight: .infinity)
                        .frame(width: 70)
                        .background(Color.red)
                }
            }

            // Card content (swipeable)
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
            .contentShape(Rectangle()) // Makes entire card tappable
            .contextMenu {
                // Long-press menu
                Button(action: { showingEditSheet = true }) {
                    Label("Edit", systemImage: "pencil")
                }

                Button(role: .destructive, action: { showingDeleteConfirmation = true }) {
                    Label("Delete", systemImage: "trash")
                }
            }
        }
        .frame(height: 100)
        .sheet(isPresented: $showingEditSheet) {
            EditApplicationSheet(application: application, viewModel: viewModel)
        }
        .alert("Delete Application", isPresented: $showingDeleteConfirmation) {
            Button("Delete", role: .destructive) {
                viewModel.deleteApplication(id: application.id)
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Are you sure you want to delete \(application.company)? This cannot be undone.")
        }
    }
}

#Preview {
    let modelContext = ModelContext(try! ModelContainer(for: ApplicationModel.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)))
    let viewModel = ApplicationsViewModel(modelContext: modelContext)

    return ApplicationListItem(
        application: ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date.now.addingTimeInterval(-86400 * 5)
        ),
        viewModel: viewModel
    )
}
