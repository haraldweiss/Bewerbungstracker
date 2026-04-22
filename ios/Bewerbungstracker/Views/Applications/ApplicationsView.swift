import SwiftUI
import SwiftData

struct ApplicationsView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel: ApplicationsViewModel

    init() {
        let container = try! ModelContainer(for: ApplicationModel.self)
        let context = ModelContext(container)
        _viewModel = StateObject(wrappedValue: ApplicationsViewModel(modelContext: context))
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search Bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(AppColors.textTertiary)
                    TextField("Search applications", text: Binding(
                        get: { viewModel.searchText },
                        set: { viewModel.updateSearch($0) }
                    ))
                }
                .padding(12)
                .background(AppColors.sectionBackground)
                .cornerRadius(6)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                // Filter Pills
                ApplicationFilterView(selectedFilter: $viewModel.selectedFilter)
                    .onChange(of: viewModel.selectedFilter) { _, _ in
                        viewModel.applyFilters()
                    }

                // Applications List
                if viewModel.filteredApplications.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "inbox.fill")
                            .font(.system(size: 48))
                            .foregroundColor(AppColors.textTertiary)
                        Text("No applications")
                            .font(AppFonts.heading)
                            .foregroundColor(AppColors.textSecondary)
                        Text("Create your first application to get started")
                            .font(AppFonts.secondary)
                            .foregroundColor(AppColors.textTertiary)
                    }
                    .frame(maxHeight: .infinity)
                    .background(AppColors.background)
                } else {
                    List {
                        ForEach(viewModel.filteredApplications, id: \.id) { app in
                            ApplicationListItem(application: app, viewModel: viewModel)
                                .listRowSeparator(.hidden)
                                .listRowInsets(EdgeInsets(top: 4, leading: 12, bottom: 4, trailing: 12))
                        }
                    }
                    .listStyle(.plain)
                }

                // Create Button
                VStack {
                    Button(action: { viewModel.showCreateSheet = true }) {
                        Text("+ New Application")
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
            .navigationTitle("Applications")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $viewModel.showCreateSheet) {
                CreateApplicationSheet(viewModel: viewModel)
            }
        }
    }
}

#Preview {
    ApplicationsView()
}
