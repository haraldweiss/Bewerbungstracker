# Bewerbungstracker iOS App

Native iOS application for managing job applications with local persistence and cloud synchronization.

## System Requirements

- **Xcode:** 15.0 or later
- **Swift:** 5.9 or later
- **iOS Deployment Target:** 17.0+
- **macOS:** 12.0+ (for development)

## Architecture

### Design Pattern
- **MVVM:** Model-View-ViewModel architecture with separation of concerns
- **Local Persistence:** SwiftData (modern replacement for Core Data)
- **Networking:** URLSession with async/await for REST API communication
- **Security:** Keychain for secure token storage

### Project Structure

```
Bewerbungstracker/
├── Models/
│   ├── ApplicationModel.swift    # Job application entity
│   └── EmailModel.swift          # Email entity with relationships
├── Views/
│   ├── ContentView.swift         # Main tab-based navigation
│   ├── LoginView.swift           # Authentication UI
│   ├── ApplicationListView.swift # List of applications
│   ├── EmailDetailView.swift     # Email content viewer
│   └── SettingsView.swift        # User settings & sync controls
├── Services/
│   ├── APIClient.swift           # REST API communication
│   ├── TokenManager.swift        # Secure JWT token management
│   └── CloudSyncService.swift    # iCloud Drive sync (future)
├── CoreData/
│   └── Bewerbungstracker.xcdatamodeld  # Data model (optional, if using Core Data)
├── App.swift                     # SwiftUI app entry point
└── Bewerbungstracker.entitlements # iCloud capabilities

```

## Setup Instructions

### 1. Project Configuration

Open `Bewerbungstracker.xcodeproj` in Xcode:

```bash
open ios/Bewerbungstracker/Bewerbungstracker.xcodeproj
```

### 2. Target Configuration

1. Select `Bewerbungstracker` target
2. Go to **Signing & Capabilities**
3. Ensure Team ID is set (required for iCloud)
4. Enable **iCloud** capability with Documents backend

### 3. Build Configuration

```bash
# Build for iOS simulator
xcodebuild build -scheme Bewerbungstracker -destination 'generic/platform=iOS Simulator'

# Build for device
xcodebuild build -scheme Bewerbungstracker -destination generic/platform=iOS
```

### 4. Run App

From Xcode:
- Select desired simulator/device
- Press **Cmd+R** to run
- Or use: `xcodebuild -scheme Bewerbungstracker -destination 'platform=iOS Simulator,name=iPhone 15'`

## Configuration

### Backend URL

Edit `APIClient.swift`:

```swift
private let baseURL = "http://localhost:8080/api"  // Development
// Change to: "https://api.example.com/api"        // Production
```

### Keychain Service Identifier

Edit `TokenManager.swift`:

```swift
private let keychainService = "com.bewerbungstracker.app"
```

## Features

### Authentication
- Email/password registration and login
- JWT token-based authentication
- Secure token storage in Keychain
- Auto-token refresh with expiry handling
- Logout with token invalidation

### Application Management
- Create new job applications
- View list of applications with status filtering
- Update application status (applied, interview, offer, rejected, archived)
- Delete applications with confirmation
- Track applied date for each position

### Email Integration
- View emails related to applications
- Filter emails by application
- Claude AI-powered email analysis
- Smart email-to-application matching

### Synchronization
- Background sync with backend
- Conflict resolution (server-version wins)
- Offline read access with queued writes
- Delta sync for bandwidth efficiency

### Local Storage
- SwiftData persistence for applications and emails
- Automatic model relationship management
- Type-safe queries and updates

## Testing

### Unit Tests

```bash
# Run all tests
xcodebuild test -scheme Bewerbungstracker

# Run specific test class
xcodebuild test -scheme Bewerbungstracker -only-testing Bewerbungstracker/APIClientTests

# Generate coverage report
xcodebuild test -scheme Bewerbungstracker -enableCodeCoverage YES
```

### Test Categories

