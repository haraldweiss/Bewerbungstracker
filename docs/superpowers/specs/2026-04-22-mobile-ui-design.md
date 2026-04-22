# Bewerbungstracker Mobile UI Design Specification

**Date:** 2026-04-22  
**Status:** Approved  
**Scope:** iOS/Android UI Implementation (Phase 4)  
**Design Approach:** iOS HIG Native (iOS-first, Android Material 3 adaptation)

---

## 1. Navigation Architecture

### Bottom Tab Navigation (iOS Style)
- **4 Tabs** always visible at bottom of screen
- **Order (left to right):**
  1. Applications (main tab)
  2. Emails
  3. Notifications
  4. Settings
- **Tab Icons:** 📋 | ✉️ | 🔔 | ⚙️
- **Active Tab:** Highlighted with brand color, inactive tabs in gray
- **Behavior:** Preserves scroll position when switching tabs

---

## 2. Screen Specifications

### 2.1 Applications Tab (Home Screen)

**Primary Purpose:** Display, filter, search, and create job applications.

**Layout Components:**
- **Header:** Standard title "Applications"
- **Search Bar:** Placeholder text "Search applications..." with search icon
- **Filter Pills:** Horizontal scrolling, pill-shaped buttons
  - Filters: "All", "Applied", "Interview", "Offer"
  - Selected filter: Brand color background
  - Unselected filter: Light gray background
- **Application Cards:** Full-width detailed cards in vertical list
  - **Card Structure:**
    - Left border (3px) colored by status (green=interview, orange=applied, blue=offer, purple=pending)
    - Company name (bold, 13pt)
    - Position title + Location (gray, 12pt)
    - Metadata row: Applied date + Email count (small, 11pt, gray)
    - Right side: Status badge (colored, white text, small)
  - **Card Spacing:** 8px margins between cards
  - **Card Tap Action:** Opens application detail view (future enhancement)
