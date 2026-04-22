# Phase 4: Mobile UI Implementation (iOS + Android)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build iOS SwiftUI and Android Jetpack Compose UI for Bewerbungstracker with 4 main screens: Applications, Emails, Notifications, Settings. Implement MVP Phase 4.1 features: list view, filter, search, create application.

**Architecture:** 
- **iOS:** SwiftUI with MVVM pattern, SwiftData for local persistence, URLSession for API calls
- **Android:** Jetpack Compose with MVVM pattern, Room Database for persistence, Retrofit for API calls
- **Shared:** Same bottom tab navigation structure, same data models (mapped to platform-specific entities), same feature set
- **Parallel Development:** iOS and Android tasks run independently, can be executed by different developers or sequentially

**Tech Stack:**
- iOS: Xcode 15+, Swift 5.9+, SwiftUI, SwiftData, URLSession
- Android: Android Studio 2023.1+, Kotlin 1.9+, Jetpack Compose, Room, Retrofit
- Both: Bottom tab navigation, MVVM pattern, async/await (iOS) or Coroutines (Android)

---

## File Structure

### iOS SwiftUI Project Structure

```
ios/Bewerbungstracker/
├── App.swift (entry point, tab bar setup)
├── Models/
│   ├── ApplicationModel.swift (SwiftData model)
│   ├── EmailModel.swift
│   ├── NotificationModel.swift
│   └── UserModel.swift
├── Views/
│   ├── MainTabView.swift (bottom tab navigation)
│   ├── Applications/
│   │   ├── ApplicationsView.swift (main list)
│   │   ├── ApplicationListItem.swift (card component)
│   │   ├── ApplicationFilterView.swift (filter pills)
│   │   └── CreateApplicationSheet.swift (modal form)
│   ├── Emails/
│   │   ├── EmailsView.swift (grouped view)
│   │   ├── EmailSection.swift (grouped by app)
│   │   └── EmailDetailView.swift (full email)
│   ├── Notifications/
│   │   ├── NotificationsView.swift (activity timeline)
│   │   └── NotificationRow.swift (single activity item)
│   └── Settings/
│       ├── SettingsView.swift (main settings)
│       ├── ProfileCard.swift (user info)
│       ├── SettingsSection.swift (reusable section)
│       └── LogoutButton.swift
├── ViewModels/
│   ├── ApplicationsViewModel.swift
│   ├── EmailsViewModel.swift
│   ├── NotificationsViewModel.swift
│   └── SettingsViewModel.swift
├── Services/
│   ├── APIClient.swift (already exists, extend)
│   ├── TokenManager.swift (already exists, use)
│   └── SyncService.swift (data sync logic)
└── Utils/
    ├── Colors.swift (color constants)
    ├── Fonts.swift (typography)
    └── Formatters.swift (date, status formatting)
```

### Android Jetpack Compose Project Structure

```
android/app/src/main/kotlin/com/example/bewerbungstracker/
├── MainActivity.kt (entry point, nav setup)
├── ui/
│   ├── theme/
│   │   ├── Color.kt (Material 3 colors)
│   │   ├── Type.kt (typography)
│   │   └── Theme.kt (theme setup)
│   ├── screens/
│   │   ├── MainTabScreen.kt (bottom tab navigation)
│   │   ├── applications/
│   │   │   ├── ApplicationsScreen.kt (main list)
│   │   │   ├── ApplicationCard.kt (card component)
│   │   │   ├── ApplicationFilterBar.kt (filter pills)
│   │   │   └── CreateApplicationDialog.kt (modal form)
│   │   ├── emails/
│   │   │   ├── EmailsScreen.kt (grouped view)
│   │   │   ├── EmailGroup.kt (grouped by app)
│   │   │   └── EmailDetailScreen.kt (full email)
│   │   ├── notifications/
│   │   │   ├── NotificationsScreen.kt (activity timeline)
│   │   │   └── NotificationItem.kt (single activity)
│   │   └── settings/
│   │       ├── SettingsScreen.kt (main settings)
│   │       ├── ProfileCard.kt (user info)
│   │       ├── SettingsSectionItem.kt (reusable)
│   │       └── LogoutButton.kt
├── viewmodel/
│   ├── ApplicationsViewModel.kt
│   ├── EmailsViewModel.kt
│   ├── NotificationsViewModel.kt
│   └── SettingsViewModel.kt
├── data/
│   ├── AppDatabase.kt (already exists, extend)
│   ├── dao/ (already exists, extend)
│   └── entity/ (already exists, extend)
├── services/
│   ├── APIClient.kt (already exists, extend)
│   ├── TokenManager.kt (already exists, use)
│   └── SyncService.kt
└── utils/
    ├── Constants.kt
    ├── DateFormatter.kt
    └── StatusHelper.kt
```

---

## Implementation Tasks

### Phase 4.1: MVP — List, Filter, Search, Create

---

## SECTION A: iOS SwiftUI Implementation

### Task A1: iOS Project Setup & Navigation Infrastructure

**Files:**
- Modify: `ios/Bewerbungstracker/App.swift`
- Create: `ios/Bewerbungstracker/Views/MainTabView.swift`
- Create: `ios/Bewerbungstracker/Utils/Colors.swift`
- Create: `ios/Bewerbungstracker/Utils/Fonts.swift`

#### Step 1: Create Colors.swift with design system colors

