import SwiftUI
import SwiftData

struct EmailsView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.colorScheme) var colorScheme
    @StateObject private var viewModel: EmailsViewModel

    init() {
        let container = try! ModelContainer(for: [ApplicationModel.self, EmailModel.self])
        let context = ModelContext(container)
        _viewModel = StateObject(wrappedValue: EmailsViewModel(modelContext: context))
    }

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)
        NavigationStack {
            VStack(spacing: 0) {
                // Search Bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(colors.textTertiary)
                    TextField("Search emails", text: Binding(
                        get: { viewModel.searchText },
                        set: { viewModel.updateSearch($0) }
                    ))
                }
                .padding(12)
                .background(colors.sectionBackground)
                .cornerRadius(6)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                // Emails List
                if viewModel.groupedEmails.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "envelope.open")
                            .font(.system(size: 48))
                            .foregroundColor(colors.textTertiary)
                        Text("No emails")
                            .font(AppFonts.heading)
                            .foregroundColor(colors.textSecondary)
                        Text("Emails linked to your applications will appear here")
                            .font(AppFonts.secondary)
                            .foregroundColor(colors.textTertiary)
                    }
                    .frame(maxHeight: .infinity)
                    .background(colors.background)
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(viewModel.groupedEmails.indices, id: \.self) { index in
                                let group = viewModel.groupedEmails[index]
                                EmailSection(
                                    application: group.application,
                                    emails: group.emails,
                                    onSelectEmail: { email in
                                        viewModel.selectEmail(email)
                                    }
                                )
                            }
                        }
                        .padding(12)
                    }
                }

                Spacer()
            }
            .navigationTitle("Emails")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $viewModel.showDetailView) {
                if let selectedEmail = viewModel.selectedEmail {
                    EmailDetailView(email: selectedEmail)
                }
            }
            .onAppear {
                viewModel.fetchEmails()
            }
        }
    }
}

#Preview {
    EmailsView()
}
