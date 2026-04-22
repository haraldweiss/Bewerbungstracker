import XCTest
import SwiftData
@testable import Bewerbungstracker

class ApplicationsViewModelTests: XCTestCase {
    var viewModel: ApplicationsViewModel!
    var modelContext: ModelContext!

    override func setUp() {
        super.setUp()
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(for: ApplicationModel.self, configurations: config)
        modelContext = ModelContext(container)
        viewModel = ApplicationsViewModel(modelContext: modelContext)
    }

    func testCreateApplication() {
        viewModel.createApplication(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date()
        )
        XCTAssertEqual(viewModel.applications.count, 1)
        XCTAssertEqual(viewModel.applications[0].company, "Google")
    }

    func testFilterByStatus() {
        viewModel.createApplication(company: "Google", position: "SWE", location: "MV", appliedDate: Date())
        viewModel.setFilter(.applied)
        XCTAssertEqual(viewModel.filteredApplications.count, 1)
    }

    func testSearchByCompany() {
        viewModel.createApplication(company: "Google", position: "SWE", location: "MV", appliedDate: Date())
        viewModel.updateSearch("Google")
        XCTAssertEqual(viewModel.filteredApplications.count, 1)
        viewModel.updateSearch("Meta")
        XCTAssertEqual(viewModel.filteredApplications.count, 0)
    }
}
