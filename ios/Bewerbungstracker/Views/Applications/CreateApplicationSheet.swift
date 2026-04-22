import SwiftUI

struct CreateApplicationSheet: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var viewModel: ApplicationsViewModel

    @State private var company: String = ""
    @State private var position: String = ""
    @State private var location: String = ""
    @State private var appliedDate: Date = Date()

    var isValid: Bool {
        !company.trimmingCharacters(in: .whitespaces).isEmpty &&
        !position.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Job Details") {
                    TextField("Company", text: $company)
                    TextField("Position", text: $position)
                    TextField("Location (optional)", text: $location)
                }

                Section("Applied Date") {
                    DatePicker("Date", selection: $appliedDate, displayedComponents: .date)
                }
            }
            .navigationTitle("New Application")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        viewModel.createApplication(
                            company: company,
                            position: position,
                            location: location.isEmpty ? "" : location,
                            appliedDate: appliedDate
                        )
                        dismiss()
                    }
                    .disabled(!isValid)
                }
            }
        }
    }
}

#Preview {
    @StateObject var viewModel = ApplicationsViewModel(modelContext: ModelContext(try! ModelContainer(for: ApplicationModel.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true))))
    return CreateApplicationSheet(viewModel: viewModel)
}
