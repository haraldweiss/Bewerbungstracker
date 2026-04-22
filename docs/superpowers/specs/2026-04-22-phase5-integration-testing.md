# Phase 5: iOS Integration Testing Design Specification

**Date:** 2026-04-22  
**Status:** Design  
**Scope:** iOS mobile app integration testing with mocked API  
**Platform:** iOS only (Phase 5.1)  
**Test Framework:** XCTest + Mock API Client  

---

## 1. Overview

Phase 5 validates that the iOS Bewerbungstracker app correctly integrates with backend API endpoints. Rather than requiring a running backend server, Phase 5 uses **mocked API responses** to test all networking logic, data parsing, and UI updates in isolation.

**Key Benefit:** Fast iteration without backend setup; validates app works correctly with realistic API responses before integrating with real backend in Phase 6.

---

## 2. Architecture

### 2.1 Mock API Client Strategy

The iOS app currently uses a real `APIClient` for networking (URLSession-based). Phase 5 introduces a **protocol-based design** to swap implementations:

```swift
protocol APIClientProtocol {
    func register(email: String, password: String) async throws -> AuthResponse
    func login(email: String, password: String) async throws -> AuthResponse
    func refreshToken() async throws -> AuthResponse
    func logout() async throws -> Void
    
    func listApplications() async throws -> [ApplicationResponse]
    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse
    func getApplication(id: UUID) async throws -> ApplicationResponse
    func updateApplication(id: UUID, request: UpdateApplicationRequest) async throws -> ApplicationResponse
    func deleteApplication(id: UUID) async throws -> Void
    
    func listEmails() async throws -> [EmailResponse]
    func getEmail(id: String) async throws -> EmailResponse
    func matchEmail(id: String, applicationId: UUID) async throws -> MatchResult
    func syncEmails() async throws -> SyncResponse
    func syncStatus() async throws -> SyncStatusResponse
}
```

**Real Implementation:** URLSession-based (Phase 6)  
**Mock Implementation:** Returns pre-defined JSON fixtures (Phase 5)

### 2.2 Mock Data Structure

```
ios/Bewerbungstracker/Tests/Fixtures/
├── auth/
│   ├── register_success.json
│   ├── login_success.json
│   ├── refresh_token.json
│   └── error_401_unauthorized.json
├── applications/
│   ├── list_3_items.json
│   ├── create_response.json
│   ├── update_response.json
│   ├── delete_response.json
│   └── error_404_not_found.json
├── emails/
│   ├── list_grouped.json
│   ├── detail_full_body.json
│   ├── sync_response.json
│   └── sync_status.json
└── error_responses/
    ├── 400_bad_request.json
    ├── 403_forbidden.json
    ├── 500_server_error.json
    └── timeout.json
```

### 2.3 Mock API Client Implementation

`MockAPIClient.swift` implements `APIClientProtocol`:

```swift
class MockAPIClient: APIClientProtocol {
    let fixtureBundle: Bundle
    
    func listApplications() async throws -> [ApplicationResponse] {
        return try loadFixture("applications/list_3_items.json")
    }
    
    func createApplication(_ request: CreateApplicationRequest) async throws -> ApplicationResponse {
        // Simulate delay (realistic)
        try await Task.sleep(nanoseconds: 500_000_000)
        return try loadFixture("applications/create_response.json")
    }
    
    // ... other methods
    
    private func loadFixture<T: Decodable>(_ path: String) throws -> T {
        // Load JSON from test bundle, decode, return
    }
}
```

### 2.4 Injection Point

Update `ApplicationsViewModel` to accept `APIClientProtocol` in initializer:

```swift
@MainActor
class ApplicationsViewModel: ObservableObject {
    let apiClient: APIClientProtocol
    
    init(apiClient: APIClientProtocol = URLSessionAPIClient()) {
        self.apiClient = apiClient
    }
}
```

Tests inject `MockAPIClient`:

```swift
let mockAPI = MockAPIClient()
let viewModel = ApplicationsViewModel(apiClient: mockAPI)
```

---

## 3. Mock Data Fixtures

### 3.1 Authentication Fixtures

**register_success.json**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "test@example.com",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

**login_success.json** — Same as register_success  
**refresh_token.json** — New access/refresh tokens  
**error_401_unauthorized.json**
```json
{
  "error": "Invalid credentials",
  "code": 401
}
```

### 3.2 Applications Fixtures

**list_3_items.json**
```json
{
  "total": 3,
  "has_more": false,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "company": "Google",
      "position": "Software Engineer",
      "location": "Mountain View, CA",
      "status": "interview",
      "applied_date": "2026-04-17T00:00:00Z",
      "created_at": "2026-04-17T10:30:00Z",
      "updated_at": "2026-04-20T14:22:00Z",
      "notes": "Strong interview process"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "company": "Meta",
      "position": "Product Manager",
      "location": "Boston, MA",
      "status": "applied",
      "applied_date": "2026-04-12T00:00:00Z",
      "created_at": "2026-04-12T09:15:00Z",
      "updated_at": "2026-04-12T09:15:00Z",
      "notes": null
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "company": "Microsoft",
      "position": "Data Scientist",
      "location": "Seattle, WA",
      "status": "offer",
      "applied_date": "2026-04-10T00:00:00Z",
      "created_at": "2026-04-10T11:00:00Z",
      "updated_at": "2026-04-21T16:45:00Z",
      "notes": "Negotiating salary"
    }
  ]
}
```

**create_response.json** — Single application item from list above  
**error_404_not_found.json**
```json
{
  "error": "Application not found",
  "code": 404
}
```

### 3.3 Emails Fixtures

**list_grouped.json**
```json
{
  "total": 5,
  "groups": [
    {
      "application_id": "550e8400-e29b-41d4-a716-446655440001",
      "company": "Google",
      "status": "interview",
      "emails": [
        {
          "id": "msg_001",
          "subject": "Interview Scheduled",
          "from": "recruiter@google.com",
          "timestamp": "2026-04-20T14:22:00Z",
          "body_preview": "Your interview is scheduled for April 24..."
        },
        {
          "id": "msg_002",
          "subject": "Application Received",
          "from": "noreply@google.com",
          "timestamp": "2026-04-17T10:30:00Z",
          "body_preview": "Thank you for applying..."
        }
      ]
    },
    {
      "application_id": "550e8400-e29b-41d4-a716-446655440002",
      "company": "Meta",
      "status": "applied",
      "emails": [
        {
          "id": "msg_003",
          "subject": "Application Received",
          "from": "noreply@meta.com",
          "timestamp": "2026-04-12T09:15:00Z",
          "body_preview": "Thank you for applying to Meta..."
        }
      ]
    }
  ]
}
```

**detail_full_body.json**
```json
{
  "id": "msg_001",
  "subject": "Interview Scheduled",
  "from": "recruiter@google.com",
  "to": "user@example.com",
  "timestamp": "2026-04-20T14:22:00Z",
  "body": "<html><body><p>Hello,</p><p>Your interview is scheduled for April 24 at 2:00 PM PST with our engineering team.</p><p>Best regards,<br>Google Recruiting</p></body></html>"
}
```

**sync_response.json**
```json
{
  "synced_count": 3,
  "new_emails": 2,
  "timestamp": "2026-04-22T13:45:00Z"
}
```

**sync_status.json**
```json
{
  "last_sync": "2026-04-22T13:45:00Z",
  "status": "success",
  "email_count": 5,
  "next_sync_in_seconds": 3600
}
```

---

## 4. Integration Testing Plan

### 4.1 Test Suite: Authentication Flow

**File:** `ApplicationsViewModelTests.swift` (expand existing)

Tests:
- `testLoginFlow_Success` — Register → Login → Get token
- `testTokenRefresh_Success` — Old token → Refresh → New token
- `testLogout_ClearsToken` — Logout removes stored token
- `testLoginFlow_InvalidCredentials` — 401 response handled correctly

