# Bewerbungstracker Android App

Native Android application for managing job applications with local persistence and cloud synchronization.

## System Requirements

- **Android Studio:** 2023.1 (Hedgehog) or later
- **Kotlin:** 1.9.0 or later
- **Android SDK:** API 28 (minimum) to API 34 (target)
- **Java:** JDK 17 or later
- **Gradle:** 8.0 or later

## Architecture

### Design Pattern
- **MVVM:** Model-View-ViewModel with Jetpack Compose
- **Local Persistence:** Room Database for SQLite management
- **Networking:** Retrofit + OkHttp for REST API communication
- **Security:** EncryptedSharedPreferences for token storage
- **Async:** Kotlin Coroutines with suspend functions

### Project Structure

```
android/app/src/main/
├── kotlin/com/example/bewerbungstracker/
│   ├── models/
│   │   ├── ApplicationEntity.kt  # Job application data entity
│   │   └── EmailEntity.kt        # Email data entity
│   ├── ui/
│   │   ├── LoginScreen.kt        # Authentication UI
│   │   ├── ApplicationListScreen.kt  # Applications list
│   │   ├── EmailDetailScreen.kt  # Email viewer
│   │   └── SettingsScreen.kt     # User settings
│   ├── data/
│   │   ├── AppDatabase.kt        # Room database with DAOs
│   │   ├── ApplicationDao.kt     # Application data access
│   │   └── EmailDao.kt           # Email data access
│   ├── services/
│   │   ├── APIClient.kt          # Retrofit API client
│   │   ├── TokenManager.kt       # JWT token management
│   │   └── SyncService.kt        # Background sync (WorkManager)
│   ├── viewmodel/
│   │   ├── LoginViewModel.kt     # Authentication logic
│   │   ├── ApplicationsViewModel.kt  # Applications list logic
│   │   └── EmailsViewModel.kt    # Emails logic
│   └── MainActivity.kt           # App entry point
└── res/
    ├── drawable/                 # Icons & images
    ├── layout/                   # Legacy layouts (if needed)
    ├── values/
    │   ├── colors.xml           # Color palette
    │   ├── strings.xml          # String resources
    │   └── themes/              # Theme definitions
    └── mipmap/                  # App icons

```

## Setup Instructions

### 1. Clone & Open Project

```bash
# Navigate to Android directory
cd android

# Open in Android Studio
open -a "Android Studio" .
```

Or directly in Android Studio:
- File → Open → Select `android` directory
- Wait for Gradle sync to complete

### 2. Configure SDK & JDK

In Android Studio:
1. **File** → **Project Structure** → **SDK Location**
2. Ensure Android SDK path is correct
3. Set JDK location to JDK 17+
4. Click **Sync Now**

### 3. Connect Device or Start Emulator

**Using Emulator:**
```bash
# List available emulators
$ANDROID_HOME/emulator/emulator -list-avds

# Start emulator
$ANDROID_HOME/emulator/emulator -avd <emulator_name>
```

**Using Physical Device:**
1. Enable Developer Mode (Settings → About Phone → tap Build Number 7 times)
2. Enable USB Debugging (Settings → Developer Options → USB Debugging)
3. Connect via USB
4. Trust computer when prompted

### 4. Build & Run

```bash
# Build APK
./gradlew assembleDebug

# Run on connected device/emulator
./gradlew installDebug

# Run app directly
./gradlew run
```

Or from Android Studio:
- Select device/emulator in top toolbar
- Click green **Run** button (Shift+F10)

## Configuration

### Backend URL

Edit `APIClient.kt`:

```kotlin
private const val BASE_URL = "http://localhost:8080/api/"  // Development
// Change to: "https://api.example.com/api/"                // Production
```

### Encrypted Preferences Service

Edit `TokenManager.kt`:

```kotlin
private val sharedPreferences = EncryptedSharedPreferences.create(
    context,
    "bewerbungstracker_auth",  // Change service name if needed
    masterKey,
    ...
)
```

## Features

### Authentication
- Email/password registration and login
- JWT token-based authentication with refresh mechanism
- Encrypted token storage using EncryptedSharedPreferences
- Auto-logout on token expiry
- Logout with token invalidation

### Application Management
- Create new job applications
- View list of applications with status filtering
- Update application status (applied, interview, offer, rejected, archived)
- Delete applications with confirmation dialog
- Track applied date and timestamps

### Email Integration
- View emails related to applications
- Filter emails by application
- Claude AI-powered email analysis (if enabled)
- Smart email-to-application matching

### Synchronization
- Background sync using WorkManager
- Delta sync for bandwidth efficiency
- Conflict resolution (server-version wins)
- Offline mode with queued writes

### Local Storage
- Room Database for reliable persistence
- Type-safe queries with Kotlin suspend functions
- Automatic relationship management
- Migration support for schema changes

## Testing

### Unit Tests

```bash
# Run all unit tests
./gradlew test

# Run specific test class
./gradlew testDebugUnitTest -k TokenManagerTest

# Generate test coverage
./gradlew testDebugUnitTest --coverage
```

### Instrumented Tests (Android Tests)

```bash
# Run on connected device/emulator
./gradlew connectedAndroidTest

# Run specific instrumented test
./gradlew connectedAndroidTest -k AppDatabaseTest
```