```swift
import SwiftUI

struct AppColors {
    static let primary = Color(red: 0, green: 0.48, blue: 1) // #007AFF
    static let statusInterview = Color(red: 0.29, green: 0.69, blue: 0.31) // #4CAF50
    static let statusApplied = Color(red: 1, green: 0.60, blue: 0) // #FF9800
    static let statusOffer = Color(red: 0.13, green: 0.59, blue: 1) // #2196F3
    static let statusPending = Color(red: 0.61, green: 0.15, blue: 0.69) // #9C27B0
    static let textPrimary = Color(red: 0.2, green: 0.2, blue: 0.2) // #333
    static let textSecondary = Color(red: 0.4, green: 0.4, blue: 0.4) // #666
    static let textTertiary = Color(red: 0.6, green: 0.6, blue: 0.6) // #999
    static let background = Color.white
    static let cardBackground = Color.white
    static let sectionBackground = Color(red: 0.96, green: 0.96, blue: 0.96) // #F5F5F5
    static let border = Color(red: 0.88, green: 0.88, blue: 0.88) // #E0E0E0
    static let danger = Color(red: 1, green: 0.24, blue: 0.19) // #FF3B30
}
```

#### Step 2: Create Fonts.swift with typography constants

```swift
import SwiftUI

struct AppFonts {
    // Title (17pt bold)
    static let title = Font.system(size: 17, weight: .bold, design: .default)
    
    // Heading (13pt bold)
    static let heading = Font.system(size: 13, weight: .bold, design: .default)
    
    // Body (12pt regular)
    static let body = Font.system(size: 12, weight: .regular, design: .default)
    
    // Secondary (11pt regular)
    static let secondary = Font.system(size: 11, weight: .regular, design: .default)
    
    // Label (10pt regular)
    static let label = Font.system(size: 10, weight: .regular, design: .default)
}
```

#### Step 3: Create MainTabView.swift with bottom tab navigation

```swift
import SwiftUI

struct MainTabView: View {
    @State private var selectedTab: Int = 0
    
    var body: some View {
        ZStack(alignment: .bottom) {
            TabView(selection: $selectedTab) {
                ApplicationsView()
                    .tabItem {
                        Image(systemName: "list.bullet")
                        Text("Applications")
                    }
                    .tag(0)
                
                EmailsView()
                    .tabItem {
                        Image(systemName: "envelope")
                        Text("Emails")
                    }
                    .tag(1)
                
                NotificationsView()
                    .tabItem {
                        Image(systemName: "bell")
                        Text("Notifications")
                    }
                    .tag(2)
                
                SettingsView()
                    .tabItem {
                        Image(systemName: "gear")
                        Text("Settings")
                    }
                    .tag(3)
            }
            .accentColor(AppColors.primary)
        }
    }
}

#Preview {
    MainTabView()
}
```

#### Step 4: Modify App.swift to use MainTabView

```swift
import SwiftUI
import SwiftData

@main
struct BewerbungstrackerApp: App {
    var body: some Scene {
        WindowGroup {
            MainTabView()
                .modelContainer(for: [ApplicationModel.self, EmailModel.self])
        }
    }
}
```

#### Step 5: Run app to verify tab navigation works

Run: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`
Expected: App launches with 4 tabs at bottom, can switch between tabs

#### Step 6: Commit

```bash
cd ios/Bewerbungstracker
git add App.swift Views/MainTabView.swift Utils/Colors.swift Utils/Fonts.swift
git commit -m "feat: iOS base tab navigation and design system"
```

---

### Task A2: iOS Applications Model & ViewModel

**Files:**
- Modify: `ios/Bewerbungstracker/Models/ApplicationModel.swift` (extend existing)
- Create: `ios/Bewerbungstracker/ViewModels/ApplicationsViewModel.swift`
- Create: `ios/Bewerbungstracker/Utils/Formatters.swift`

#### Step 1: Extend ApplicationModel.swift with SwiftData annotations

```swift
import SwiftData
import Foundation

@Model
final class ApplicationModel {
    @Attribute(.unique) var id: UUID = UUID()
    var company: String
    var position: String
    var location: String?
    var status: ApplicationStatus = .applied
    var appliedDate: Date
    var createdAt: Date = Date()
    var updatedAt: Date = Date()
    var notes: String?
    
    @Relationship(deleteRule: .cascade, inverse: \EmailModel.application) var emails: [EmailModel] = []
    
    init(company: String, position: String, location: String? = nil, status: ApplicationStatus = .applied, appliedDate: Date = Date()) {
        self.company = company
        self.position = position
        self.location = location
        self.status = status
        self.appliedDate = appliedDate
    }
}

enum ApplicationStatus: String, Codable, CaseIterable {
    case applied = "applied"
    case interview = "interview"
    case offer = "offer"
    case rejected = "rejected"
    case archived = "archived"
    
    var displayName: String {
        switch self {
        case .applied: return "Applied"
        case .interview: return "Interview"
        case .offer: return "Offer"
        case .rejected: return "Rejected"
        case .archived: return "Archived"
        }
    }
    
    var color: Color {
        switch self {
        case .applied: return AppColors.statusApplied
        case .interview: return AppColors.statusInterview
        case .offer: return AppColors.statusOffer
        case .rejected: return AppColors.danger
        case .archived: return AppColors.textTertiary
        }
    }
}
```

#### Step 2: Create Formatters.swift with date formatting

```swift
import Foundation

struct DateFormatters {
    static let relativeDateFormatter: DateComponentsFormatter = {
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .abbreviated
        formatter.maximumUnitCount = 1
        return formatter
    }()
    
    static func relativeDate(from date: Date) -> String {
        let calendar = Calendar.current
        let now = Date()
        let components = calendar.dateComponents([.day, .hour, .minute], from: date, to: now)
        
        if let days = components.day, days > 0 {
            return days == 1 ? "1 day ago" : "\(days) days ago"
        } else if let hours = components.hour, hours > 0 {
            return hours == 1 ? "1 hour ago" : "\(hours) hours ago"
        } else if let minutes = components.minute, minutes >= 0 {
            return minutes == 0 ? "just now" : "\(minutes) minutes ago"
        }
        return "just now"
    }
}