### 4.2 Test Suite: Applications CRUD

Tests:
- `testListApplications_ReturnsThreeItems` — API returns 3 applications, UI shows all
- `testCreateApplication_AddsToLocalDB` — Create via API, verify in SwiftData
- `testUpdateApplication_RefreshesUI` — Edit application, ViewModel updates
- `testDeleteApplication_RemovesFromList` — Delete via API, disappears from list
- `testFilterByStatus_ShowsOnlyInterview` — Filter logic works with mock data
- `testSearchByCompany_ReturnsMatches` — Search "Google" returns Google application

### 4.3 Test Suite: Emails Integration

Tests:
- `testListEmails_GroupedByApplicationStatus` — Emails grouped correctly
- `testEmailDetailView_LoadsFullBody` — Detail screen shows complete email
- `testSyncEmails_UpdatesLocalDatabase` — Sync fetches new emails
- `testSyncStatus_ShowsLastSyncTime` — Settings displays sync info correctly

### 4.4 Test Suite: Error Handling

Tests:
- `testAPI_401Unauthorized_ShowsLoginError` — Proper error message displayed
- `testAPI_404NotFound_ShowsAlertToUser` — User sees "not found" error
- `testAPI_NetworkTimeout_ShowsRetryOption` — Timeout handled gracefully
- `testAPI_MalformedJSON_ShowsErrorAlert` — Invalid response doesn't crash

---

## 5. Test Execution

### 5.1 Run Tests

```bash
cd ios/Bewerbungstracker
xcodebuild test -scheme Bewerbungstracker -configuration Debug \
  -derivedDataPath build \
  -enableCodeCoverage YES
```

### 5.2 Expected Output

```
Test Suite: ApplicationsIntegrationTests
  Passing: 6/6 tests
  Coverage: 87% of ViewModels

Test Suite: EmailsIntegrationTests
  Passing: 4/4 tests

Test Suite: AuthIntegrationTests
  Passing: 3/3 tests

Test Suite: ErrorHandlingTests
  Passing: 4/4 tests

Total: 17/17 tests passing ✅
```

---

## 6. Files to Create/Modify

### Create:
- `MockAPIClient.swift` — Mock implementation of APIClientProtocol
- `APIClientProtocol.swift` — Protocol definition (extract from existing)
- `Tests/Integration/AuthIntegrationTests.swift` — Auth flow tests
- `Tests/Integration/ApplicationsIntegrationTests.swift` — CRUD tests
- `Tests/Integration/EmailsIntegrationTests.swift` — Email grouping tests
- `Tests/Integration/ErrorHandlingTests.swift` — Error handling tests
- `Tests/Fixtures/` directory with all JSON files (30+ files)

### Modify:
- `ViewModels/ApplicationsViewModel.swift` — Accept APIClientProtocol in init
- `ViewModels/EmailsViewModel.swift` — Accept APIClientProtocol in init
- `ViewModels/SettingsViewModel.swift` — Accept APIClientProtocol in init
- `App.swift` — Conditionally inject MockAPIClient (via environment variable)

---

## 7. Success Criteria

- ✅ MockAPIClient implements full APIClientProtocol
- ✅ All 30+ fixture JSON files created with realistic data
- ✅ 17+ integration tests pass (auth, CRUD, emails, error handling)
- ✅ Code coverage ≥ 85% for ViewModel layer
- ✅ App can toggle between mock and real API (environment variable)
- ✅ All 4 screens load correctly with mocked data
- ✅ Filtering, searching, grouping work with mock responses
- ✅ Error handling (401, 404, timeout) works correctly

---

## 8. Next Phase

Phase 5.2 (Android integration testing) follows same pattern after iOS complete.  
Phase 6 replaces MockAPIClient with real URLSessionAPIClient against deployed backend.

---

**Status:** Ready for implementation plan
