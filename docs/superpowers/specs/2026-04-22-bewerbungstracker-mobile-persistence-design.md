# Bewerbungstracker: Mobile + Persistenz — Design Spec

**Date:** 2026-04-22  
**Status:** Approved for Implementation  
**Approach:** Inkrementell-Parallel (Phase 1: Persistenz + REST API, Phase 2: Claude Routing, Phase 3: Native Mobile)

---

## Executive Summary

Roadmap zur Modernisierung des Bewerbungstrackers:
1. **Phase 1:** Datenbank-Persistenz (SQLAlchemy + PostgreSQL/SQLite) + REST API für Mobile
2. **Phase 2:** Integration des Claude API Routing Systems (Cost Tracking, Smart Matching)
3. **Phase 3:** Native Mobile Apps (iOS + Android) mit Cloud Sync & Auto-Backup

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│         Native Mobile Apps (iOS/Android)        │
│  - SwiftUI / Jetpack Compose                   │
│  - Local DB (Core Data / Room)                 │
│  - iCloud Drive / Google Drive Sync             │
└──────────────────┬──────────────────────────────┘
                   │ REST API (JWT Token Auth)
┌──────────────────▼──────────────────────────────┐
│       Flask Backend (Modernisiert)             │
│  - SQLAlchemy ORM                              │
│  - PostgreSQL / SQLite                         │
│  - REST API Endpoints                          │
│  - Claude Routing Integration                  │
│  - IMAP Proxy (127.0.0.1:8765)                 │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    ┌────▼────┐      ┌──────▼──────┐
    │ Database │      │ Claude API  │
    │ (PostgreSQL)   │ (Routed)    │
    └─────────┘      └─────────────┘