- **Create Button:** Bottom-right positioned "+ New Application" button
  - Blue background (#007AFF), white text
  - Always visible (sticky bottom or scroll position)
  - Thumb-friendly size (10x10mm minimum touch target)

**Must-Have Features (Phase 4.1):**
- View applications list with status indicators
- Filter by status (All, Applied, Interview, Offer)
- Search by company/position name
- Create new application (modal form)

**Nice-to-Have (Phase 4.2+):**
- Sort by date, company, status
- Swipe to delete
- Edit existing application
- Bulk actions (archive multiple)

---

### 2.2 Emails Tab

**Primary Purpose:** View and manage emails related to applications.

**Layout Components:**
- **Search Bar:** "Search emails..." placeholder
- **Grouped Sections:** 
  - Grouped by **Application + Status** (e.g., "Google — Interview")
  - Section headers: Uppercase, gray, 12pt
- **Email Items (within each group):**
  - Left border (3px) colored by application status
  - Email subject (bold, 12pt)
  - From address + timestamp (gray, 11pt)
  - Tap to view full email content
- **Empty State:** "No emails yet" message when no data

**Must-Have Features (Phase 4.1):**
- View emails grouped by application + status
- Display sender and timestamp
- Tap to read full email content
- Link email to application (manual action)

**Nice-to-Have (Phase 4.2+):**
- Claude AI analysis badge (indicates if Claude analyzed this email)
- Auto-categorize email to application
- Star/favorite emails
- Delete emails

---

### 2.3 Notifications Tab

**Primary Purpose:** Activity timeline — track application milestones and reminders.

**Layout Components:**
- **Activity Feed:** Vertical timeline list
- **Activity Items:**
  - Activity description (bold, 13pt)
  - Activity context/details (gray, 12pt)
  - Relative timestamp (gray, 11pt)
  - Examples:
    - "Google Interview Scheduled" → "Tomorrow at 2:00 PM" → "2 hours ago"
    - "Applied to Meta — Product Manager" → "Boston, MA" → "3 days ago"
    - "Follow-up Reminder: Microsoft" → "Consider sending follow-up email" → "1 week ago"
- **Chronological Order:** Most recent first (default)
- **Empty State:** "No activity yet" message

**Must-Have Features (Phase 4.1):**
- Display activity timeline (applications submitted, interviews scheduled, offers received)
- Show relative timestamps (X days ago)
- Basic filtering/grouping optional

**Nice-to-Have (Phase 4.2+):**
- Push notifications for important events
- Mark as read/unread
- Archive activities
- Customize notification preferences

---

### 2.4 Settings Tab

**Primary Purpose:** Account management, data sync, and app configuration.

**Layout Components:**
- **User Profile Section:** Top card with user info
  - Profile avatar (placeholder circle or initials)
  - Full name (bold, 14pt)
  - Email address (gray, 12pt)
  - Tap to edit profile (future)
- **Settings Sections:** Grouped cards below profile
  - **Account Settings** → "Change password, email, preferences"
  - **Sync & Data** → "Last sync: X minutes ago" + Manual sync button
  - **Data Export & Backup** → "Export CSV, backup options"
  - **App Info** → "Version 1.0, Terms & Privacy"
- **Logout Button:** Bottom card, red background (#FF3B30), white text
  - Requires confirmation before logout (safety)

**Must-Have Features (Phase 4.1):**
- Display user profile (name, email)
- Logout functionality
- Show sync status (last sync time)
- Link to account settings (edit profile, password)

**Nice-to-Have (Phase 4.2+):**
- Push notification preferences
- Dark mode toggle
- Language selection
- Account deletion
- Session management (show active sessions)

---

## 3. Design System & Styling

### Color Palette (iOS HIG)
| Element | Color | HEX |
|---------|-------|-----|
| Brand Primary | Blue | #007AFF |
| Status: Interview | Green | #4CAF50 |
| Status: Applied | Orange | #FF9800 |
| Status: Offer | Light Blue | #2196F3 |
| Status: Pending | Purple | #9C27B0 |
| Text Primary | Dark Gray | #333333 |
| Text Secondary | Medium Gray | #666666 |
| Text Tertiary | Light Gray | #999999 |
| Background | White | #FFFFFF |
| Card Background | White | #FFFFFF |
| Section Background | Light Gray | #F5F5F5 |
| Border | Light Gray | #E0E0E0 |
| Danger/Delete | Red | #FF3B30 |

### Typography
- **Font Family:** San Francisco (iOS native system font)
- **Title (Screen headers):** 17pt, bold
- **Heading (Card titles):** 13pt, bold
- **Body (Primary text):** 12pt, regular
- **Secondary (Supporting text):** 11pt, regular, gray
- **Label (Tiny text):** 10pt, regular, light gray

### Spacing Grid
- **Base Unit:** 4px
- **Common spacings:** 8px, 12px, 16px, 20px, 24px
- **Card padding:** 12px
- **Section margins:** 16px
- **Tab margin:** 8px between items

### Rounded Corners
- **Cards:** 6px
- **Buttons:** 6px
- **Status badges:** 3px
- **Input fields:** 4px

### Shadows & Depth
- **Card shadow:** Subtle (0px 1px 3px rgba(0,0,0,0.1))
- **Bottom bar shadow:** Light elevation shadow
- **Button press state:** Darker background on tap

### Interaction States
- **Button Hover:** Darker background, slight scale
- **Button Active/Pressed:** Darker background, no scale
- **Input Focus:** Blue border/highlight
- **Card Tap:** Slight background color change or scale

---

## 4. iOS Implementation Details

### SwiftUI Components
- **Bottom Tab Bar:** `TabView` with `.tabViewStyle(.page)` → NO, use custom `ZStack` with `VStack` for proper iOS tab bar behavior
  - Use Tab View with proper tab bar icons
  - Safe area handling for iPhone notch
  - Safe area handling for Dynamic Island
- **Navigation:** `NavigationStack` for modal/sheet transitions
- **List Views:** `List` or `ScrollView` + `VStack` for custom card layouts
- **Search:** `SearchField` integrated with filtering logic
- **Input Fields:** `TextField` with proper keyboard handling
- **Buttons:** `Button` with `.buttonStyle(.bordered)` or custom styles

### Local Persistence
- **SwiftData:** Models for Application, Email, Notification entities
- **Keychain:** JWT tokens stored securely
- **UserDefaults:** Non-sensitive preferences (last sync time, user preferences)

### Networking
- **URLSession:** Async/await for API calls
- **JSON Codable:** Encode/decode API responses
- **Token Management:** Auto-refresh JWT tokens, handle 401 responses

---

## 5. Android Implementation Details (Material Design 3 Adaptation)

### Jetpack Compose Components
- **Bottom Navigation Bar:** `BottomNavigation` with Material 3 styling
  - 4 navigation items matching iOS (same order, similar icons)
- **Navigation:** `NavController` with `NavHost` for screen transitions
- **List Views:** `LazyColumn` for application cards
- **Search:** `TextField` with leading search icon
- **Buttons:** `Button` with Material 3 colors and elevation

### Local Persistence
- **Room Database:** ApplicationEntity, EmailEntity with DAOs
- **EncryptedSharedPreferences:** JWT token storage
- **DataStore:** Non-sensitive user preferences

### Networking
- **Retrofit + OkHttp:** API communication with interceptors
- **Coroutines:** Suspend functions for async operations
- **Token Management:** Same as iOS (auto-refresh, 401 handling)

---

## 6. Data Models (Shared Across Platforms)

### Application
```
{
  id: UUID,
  company: String,
  position: String,
  location: String,
  status: Enum (applied, interview, offer, rejected, archived),
  appliedDate: Date,
  createdAt: Date,
  updatedAt: Date,
  notes: String? (optional)
}
```

### Email
```
{
  id: String (messageId),
  subject: String,
  from: String,
  body: String,
  timestamp: Date,
  applicationId: UUID (foreign key),
  claudeAnalyzed: Boolean
}
```

### Notification/Activity
```
{
  id: UUID,
  type: Enum (application_created, interview_scheduled, offer_received, email_received, reminder),
  title: String,
  description: String,
  timestamp: Date,
  applicationId: UUID? (optional),
  isRead: Boolean
}
```

---

## 7. Testing Strategy

### Unit Tests
- **Search/Filter logic:** Verify filtering applications by status/name
- **Date formatting:** Verify relative timestamps ("2 days ago")
- **Data model validation:** Verify required fields, constraints

### UI/Integration Tests (iOS)
- **Navigation:** Verify tab switching preserves state
- **Create application:** Verify form submission, error handling
- **Search:** Verify search results update in real-time
- **Offline mode:** Verify app functions without network (where applicable)

### UI/Integration Tests (Android)
- Same as iOS, using Jetpack Compose testing

### Manual Testing Checklist
- [ ] All 4 tabs accessible and functional
- [ ] Applications list displays with filters
- [ ] Search works for company/position
- [ ] Create application modal opens and saves
- [ ] Emails group by application correctly
- [ ] Notifications timeline displays chronologically
- [ ] Settings profile shows correct user info
- [ ] Logout works and clears session
- [ ] Sync status displays and updates
- [ ] Handles network disconnection gracefully

---

## 8. Rollout Plan

### Phase 4.1 (MVP - Week 1-2)
- **Applications Tab:** Full implementation (list, filter, search, create)
- **Emails Tab:** Full implementation (grouping, basic viewing)
- **Notifications Tab:** Activity timeline (basic timeline display)
- **Settings Tab:** Profile display, logout
- **Bottom Tab Navigation:** All 4 tabs functional
- **Platform:** iOS first, then Android adaptation

### Phase 4.2 (Enhancements - Week 3+)
- Edit/Delete applications
- Email detail view with Claude analysis badges
- Manual link email to application
- Manual sync button with status feedback
- User profile editing
- Data export functionality
- Dark mode support (if time permits)

---

## 9. Design Principles & Rationale

1. **iOS HIG Native:** Authentic iOS UX (familiar to iOS users) — trade-off: Android will use Material Design 3
2. **Detailed Cards Layout:** Rich context (company, location, email count) in one glance — trade-off: fewer items per screen, more scrolling
3. **Color-Coded Status:** Quick visual scanning of application status — enhances scannability
4. **Bottom Tab Navigation:** Thumb-friendly, always visible, industry standard on mobile
5. **Activity Timeline:** Helps users track progress and upcoming deadlines at a glance
6. **Grouped Emails:** Logical organization by application, reduces cognitive load

---

## 10. Success Criteria

- ✅ All 4 tabs fully functional (Applications, Emails, Notifications, Settings)
- ✅ Applications can be created, viewed, filtered, searched
- ✅ Emails grouped and viewable by application
- ✅ Notifications show activity timeline
- ✅ Settings allow logout and account info viewing
- ✅ iOS app builds and runs without errors
- ✅ Android app builds and runs without errors
- ✅ Navigation between tabs preserves scroll state
- ✅ Sync status displays correctly
- ✅ User can logout and re-login

---

**Next Steps:** Implementation plan (Phase 4 Frontend Development)