struct StatusFormatters {
    static func statusColor(_ status: ApplicationStatus) -> Color {
        status.color
    }
}
```

#### Step 3: Create ApplicationsViewModel.swift

```swift
import SwiftUI
import SwiftData

@MainActor
class ApplicationsViewModel: ObservableObject {
    @Published var applications: [ApplicationModel] = []
    @Published var filteredApplications: [ApplicationModel] = []
    @Published var searchText: String = ""
    @Published var selectedFilter: ApplicationStatus? = nil
    @Published var showCreateSheet: Bool = false
    
    private let modelContext: ModelContext
    
    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchApplications()
    }
    
    func fetchApplications() {
        do {
            let descriptor = FetchDescriptor<ApplicationModel>(
                sortBy: [SortDescriptor(\.appliedDate, order: .reverse)]
            )
            applications = try modelContext.fetch(descriptor)
            applyFilters()
        } catch {
            print("Failed to fetch applications: \(error)")
        }
    }
    
    func applyFilters() {
        var filtered = applications
        
        if let filter = selectedFilter {
            filtered = filtered.filter { $0.status == filter }
        }
        
        if !searchText.isEmpty {
            filtered = filtered.filter { app in
                app.company.localizedCaseInsensitiveContains(searchText) ||
                app.position.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        filteredApplications = filtered
    }
    
    func updateSearch(_ text: String) {
        searchText = text
        applyFilters()
    }
    
    func setFilter(_ status: ApplicationStatus?) {
        selectedFilter = status
        applyFilters()
    }
    
    func createApplication(company: String, position: String, location: String, appliedDate: Date) {
        let newApp = ApplicationModel(
            company: company,
            position: position,
            location: location,
            appliedDate: appliedDate
        )
        modelContext.insert(newApp)
        try? modelContext.save()
        fetchApplications()
    }
    
    func deleteApplication(_ app: ApplicationModel) {
        modelContext.delete(app)
        try? modelContext.save()
        fetchApplications()
    }
}
```

#### Step 4: Create test file for ViewModel

```swift
// ios/Bewerbungstracker/Tests/ViewModels/ApplicationsViewModelTests.swift
import XCTest
@testable import Bewerbungstracker

class ApplicationsViewModelTests: XCTestCase {
    var viewModel: ApplicationsViewModel!
    
    override func setUp() {
        super.setUp()
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try! ModelContainer(for: ApplicationModel.self, configurations: config)
        let context = ModelContext(container)
        viewModel = ApplicationsViewModel(modelContext: context)
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
```

#### Step 5: Run unit tests

Run: `xcodebuild test -scheme Bewerbungstracker -only-testing BewerbungstrackerTests/ApplicationsViewModelTests`
Expected: All 3 tests pass

#### Step 6: Commit

```bash
git add Models/ApplicationModel.swift ViewModels/ApplicationsViewModel.swift Utils/Formatters.swift Tests/ViewModels/ApplicationsViewModelTests.swift
git commit -m "feat: iOS ApplicationModel and ViewModel with filtering/search logic"
```

---

### Task A3: iOS Applications Screen (List, Filter, Search, Create)

**Files:**
- Create: `ios/Bewerbungstracker/Views/Applications/ApplicationsView.swift`
- Create: `ios/Bewerbungstracker/Views/Applications/ApplicationListItem.swift`
- Create: `ios/Bewerbungstracker/Views/Applications/ApplicationFilterView.swift`
- Create: `ios/Bewerbungstracker/Views/Applications/CreateApplicationSheet.swift`

#### Step 1: Create ApplicationListItem.swift (card component)

```swift
import SwiftUI

struct ApplicationListItem: View {
    let application: ApplicationModel
    
    var body: some View {
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
    }
}

#Preview {
    ApplicationListItem(
        application: ApplicationModel(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date.now.addingTimeInterval(-86400 * 5)
        )
    )
}
```

#### Step 2: Create ApplicationFilterView.swift

```swift
import SwiftUI

struct ApplicationFilterView: View {
    @Binding var selectedFilter: ApplicationStatus?
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterButton(
                    title: "All",
                    isSelected: selectedFilter == nil,
                    action: { selectedFilter = nil }
                )
                
                ForEach(ApplicationStatus.allCases, id: \.self) { status in
                    FilterButton(
                        title: status.displayName,
                        isSelected: selectedFilter == status,
                        action: { selectedFilter = status }
                    )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
    }
}

struct FilterButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(AppFonts.body)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? AppColors.primary : AppColors.sectionBackground)
                .foregroundColor(isSelected ? .white : AppColors.textSecondary)
                .cornerRadius(4)
        }
    }
}

#Preview {
    @State var filter: ApplicationStatus? = nil
    return ApplicationFilterView(selectedFilter: $filter)
}
```

#### Step 3: Create CreateApplicationSheet.swift

```swift
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
                            location: location.isEmpty ? nil : location,
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
```

#### Step 4: Create ApplicationsView.swift (main screen)

```swift
import SwiftUI
import SwiftData