```

---

## Phase 1: Persistenz + REST API Layer

### 1.1 Datenbankschema

**users**
```sql
- id (PK)
- email (UNIQUE)
- password_hash
- imap_host, imap_user, imap_password_encrypted
- created_at, updated_at
```

**sessions**
```sql
- token (PK, JWT)
- user_id (FK)
- expires_at
- created_at
```

**applications** (Bewerbungen)
```sql
- id (PK)
- user_id (FK)
- company
- position
- status (ENUM: 'applied', 'interview', 'offer', 'rejected', 'archived')
- applied_date
- created_at, updated_at
```

**emails**
```sql
- id (PK)
- user_id (FK)
- message_id (unique per IMAP folder)
- subject
- from_address
- body (optional, for search)
- matched_application_id (FK, nullable)
- timestamp
- created_at
```

**api_calls** (für Claude Routing)
```sql
- id (PK)
- user_id (FK)
- endpoint (e.g., '/api/analyze-email')
- model (claude-haiku, sonnet, opus)
- tokens_in, tokens_out
- cost
- timestamp
```

### 1.2 Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| ORM | SQLAlchemy | Python-native, Flask-integration |
| Database | PostgreSQL (prod) / SQLite (dev) | Scalable, ACID, easy local dev |
| Migrations | Alembic | Standard for SQLAlchemy |
| API Framework | Flask + Flask-RESTful | Existing, lightweight |
| Authentication | JWT (Token-based) | Mobile-friendly, stateless |
| Password Hashing | bcrypt | Industry standard |
| Encryption | cryptography.fernet | Encrypted IMAP credentials in DB |

### 1.3 REST API Endpoints

**Authentication**
```
POST   /api/auth/login          → {email, password} → JWT token
POST   /api/auth/logout         → invalidate token
POST   /api/auth/refresh        → refresh expired token
```

**Applications (Bewerbungen)**
```
GET    /api/applications        → list all (user_id from token)
POST   /api/applications        → create new
GET    /api/applications/:id    → details
PATCH  /api/applications/:id    → update status
DELETE /api/applications/:id    → delete
```

**Emails**
```
GET    /api/emails              → list all (with filters)
GET    /api/emails?app_id=X     → emails for one application
POST   /api/emails/sync         → trigger IMAP fetch
GET    /api/emails/:id          → full email body
```

**Sync (für Mobile)**
```
GET    /api/sync                → returns delta (new/updated since last_sync)
POST   /api/sync/conflicts      → resolve offline conflicts
```

**Claude Integration (Phase 2)**
```
POST   /api/analyze-email       → Claude-powered analysis
POST   /api/match-application   → Smart email-to-application matching
GET    /api/usage/stats         → cost summary
POST   /api/budget/set          → set budget limit
```

### 1.4 Authentication Flow

1. Mobile App: `POST /api/auth/login` (email, password)
2. Backend: Hash password, check DB
3. Response: `{token: "JWT...", expires_in: 3600}`
4. Mobile: Store token in Keychain (iOS) / Keystore (Android)
5. Subsequent Requests: `Authorization: Bearer <token>`
6. Token Refresh: Auto-refresh 5 min before expiry

### 1.5 Migration Strategy

- Use Alembic for versioned migrations
- `alembic init alembic` (one-time setup)
- `alembic revision --autogenerate` for schema changes
- Mobile apps don't run migrations (backend-only)

---

## Phase 2: Claude Routing Integration

### 2.1 Integration Points

**Use Case 1: Email Analysis**
- User receives email about Bewerbung
- Mobile app → `POST /api/analyze-email`
- Backend routes to Claude (Haiku for speed, Opus if needed for complexity)
- Response: Extracted info (company, position, deadline, sentiment)

**Use Case 2: Smart Matching**
- `POST /api/match-application`
- Claude analyzes: "Is this email related to existing application X?"
- Response: matched_application_id + confidence score

### 2.2 New Database Table

**api_calls** (see Phase 1.1)

### 2.3 New Endpoints

```
POST   /api/analyze-email       {email_id} → Claude-analyzed metadata
POST   /api/match-application   {email_id} → {app_id, confidence}
GET    /api/usage/stats         → {month_cost, requests, model_breakdown}
POST   /api/budget/set          {project_id, limit_usd}
```

### 2.4 Backend Changes

- Import routing library (from Phase 2 work)
- `from claude_routing import claudeModelRouter`
- Wrap each Claude call: `router.selectModel(task)` → returns model + cost estimate
- Log to api_calls table via cost_calculator

---

## Phase 3: Native Mobile Apps

### 3.1 iOS (Swift/SwiftUI)

**Architecture:**
- MVVM (Model-View-ViewModel)
- Core Data for local persistence
- URLSession for REST API
- Combine for reactive updates

**Key Features:**
- TabView: Applications, Emails, Settings
- LoginView: email + password → token storage
- ApplicationListView: swipe-to-delete, status badges
- EmailDetailView: full body, related application highlight
- SettingsView: logout, backup/restore, auto-sync toggle

**Local Storage:**
```swift
@Entity
final class ApplicationModel {
    @Attribute(.unique) var id: UUID
    var company: String
    var position: String
    var status: String // "applied", "interview", ...
    var appliedDate: Date
    var emails: [EmailModel] // @Relationship
}
```

**Cloud Integration (iCloud):**
```swift
// Auto-backup to iCloud Drive daily
let fileManager = FileManager.default
let iCloudContainer = fileManager.url(forUbiquityContainerIdentifier: nil)
// Export JSON to iCloud
let jsonData = try JSONEncoder().encode(applications)
try jsonData.write(to: iCloudBackupURL)
```

**Auto-Sync:**
- Timer fires daily at 2 AM
- `URLSession` calls `GET /api/sync`
- Core Data merges delta
- Conflict: server-version wins

### 3.2 Android (Kotlin/Jetpack Compose)

**Architecture:**
- MVVM with ViewModel + StateFlow
- Room Database for local persistence
- Retrofit + OkHttp for REST API
- Jetpack Compose for UI

**Key Features:**
- Same as iOS (Applications, Emails, Settings)
- Material Design 3
- Bottom navigation instead of TabView

**Local Storage:**
```kotlin
@Entity
data class ApplicationEntity(
    @PrimaryKey val id: String,
    val company: String,
    val position: String,
    val status: String,
    val appliedDate: Long
)

@Dao
interface ApplicationDao {
    @Query("SELECT * FROM applications WHERE userId = :userId")
    suspend fun getAllApplications(userId: String): List<ApplicationEntity>
}
```

**Cloud Integration (Google Drive):**
```kotlin
// Use Google Drive API v3
val driveService = Drive.Builder(httpTransport, jsonFactory, credential)
    .setApplicationName("Bewerbungstracker")
    .build()
// Auto-backup JSON to Google Drive
val fileContent = FileContent("application/json", File(exportPath))
driveService.files().create(fileMetadata, fileContent).execute()
```

**Auto-Sync:**
- WorkManager for background task
- Daily at 2 AM
- `Retrofit` calls `GET /api/sync`
- Room DB merges delta

### 3.3 Shared Features

**JWT Token Management:**
- Store securely: Keychain (iOS) / Keystore (Android)
- Auto-refresh 5 min before expiry
- Clear on logout

**Offline Mode:**
- Full read access to local DB when offline
- Write operations queued, sync when online
- Conflict resolution: server wins OR user chooses

**Auto-Backup:**
```
Daily at 2 AM (local time):
  - Export all data to JSON
  - Upload to iCloud Drive (iOS) / Google Drive (Android)
  - Keep last 7 backups
  - Delete older backups