- **APIClientTests:** REST API communication
- **TokenManagerTests:** Keychain storage and JWT handling
- **ApplicationModelTests:** Data model validation
- **CloudSyncTests:** Synchronization logic

### Manual Testing

1. **Login Flow:**
   - Launch app → Login with test credentials
   - Verify token stored in Keychain
   - Verify token not logged in console

2. **Offline Mode:**
   - Disconnect network (Xcode → Debug → Network Conditions)
   - Create application (should queue)
   - Reconnect network → Verify sync

3. **Sync:**
   - Make change on web app
   - Trigger sync in iOS app
   - Verify local DB updated

## Debugging

### Console Logging

Enable verbose API logging:

```swift
// In APIClient.swift, add logging:
print("API Request: \(request.url?.absoluteString ?? "")")
print("Response Status: \(httpResponse.statusCode)")
```

### Keychain Debugging

Check stored tokens:

```swift
// In TokenManager, call this for debugging:
let token = TokenManager.shared.getAccessToken()
if let decoded = TokenManager.shared.decodeToken(token ?? "") {
    print("Token Payload: \(decoded)")
}
```

### SwiftData Inspector

SwiftUI SwiftData query inspection:

```swift
@Query(sort: \ApplicationModel.createdAt, order: .reverse)
var applications: [ApplicationModel]
```

## Deployment

### Testflight (Beta Testing)

1. Archive app: **Product → Archive** in Xcode
2. Upload to App Store Connect
3. Submit for TestFlight review
4. Share link with beta testers

### App Store (Production)

1. Prepare release notes and screenshots
2. Increment version in Xcode (General → Version)
3. Archive: **Product → Archive**
4. Submit to App Store Connect
5. Wait for review (typically 1-2 days)

### Code Signing

Ensure provisioning profiles are configured:

```bash
# List provisioning profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/

# Verify code signing
codesign -v -v /path/to/Bewerbungstracker.app
```

## Troubleshooting

### Build Issues

**Error: "SwiftData not found"**
- Ensure iOS deployment target ≥ 17.0
- Clean build folder: **Cmd+Shift+K**

**Error: "Keychain EntitlementMissing"**
- Verify `Bewerbungstracker.entitlements` includes Keychain capability

### Runtime Issues

**Token not persisting**
- Check Keychain permission in entitlements
- Verify simulator hasn't been reset (clears Keychain)

**API calls timing out**
- Check backend is running on `http://localhost:8080`
- Verify network connectivity in Debug Menu

**Sync conflicts**
- Check last_sync timestamp in local defaults
- Review server log for delta response

## Performance Optimization

### Memory Management

- Use `@ObservedObject` only for observed changes
- Clear unused references in `onDisappear`
- Avoid circular references in models

### Network Efficiency

- Implement request batching for multiple applications
- Use ETags for conditional requests
- Compress large payloads

### Database Optimization

- Create indexes on frequently queried fields
- Use `.unique` constraint on email messageId
- Archive old applications to reduce query time

## Security Best Practices

1. **Token Storage:** Always use Keychain, never UserDefaults
2. **HTTPS:** Use HTTPS in production (enforce via entitlements)
3. **Certificate Pinning:** Implement for API endpoints
4. **Input Validation:** Validate all user input before sending to API
5. **Sensitive Data:** Never log tokens or passwords
6. **App Transport Security:** Disable only for localhost development

## Resources

- [SwiftUI Documentation](https://developer.apple.com/documentation/swiftui)
- [SwiftData Guide](https://developer.apple.com/documentation/swiftdata)
- [URLSession Tutorial](https://developer.apple.com/documentation/foundation/urlsession)
- [Keychain Services API](https://developer.apple.com/documentation/security/keychain_services)
- [App Store Connect Help](https://help.apple.com/app-store-connect)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review backend logs at `/Library/WebServer/Documents/Bewerbungstracker/`
3. Check API endpoint in APIClient.swift matches backend URL
4. Verify network connectivity and firewall rules