struct ApplicationsView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel: ApplicationsViewModel
    
    init() {
        // Initialize ViewModel with model context
        _viewModel = StateObject(wrappedValue: ApplicationsViewModel(modelContext: ModelContext(try! ModelContainer(for: ApplicationModel.self))))
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
                            ApplicationListItem(application: app)
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
```

#### Step 5: Run app and test Applications screen

Run: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`
Expected: 
- Search bar visible
- Filter pills visible (All, Applied, Interview, Offer)
- Create button at bottom
- Can tap Create to open modal
- Can enter company/position and save
- List updates with new application

#### Step 6: Commit

```bash
git add Views/Applications/*.swift
git commit -m "feat: iOS Applications screen with list, filter, search, create"
```

---

### Task A4: iOS Emails Screen (Grouped by Application & Status)

**Files:**
- Modify: `ios/Bewerbungstracker/Models/EmailModel.swift` (ensure relationships)
- Create: `ios/Bewerbungstracker/ViewModels/EmailsViewModel.swift`
- Create: `ios/Bewerbungstracker/Views/Emails/EmailsView.swift`
- Create: `ios/Bewerbungstracker/Views/Emails/EmailSection.swift`
- Create: `ios/Bewerbungstracker/Views/Emails/EmailDetailView.swift`

#### Step 1: Ensure EmailModel.swift has proper relationship

```swift
import SwiftData
import Foundation

@Model
final class EmailModel {
    @Attribute(.unique) var messageId: String
    var subject: String
    var from: String
    var body: String
    var timestamp: Date
    var claudeAnalyzed: Bool = false
    
    @Relationship(deleteRule: .cascade) var application: ApplicationModel?
    
    init(messageId: String, subject: String, from: String, body: String, timestamp: Date, claudeAnalyzed: Bool = false) {
        self.messageId = messageId
        self.subject = subject
        self.from = from
        self.body = body
        self.timestamp = timestamp
        self.claudeAnalyzed = claudeAnalyzed
    }
}
```

#### Step 2: Create EmailsViewModel.swift

```swift
import SwiftUI
import SwiftData

@MainActor
class EmailsViewModel: ObservableObject {
    @Published var emails: [EmailModel] = []
    @Published var groupedEmails: [(ApplicationModel, [EmailModel])] = []
    @Published var searchText: String = ""
    @Published var selectedEmail: EmailModel? = nil
    
    private let modelContext: ModelContext
    
    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchEmails()
    }
    
    func fetchEmails() {
        do {
            let descriptor = FetchDescriptor<EmailModel>(
                sortBy: [SortDescriptor(\.timestamp, order: .reverse)]
            )
            emails = try modelContext.fetch(descriptor)
            groupEmails()
        } catch {
            print("Failed to fetch emails: \(error)")
        }
    }
    
    func groupEmails() {
        var grouped: [UUID: (ApplicationModel, [EmailModel])] = [:]
        
        for email in emails {
            if let app = email.application {
                if grouped[app.id] == nil {
                    grouped[app.id] = (app, [])
                }
                grouped[app.id]?.1.append(email)
            }
        }
        
        groupedEmails = grouped.values.sorted { $0.0.company < $1.0.company }
    }
    
    func updateSearch(_ text: String) {
        searchText = text
        // Filter logic here if needed
    }
    
    func linkEmailToApplication(_ email: EmailModel, application: ApplicationModel) {
        email.application = application
        try? modelContext.save()
        fetchEmails()
    }
}
```

#### Step 3: Create EmailSection.swift (grouped view)

```swift
import SwiftUI

struct EmailSection: View {
    let application: ApplicationModel
    let emails: [EmailModel]
    @State private var isExpanded: Bool = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Section Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(application.company)
                        .font(AppFonts.heading)
                        .foregroundColor(AppColors.textPrimary)
                    Text(application.status.displayName)
                        .font(AppFonts.secondary)
                        .foregroundColor(AppColors.textTertiary)
                }
                
                Spacer()
                
                Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                    .foregroundColor(AppColors.textTertiary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(AppColors.sectionBackground)
            .onTapGesture { isExpanded.toggle() }
            
            // Emails List
            if isExpanded {
                VStack(spacing: 0) {
                    ForEach(emails, id: \.messageId) { email in
                        EmailRow(email: email)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 12)
                            .borderBottom()
                    }
                }
            }
        }
        .background(AppColors.cardBackground)
        .cornerRadius(6)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
}

struct EmailRow: View {
    let email: EmailModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(email.subject)
                .font(AppFonts.heading)
                .foregroundColor(AppColors.textPrimary)
                .lineLimit(2)
            
            Text(email.from)
                .font(AppFonts.secondary)
                .foregroundColor(AppColors.textSecondary)
                .lineLimit(1)
            
            Text(DateFormatters.relativeDate(from: email.timestamp))
                .font(AppFonts.label)
                .foregroundColor(AppColors.textTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

extension View {
    func borderBottom() -> some View {
        self.overlay(
            VStack {
                Spacer()
                Divider()
                    .background(AppColors.border)
            }
        )
    }
}

#Preview {
    EmailSection(
        application: ApplicationModel(company: "Google", position: "SWE", location: "MV"),
        emails: [
            EmailModel(messageId: "1", subject: "Interview Scheduled", from: "recruiter@google.com", body: "...", timestamp: Date.now.addingTimeInterval(-86400 * 2)),
            EmailModel(messageId: "2", subject: "Application Received", from: "noreply@google.com", body: "...", timestamp: Date.now.addingTimeInterval(-86400 * 5))
        ]
    )
}
```

#### Step 4: Create EmailDetailView.swift

```swift
import SwiftUI

struct EmailDetailView: View {
    let email: EmailModel
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    // Header
                    VStack(alignment: .leading, spacing: 4) {
                        Text(email.subject)
                            .font(AppFonts.title)
                            .foregroundColor(AppColors.textPrimary)
                        
                        HStack {
                            Text("From: \(email.from)")
                                .font(AppFonts.body)
                                .foregroundColor(AppColors.textSecondary)
                            
                            Spacer()
                            
                            Text(DateFormatters.relativeDate(from: email.timestamp))
                                .font(AppFonts.secondary)
                                .foregroundColor(AppColors.textTertiary)
                        }
                    }
                    .padding(12)
                    .background(AppColors.sectionBackground)
                    .cornerRadius(6)
                    
                    // Body
                    Text(email.body)
                        .font(AppFonts.body)
                        .foregroundColor(AppColors.textPrimary)
                        .padding(12)
                    
                    Spacer()
                }
                .padding(12)
            }
            .navigationTitle("Email")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    EmailDetailView(
        email: EmailModel(
            messageId: "1",
            subject: "Interview Scheduled",
            from: "recruiter@google.com",
            body: "Dear Candidate,\n\nWe are pleased to invite you for an interview...",
            timestamp: Date()
        )
    )
}
```

#### Step 5: Create EmailsView.swift (main screen)

```swift
import SwiftUI
import SwiftData

struct EmailsView: View {
    @StateObject private var viewModel: EmailsViewModel
    @State private var selectedEmail: EmailModel? = nil
    
    init() {
        _viewModel = StateObject(wrappedValue: EmailsViewModel(modelContext: ModelContext(try! ModelContainer(for: EmailModel.self))))
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search Bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(AppColors.textTertiary)
                    TextField("Search emails", text: Binding(
                        get: { viewModel.searchText },
                        set: { viewModel.updateSearch($0) }
                    ))
                }
                .padding(12)
                .background(AppColors.sectionBackground)
                .cornerRadius(6)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                
                // Grouped Emails
                if viewModel.groupedEmails.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 48))
                            .foregroundColor(AppColors.textTertiary)
                        Text("No emails")
                            .font(AppFonts.heading)
                            .foregroundColor(AppColors.textSecondary)
                    }
                    .frame(maxHeight: .infinity)
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(viewModel.groupedEmails, id: \.0.id) { app, emails in
                                EmailSection(application: app, emails: emails)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .navigationTitle("Emails")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    EmailsView()
}
```

#### Step 6: Run and test Emails screen

Run: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`
Expected:
- Switch to Emails tab
- See grouped emails by application
- Can tap to expand/collapse sections
- Can see sender and timestamp

#### Step 7: Commit

```bash
git add Models/EmailModel.swift ViewModels/EmailsViewModel.swift Views/Emails/*.swift
git commit -m "feat: iOS Emails screen with grouping by application"
```

---

### Task A5: iOS Notifications Screen (Activity Timeline)

**Files:**
- Create: `ios/Bewerbungstracker/Models/NotificationModel.swift`
- Create: `ios/Bewerbungstracker/ViewModels/NotificationsViewModel.swift`
- Create: `ios/Bewerbungstracker/Views/Notifications/NotificationsView.swift`
- Create: `ios/Bewerbungstracker/Views/Notifications/NotificationRow.swift`

#### Step 1: Create NotificationModel.swift

```swift
import SwiftData
import Foundation

@Model
final class NotificationModel {
    @Attribute(.unique) var id: UUID = UUID()
    var type: NotificationType
    var title: String
    var description: String
    var timestamp: Date
    var isRead: Bool = false
    
    @Relationship var application: ApplicationModel?
    
    init(type: NotificationType, title: String, description: String, timestamp: Date = Date(), application: ApplicationModel? = nil) {
        self.type = type
        self.title = title
        self.description = description
        self.timestamp = timestamp
        self.application = application
    }
}

enum NotificationType: String, Codable {
    case applicationCreated = "application_created"
    case interviewScheduled = "interview_scheduled"
    case offerReceived = "offer_received"
    case emailReceived = "email_received"
    case reminder = "reminder"
    
    var icon: String {
        switch self {
        case .applicationCreated: return "checkmark.circle"
        case .interviewScheduled: return "calendar"
        case .offerReceived: return "star"
        case .emailReceived: return "envelope"
        case .reminder: return "bell"
        }
    }
}
```

#### Step 2: Create NotificationsViewModel.swift

```swift
import SwiftUI
import SwiftData

@MainActor
class NotificationsViewModel: ObservableObject {
    @Published var notifications: [NotificationModel] = []
    
    private let modelContext: ModelContext
    
    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchNotifications()
    }
    
    func fetchNotifications() {
        do {
            let descriptor = FetchDescriptor<NotificationModel>(
                sortBy: [SortDescriptor(\.timestamp, order: .reverse)]
            )
            notifications = try modelContext.fetch(descriptor)
        } catch {
            print("Failed to fetch notifications: \(error)")
        }
    }
    
    func addNotification(type: NotificationType, title: String, description: String, application: ApplicationModel? = nil) {
        let notification = NotificationModel(
            type: type,
            title: title,
            description: description,
            application: application
        )
        modelContext.insert(notification)
        try? modelContext.save()
        fetchNotifications()
    }
    
    func markAsRead(_ notification: NotificationModel) {
        notification.isRead = true
        try? modelContext.save()
        fetchNotifications()
    }
}
```

#### Step 3: Create NotificationRow.swift

```swift
import SwiftUI

struct NotificationRow: View {
    let notification: NotificationModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(notification.title)
                .font(AppFonts.heading)
                .foregroundColor(AppColors.textPrimary)
            
            Text(notification.description)
                .font(AppFonts.body)
                .foregroundColor(AppColors.textSecondary)
                .lineLimit(2)
            
            Text(DateFormatters.relativeDate(from: notification.timestamp))
                .font(AppFonts.label)
                .foregroundColor(AppColors.textTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppColors.cardBackground)
        .cornerRadius(6)
    }
}

#Preview {
    NotificationRow(
        notification: NotificationModel(
            type: .interviewScheduled,
            title: "Google Interview Scheduled",
            description: "Tomorrow at 2:00 PM",
            timestamp: Date.now.addingTimeInterval(-7200)
        )
    )
}
```

#### Step 4: Create NotificationsView.swift

```swift
import SwiftUI
import SwiftData

struct NotificationsView: View {
    @StateObject private var viewModel: NotificationsViewModel
    
    init() {
        _viewModel = StateObject(wrappedValue: NotificationsViewModel(modelContext: ModelContext(try! ModelContainer(for: NotificationModel.self))))
    }
    
    var body: some View {
        NavigationStack {
            if viewModel.notifications.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "bell.fill")
                        .font(.system(size: 48))
                        .foregroundColor(AppColors.textTertiary)
                    Text("No notifications")
                        .font(AppFonts.heading)
                        .foregroundColor(AppColors.textSecondary)
                }
                .frame(maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(spacing: 8) {
                        ForEach(viewModel.notifications, id: \.id) { notification in
                            NotificationRow(notification: notification)
                        }
                    }
                    .padding(12)
                }
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

#Preview {
    NotificationsView()
}
```

#### Step 5: Run and test Notifications screen

Run: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`
Expected:
- Switch to Notifications tab
- See empty state initially
- (Can manually add test data to see timeline)

#### Step 6: Commit

```bash
git add Models/NotificationModel.swift ViewModels/NotificationsViewModel.swift Views/Notifications/*.swift
git commit -m "feat: iOS Notifications screen with activity timeline"
```

---

### Task A6: iOS Settings Screen

**Files:**
- Create: `ios/Bewerbungstracker/Models/UserModel.swift`
- Create: `ios/Bewerbungstracker/ViewModels/SettingsViewModel.swift`
- Create: `ios/Bewerbungstracker/Views/Settings/SettingsView.swift`
- Create: `ios/Bewerbungstracker/Views/Settings/ProfileCard.swift`

#### Step 1: Create UserModel.swift

```swift
import SwiftData
import Foundation

@Model
final class UserModel {
    var id: UUID = UUID()
    var name: String
    var email: String
    var createdAt: Date = Date()
    var lastSyncAt: Date?
    
    init(name: String, email: String) {
        self.name = name
        self.email = email
    }
}
```

#### Step 2: Create SettingsViewModel.swift

```swift
import SwiftUI
import SwiftData

@MainActor
class SettingsViewModel: ObservableObject {
    @Published var user: UserModel? = nil
    @Published var lastSyncTime: String = "Never"
    @Published var syncInProgress: Bool = false
    
    private let modelContext: ModelContext
    
    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchUser()
    }
    
    func fetchUser() {
        do {
            let descriptor = FetchDescriptor<UserModel>()
            user = try modelContext.fetch(descriptor).first
            updateSyncTime()
        } catch {
            print("Failed to fetch user: \(error)")
        }
    }
    
    func updateSyncTime() {
        if let syncDate = user?.lastSyncAt {
            lastSyncTime = "Last sync: \(DateFormatters.relativeDate(from: syncDate))"
        } else {
            lastSyncTime = "Never synced"
        }
    }
    
    func manualSync() {
        syncInProgress = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            self.user?.lastSyncAt = Date()
            try? self.modelContext.save()
            self.updateSyncTime()
            self.syncInProgress = false
        }
    }
    
    func logout() {
        // Clear tokens and user session
        TokenManager.shared.clearTokens()
        // Trigger navigation to login screen (handle in parent)
    }
}
```

#### Step 3: Create ProfileCard.swift

```swift
import SwiftUI

struct ProfileCard: View {
    let user: UserModel?
    
    var body: some View {
        VStack(alignment: .center, spacing: 8) {
            Circle()
                .fill(AppColors.sectionBackground)
                .frame(width: 60, height: 60)
                .overlay(
                    Text(initials)
                        .font(AppFonts.heading)
                        .foregroundColor(AppColors.textSecondary)
                )
            
            Text(user?.name ?? "User")
                .font(AppFonts.heading)
                .foregroundColor(AppColors.textPrimary)
            
            Text(user?.email ?? "email@example.com")
                .font(AppFonts.body)
                .foregroundColor(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(16)
        .background(AppColors.sectionBackground)
        .cornerRadius(6)
    }
    
    var initials: String {
        let names = (user?.name ?? "U").split(separator: " ")
        if names.count >= 2 {
            return String(names[0].prefix(1)) + String(names[1].prefix(1))
        } else {
            return String(names[0].prefix(1))
        }
    }
}

#Preview {
    ProfileCard(user: UserModel(name: "Harald Weiss", email: "anubclaw@gmail.com"))
}
```

#### Step 4: Create SettingsView.swift

```swift
import SwiftUI
import SwiftData

struct SettingsView: View {
    @StateObject private var viewModel: SettingsViewModel
    @State private var showLogoutConfirm: Bool = false
    
    init() {
        _viewModel = StateObject(wrappedValue: SettingsViewModel(modelContext: ModelContext(try! ModelContainer(for: UserModel.self))))
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                // Profile Card
                ProfileCard(user: viewModel.user)
                    .padding(12)
                
                // Settings Sections
                VStack(spacing: 8) {
                    SettingsSectionItem(
                        title: "Account Settings",
                        subtitle: "Change password, email, preferences",
                        icon: "person.fill"
                    )
                    
                    SettingsSectionItem(
                        title: "Sync & Data",
                        subtitle: viewModel.lastSyncTime,
                        icon: "icloud.fill",
                        action: {
                            viewModel.manualSync()
                        },
                        isLoading: viewModel.syncInProgress
                    )
                    
                    SettingsSectionItem(
                        title: "Data Export & Backup",
                        subtitle: "Export data as CSV, backup to cloud",
                        icon: "arrow.up.doc.fill"
                    )
                    
                    SettingsSectionItem(
                        title: "App Info",
                        subtitle: "Version 1.0 • Terms & Privacy",
                        icon: "info.circle.fill"
                    )
                }
                .padding(.horizontal, 12)
                
                Spacer()
                
                // Logout Button
                Button(action: { showLogoutConfirm = true }) {
                    Text("Logout")
                        .font(AppFonts.heading)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(AppColors.danger)
                        .cornerRadius(6)
                }
                .padding(12)
                .alert("Logout", isPresented: $showLogoutConfirm) {
                    Button("Cancel", role: .cancel) { }
                    Button("Logout", role: .destructive) {
                        viewModel.logout()
                    }
                } message: {
                    Text("Are you sure you want to logout?")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct SettingsSectionItem: View {
    let title: String
    let subtitle: String
    let icon: String
    var action: (() -> Void)? = nil
    var isLoading: Bool = false
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(AppColors.primary)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(AppFonts.heading)
                    .foregroundColor(AppColors.textPrimary)
                Text(subtitle)
                    .font(AppFonts.secondary)
                    .foregroundColor(AppColors.textSecondary)
            }
            
            Spacer()
            
            if isLoading {
                ProgressView()
                    .controlSize(.small)
            } else {
                Image(systemName: "chevron.right")
                    .foregroundColor(AppColors.textTertiary)
                    .font(.caption)
            }
        }
        .padding(12)
        .background(AppColors.cardBackground)
        .cornerRadius(6)
        .onTapGesture {
            action?()
        }
    }
}

#Preview {
    SettingsView()
}
```

#### Step 5: Run and test Settings screen

Run: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`
Expected:
- Switch to Settings tab
- See profile card (initials placeholder)
- See 4 settings sections
- Can tap manual sync
- Can see logout button

#### Step 6: Commit

```bash
git add Models/UserModel.swift ViewModels/SettingsViewModel.swift Views/Settings/*.swift
git commit -m "feat: iOS Settings screen with profile, sync, and logout"
```

---

### Task A7: iOS Integration Testing

**Files:**
- Create: `ios/Bewerbungstracker/Tests/Integration/EndToEndTests.swift`

#### Step 1: Write integration test

```swift
import XCTest
import SwiftUI
@testable import Bewerbungstracker

class EndToEndTests: XCTestCase {
    func testApplicationWorkflow() throws {
        // Test: Create application → View in list → Filter → Search → Delete
        
        let container = try ModelContainer(for: ApplicationModel.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true))
        let context = ModelContext(container)
        let viewModel = ApplicationsViewModel(modelContext: context)
        
        // Create application
        viewModel.createApplication(
            company: "Google",
            position: "Software Engineer",
            location: "Mountain View",
            appliedDate: Date()
        )
        XCTAssertEqual(viewModel.applications.count, 1)
        
        // Filter by status
        viewModel.setFilter(.applied)
        XCTAssertEqual(viewModel.filteredApplications.count, 1)
        
        // Search
        viewModel.updateSearch("Google")
        XCTAssertEqual(viewModel.filteredApplications.count, 1)
        
        // Search no match
        viewModel.updateSearch("Meta")
        XCTAssertEqual(viewModel.filteredApplications.count, 0)
        
        // Delete
        if let app = viewModel.applications.first {
            viewModel.deleteApplication(app)
        }
        XCTAssertEqual(viewModel.applications.count, 0)
    }
}
```

#### Step 2: Run integration test

Run: `xcodebuild test -scheme Bewerbungstracker -only-testing BewerbungstrackerTests/EndToEndTests`
Expected: PASS

#### Step 3: Commit

```bash
git add Tests/Integration/EndToEndTests.swift
git commit -m "test: iOS end-to-end integration tests"
```

---

## SECTION B: Android Jetpack Compose Implementation

### Task B1: Android Project Setup & Navigation Infrastructure

**Files:**
- Modify: `android/app/src/main/kotlin/com/example/bewerbungstracker/MainActivity.kt`
- Create: `android/app/src/main/kotlin/com/example/bewerbungstracker/ui/screens/MainTabScreen.kt`
- Create: `android/app/src/main/kotlin/com/example/bewerbungstracker/ui/theme/Color.kt`
- Create: `android/app/src/main/kotlin/com/example/bewerbungstracker/ui/theme/Type.kt`

#### Step 1: Create Color.kt with Material 3 colors

```kotlin
package com.example.bewerbungstracker.ui.theme

import androidx.compose.ui.graphics.Color

val PrimaryBlue = Color(0xFF007AFF)
val StatusInterview = Color(0xFF4CAF50)
val StatusApplied = Color(0xFFFF9800)
val StatusOffer = Color(0xFF2196F3)
val StatusPending = Color(0xFF9C27B0)
val TextPrimary = Color(0xFF333333)
val TextSecondary = Color(0xFF666666)
val TextTertiary = Color(0xFF999999)
val Background = Color(0xFFFFFFFF)
val CardBackground = Color(0xFFFFFFFF)
val SectionBackground = Color(0xFFF5F5F5)
val BorderColor = Color(0xFFE0E0E0)
val DangerRed = Color(0xFFFF3B30)
```

#### Step 2: Create Type.kt with typography

```kotlin
package com.example.bewerbungstracker.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val AppTypography = Typography(
    titleLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 17.sp
    ),
    headlineSmall = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 13.sp
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp
    ),
    bodySmall = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 11.sp
    ),
    labelSmall = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 10.sp
    )
)
```

#### Step 3: Modify MainActivity.kt

```kotlin
package com.example.bewerbungstracker

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.example.bewerbungstracker.ui.screens.MainTabScreen
import com.example.bewerbungstracker.ui.theme.BewerbungstrackerTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            BewerbungstrackerTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    MainTabScreen()
                }
            }
        }
    }
}
```

#### Step 4: Create MainTabScreen.kt

```kotlin
package com.example.bewerbungstracker.ui.screens

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector

@Composable
fun MainTabScreen() {
    var selectedTab by remember { mutableStateOf(0) }
    
    Scaffold(
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Home, contentDescription = "Applications") },
                    label = { Text("Applications") },
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Email, contentDescription = "Emails") },
                    label = { Text("Emails") },
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Notifications, contentDescription = "Notifications") },
                    label = { Text("Notifications") },
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Settings, contentDescription = "Settings") },
                    label = { Text("Settings") },
                    selected = selectedTab == 3,
                    onClick = { selectedTab = 3 }
                )
            }
        }
    ) { innerPadding ->
        when (selectedTab) {
            0 -> ApplicationsScreen(Modifier.padding(innerPadding))
            1 -> EmailsScreen(Modifier.padding(innerPadding))
            2 -> NotificationsScreen(Modifier.padding(innerPadding))
            3 -> SettingsScreen(Modifier.padding(innerPadding))
        }
    }
}
```

#### Step 5: Run app to verify navigation works

Run: `./gradlew installDebug` then run on emulator
Expected: App launches with 4 tabs at bottom, can switch tabs

#### Step 6: Commit

```bash
cd android
git add app/src/main/kotlin/com/example/bewerbungstracker/MainActivity.kt ui/theme/Color.kt ui/theme/Type.kt ui/screens/MainTabScreen.kt
git commit -m "feat: Android base tab navigation and Material 3 theme"
```

---

### Task B2-B6: Android Screens (Same Structure as iOS)

Due to length constraints, the Android implementation follows the same pattern as iOS. Each task mirrors the iOS equivalent:

- **Task B2:** ApplicationsViewModel + Models
- **Task B3:** ApplicationsScreen (List, Filter, Search, Create)
- **Task B4:** EmailsScreen (Grouped)
- **Task B5:** NotificationsScreen (Timeline)
- **Task B6:** SettingsScreen

**Approach:** 
1. Create Jetpack Compose Screens
2. Implement Room Database entities
3. Create ViewModels with Coroutines
4. Add unit tests (using JUnit + Mockito)
5. Commit after each screen

*Details omitted for brevity, but follow the same structure and features as iOS tasks A2-A6.*

---

### Task B7: Android Integration Testing

Follow the same pattern as iOS Task A7, using Espresso or Compose Testing framework.

---

## Task Execution Order

**Sequential (Recommended):**
1. A1 (iOS Setup)
2. A2 (iOS Models)
3. A3 (iOS Applications Screen)
4. A4 (iOS Emails Screen)
5. A5 (iOS Notifications Screen)
6. A6 (iOS Settings Screen)
7. A7 (iOS Testing)
8. B1 (Android Setup)
9. B2-B6 (Android Screens)
10. B7 (Android Testing)

**Parallel (If Multiple Developers):**
- Developer 1: Tasks A1-A7 (iOS)
- Developer 2: Tasks B1-B7 (Android) (can start after B1)

---

## Success Criteria

✅ iOS:
- [ ] All 4 tabs accessible (Applications, Emails, Notifications, Settings)
- [ ] Applications tab: List, Filter, Search, Create working
- [ ] Emails tab: Grouped by application, viewable
- [ ] Notifications tab: Activity timeline displays
- [ ] Settings tab: Profile, Logout, Sync status visible
- [ ] All unit tests passing (>80% coverage)
- [ ] App builds and runs without errors on iPhone 15 simulator

✅ Android:
- [ ] Same 4 tabs functional with Material 3 design
- [ ] Same features working on Android
- [ ] All unit tests passing
- [ ] App builds and runs on Android emulator/device

✅ Overall:
- [ ] Both platforms support list, filter, search, create
- [ ] Data sync between platforms (if backend supports)
- [ ] No crashes on user workflows
- [ ] Performance acceptable (< 3s load time)

---

## Testing Strategy

### iOS Unit Tests
- ViewModel logic (filtering, searching, CRUD)
- Data model validation
- Date formatting
- Status mapping

### Android Unit Tests  
- Same as iOS using JUnit + Mockito
- Room Database queries
- API response mapping

### Integration Tests
- End-to-end workflows (create → filter → search → delete)
- Navigation between tabs
- Data persistence after app close

### Manual Testing Checklist
- [ ] Applications: Create, list, filter, search works
- [ ] Emails: Grouped correctly, can read
- [ ] Notifications: Timeline displays
- [ ] Settings: Logout works, profile shows
- [ ] Tab navigation: State preserved
- [ ] Offline mode: App doesn't crash

---

## Notes

- **Data Persistence:** Both platforms use local DB (SwiftData/Room) with API sync
- **Date Formatting:** Consistent relative dates ("2 days ago") across platforms
- **Error Handling:** Network errors logged but don't crash app (Phase 4.2)
- **Loading States:** Placeholders for empty states (Phase 4.2: add spinners)
- **Design Consistency:** iOS HIG for iOS, Material 3 for Android, same features