Manual Backup:
  - Settings → "Backup Now"
  - Same flow, immediate
```

**Import Flow:**
```
Settings → "Restore from Backup"
  → Show list of available backups
  → User selects one
  → Download JSON from iCloud/Google Drive
  → Merge with local DB (resolve conflicts)
  → Show summary ("X applications, Y emails imported")
```

---

## Data Flow Example: Email Sync

**Scenario:** User receives email in Gmail, mobile app syncs.

```
1. Mobile App (background): Timer fires 2 AM
2. App calls: GET /api/sync?last_sync=<timestamp>
3. Backend:
   - Fetches IMAP credentials (decrypt from DB)
   - imap_proxy queries IMAP server
   - Returns new emails since last_sync
   - Attempts Claude matching (if enabled)
   - Returns: [{email_id, subject, from, app_id}, ...]
4. Mobile App:
   - Receives delta
   - Merges into Core Data / Room DB
   - Shows notification: "3 new emails"
5. User opens app:
   - Sees new emails in ApplicationView
   - Can manually reassign to different app
   - Change is synced back to Backend
```

---

## Implementation Order

1. **Phase 1a:** Database schema + ORM setup (Alembic migrations)
2. **Phase 1b:** REST API endpoints (auth, CRUD applications/emails)
3. **Phase 1c:** Testing (unit tests for API, integration tests for DB)
4. **Phase 2:** Claude Routing integration (new endpoints, logging)
5. **Phase 3a:** iOS app (Swift/SwiftUI, local storage, sync)
6. **Phase 3b:** Android app (Kotlin/Compose, local storage, sync)
7. **Phase 3c:** Cloud integration (iCloud/Google Drive backup/restore)
8. **Phase 3d:** Testing (E2E, offline scenarios)

---

## Testing Strategy

### Phase 1 Testing
- **Unit:** API endpoints (mock DB)
- **Integration:** DB migrations, full CRUD
- **E2E:** Login → Create app → Sync emails → Update status

### Phase 2 Testing
- **Mock Claude API:** Test routing logic without API calls
- **Cost calculation:** Verify cost estimates match actual
- **Integration:** Full flow email analysis + DB logging

### Phase 3 Testing
- **iOS:** XCTest (UI tests, Core Data tests, networking)
- **Android:** JUnit + Espresso (unit, integration, UI)
- **Offline:** Disable network, verify local read, queue writes
- **Sync:** Conflict resolution scenarios

---

## Deployment Considerations

### Backend (Flask)
- Docker container (or SSH + nohup on local server)
- PostgreSQL on RDS or self-hosted
- Environment variables: `DATABASE_URL`, `CLAUDE_API_KEY`, `JWT_SECRET`

### iOS App
- TestFlight for beta
- App Store for production
- Code signing, provisioning profiles

### Android App
- Google Play Console internal testing
- Google Play Store for production

### Cloud Services
- iCloud: Requires Apple Developer Account
- Google Drive: Requires Google Cloud Project + OAuth setup

---

## Security Considerations

- **IMAP Credentials:** Encrypted at rest (Fernet), never logged
- **JWT Token:** Short expiry (1 hour), refresh tokens for mobile
- **Password:** bcrypt (cost=12)
- **API Rate Limiting:** 100 requests/min per user (future: add to Phase 2)
- **HTTPS Only:** Flask + nginx with SSL (backend)
- **Mobile:** Token in Keychain/Keystore, never SharedPreferences

---

## Known Limitations & Future Work

### Current Phase Scope
- No end-to-end encryption (app ↔ backend over HTTPS)
- No offline-first full sync (only read-only offline)
- No multi-device sync (each device = independent local DB)

### Future Enhancements
- Multi-device sync (server as source of truth)
- E2E encryption (only user can decrypt their emails)
- Webhook notifications (instead of polling)
- Machine learning for auto-tagging applications

---

## Success Criteria

✅ Phase 1 Done:
- All DB migrations applied without errors
- REST API tested (100+ unit tests)
- CRUD operations for applications + emails verified

✅ Phase 2 Done:
- Claude API calls routed correctly
- Cost tracking accurate (<0.1% error)
- Budget alerts working

✅ Phase 3 Done:
- iOS app installable from TestFlight
- Android app installable from Google Play Console (internal test)
- Auto-sync working (tested with offline scenario)
- Cloud backup/restore working (tested with iCloud/Google Drive)