### Test Categories

- **Unit Tests:** TokenManager, Repository, ViewModel logic
- **Database Tests:** Room DAOs, migrations, relationships
- **API Tests:** Retrofit service, error handling, token refresh
- **UI Tests:** Compose screen navigation, user interactions

### Manual Testing

1. **Login Flow:**
   - Launch app → Register/Login
   - Verify token stored in encrypted SharedPreferences
   - Check no token logged to console

2. **Offline Mode:**
   - Enable Airplane Mode
   - Create application (should queue locally)
   - Disable Airplane Mode
   - Verify sync and remote save

3. **Data Persistence:**
   - Create applications/emails
   - Force stop app (Settings → App Info → Force Stop)
   - Reopen app
   - Verify data still present

## Debugging

### Android Debug Bridge (ADB)

```bash
# View app logs
adb logcat | grep "BewerbungstrackerApp"

# Access app database via adb
adb shell
run-as com.example.bewerbungstracker
cat /data/data/com.example.bewerbungstracker/databases/bewerbungstracker.db

# Clear app data
adb shell pm clear com.example.bewerbungstracker
```

### Database Inspector

In Android Studio:
1. **View** → **Tool Windows** → **App Inspection**
2. Select device/app
3. View Room database tables and queries in real-time

### Profiler

Monitor app performance:
1. **View** → **Tool Windows** → **Profiler**
2. Monitor CPU, Memory, Network traffic
3. Identify bottlenecks

## Deployment

### Build Release APK

```bash
# Build signed release APK
./gradlew bundleRelease

# Or create APK
./gradlew assembleRelease
```

### Google Play Console

1. Create app on [Google Play Console](https://play.google.com/console)
2. Complete app details and store listing
3. Build release bundle: `./gradlew bundleRelease`
4. Upload to **App Bundles** section
5. Create release: **Testing** → **Internal testing** → **Create release**
6. Add testers and share internal testing link

### Signing Configuration

Create `keystore.properties` in project root:

```properties
storeFile=/path/to/release.keystore
storePassword=your_store_password
keyAlias=your_key_alias
keyPassword=your_key_password
```

Then configure in `build.gradle.kts`:

```kotlin
signingConfigs {
    release {
        storeFile = file(signingConfig["storeFile"])
        storePassword = signingConfig["storePassword"]
        keyAlias = signingConfig["keyAlias"]
        keyPassword = signingConfig["keyPassword"]
    }
}
```

## Troubleshooting

### Build Issues

**Error: "Could not determine Java version from '17.0.x'."**
- Ensure JDK 17+ is installed
- File → Project Structure → SDK Location → Set correct JDK path

**Error: "Gradle version X requires Java X"**
- Update Gradle: `./gradlew wrapper --gradle-version 8.0`
- Or update JDK to required version

**Error: "Room schema not found"**
- Clean and rebuild: `./gradlew clean && ./gradlew build`
- Regenerate schema: Delete `schemas/` directory and rebuild

### Runtime Issues

**Tokens not persisting**
- Check EncryptedSharedPreferences permission in manifest
- Verify device hasn't been reset
- Inspect using Android Studio App Inspection

**API calls timing out**
- Verify backend running on `http://localhost:8080`
- Check network connectivity (disable VPN if applicable)
- Verify firewall allows port 8080

**Database locked error**
- Close app completely
- Clear cache: Settings → App Info → Storage → Clear Cache
- Restart emulator/device

## Performance Optimization

### Database
- Use Room Indices on frequently queried fields
- Implement pagination for large datasets
- Use `@Embedded` for related data models

### Network
- Implement request batching
- Use gzip compression for large responses
- Implement request caching with OkHttp

### Compose UI
- Use `.drawBehind` instead of `.background` for performance
- Implement LazyColumn for long lists
- Avoid recomposition with proper state management

## Security Best Practices

1. **Token Storage:** Always use EncryptedSharedPreferences, never standard SharedPreferences
2. **HTTPS:** Use HTTPS in production (enforce via network security config)
3. **Certificate Pinning:** Implement for API endpoints
4. **Input Validation:** Validate all user input before API calls
5. **Sensitive Data:** Never log tokens, passwords, or user data
6. **Proguard/R8:** Enable minification in release builds

### Network Security Configuration

Create `res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set>
            <pin digest="SHA-256"><!-- certificate pin here --></pin>
        </pin-set>
    </domain-config>
    <!-- Allow cleartext only for localhost development -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">localhost</domain>
        <domain includeSubdomains="true">127.0.0.1</domain>
    </domain-config>
</network-security-config>
```

## Resources

- [Android Developers](https://developer.android.com/)
- [Jetpack Compose Docs](https://developer.android.com/jetpack/compose/documentation)
- [Room Database Guide](https://developer.android.com/training/data-storage/room)
- [Retrofit Documentation](https://square.github.io/retrofit/)
- [Kotlin Coroutines](https://kotlinlang.org/docs/coroutines-overview.html)
- [Material Design 3](https://m3.material.io/)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review backend logs at `/Library/WebServer/Documents/Bewerbungstracker/`
3. Check API endpoint in APIClient.kt matches backend URL
4. Verify Android Studio Logcat for error messages
5. Use Android Studio Debugger for step-through debugging
