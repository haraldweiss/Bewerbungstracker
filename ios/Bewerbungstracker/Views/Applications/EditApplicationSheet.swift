import SwiftUI
import SwiftData

struct EditApplicationSheet: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var viewModel: ApplicationsViewModel

    let application: ApplicationModel

    @State private var company: String = ""
    @State private var position: String = ""
    @State private var location: String = ""
    @State private var appliedDate: Date = Date()
    @State private var notes: String = ""
    @State private var hasChanges: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Company") {
                    TextField("Company name", text: $company)
                        .onChange(of: company) { _ in checkChanges() }
                }

                Section("Position") {
                    TextField("Job title", text: $position)
                        .onChange(of: position) { _ in checkChanges() }
                }

                Section("Location") {
                    TextField("City, State", text: $location)
                        .onChange(of: location) { _ in checkChanges() }
                }

                Section("Applied Date") {
                    DatePicker("Date", selection: $appliedDate, displayedComponents: .date)
                        .onChange(of: appliedDate) { _ in checkChanges() }
                }

                Section("Notes") {
                    TextEditor(text: $notes)
                        .frame(height: 100)
                        .onChange(of: notes) { _ in checkChanges() }
                }
            }
            .navigationTitle("Edit Application")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        viewModel.editApplication(
                            id: application.id,
                            company: company,
                            position: position,
                            location: location.isEmpty ? nil : location,
                            appliedDate: appliedDate,
                            notes: notes.isEmpty ? nil : notes
                        )
                        dismiss()
                    }
                    .disabled(!hasChanges)
                }
            }
        }
        .onAppear {
            // Pre-fill with existing data
            company = application.company
            position = application.position
            location = application.location ?? ""
            appliedDate = application.appliedDate ?? Date()
            notes = application.notes ?? ""
        }
    }

    private func checkChanges() {
        hasChanges = (
            company != application.company ||
            position != application.position ||
            location != (application.location ?? "") ||
            appliedDate != (application.appliedDate ?? Date()) ||
            notes != (application.notes ?? "")
        )
    }
}

#Preview {
    let modelContext = ModelContext(try! ModelContainer(for: ApplicationModel.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)))
    let viewModel = ApplicationsViewModel(modelContext: modelContext)
    let app = ApplicationModel(
        company: "Google",
        position: "Software Engineer",
        location: "Mountain View, CA",
        status: "interview",
        appliedDate: Date(),
        notes: "Interview scheduled"
    )

    return EditApplicationSheet(application: app, viewModel: viewModel)
}
