# Settings Page Import & Database Sync Guide

## Overview
The Settings page (Einstellungen) import now automatically syncs data to the database while maintaining localStorage functionality.

## Data Flow

### Before (Settings Import Only)
```
Export from Settings
  ↓
Import JSON (bewerbungen format)
  ↓
Save to localStorage only
  ↓
❌ Data lost on logout/reload
```

### After (Settings Import + Database Sync)
```
Export from Settings
  ↓
Import JSON (bewerbungen format)
  ↓
Save to localStorage (for offline use)
  ↓
Convert to database format (applications)
  ↓
API call to /api/backup/import
  ↓
✅ Data persisted in database
```

## Format Conversion

The Settings page automatically converts from the Settings format to the Database format:

| Settings Format | Database Format | Example |
|---|---|---|
| `firma` | `company` | "Acme Corp" |
| `position` | `position` | "Developer" |
| `status` | `status` | "beworben" → "applied" |
| `datum` | `applied_date` | "2026-04-24" |
| `createdAt` | `created_at` | ISO timestamp |
| `updatedAt` | `updated_at` | ISO timestamp |

**Note:** Fields like `gehalt`, `ort`, `email`, `quelle`, `link`, `notizen` are stored in localStorage only (not in database).

## What Happens During Import

1. **User selects JSON file from Settings page**
2. **File is parsed** - expects `bewerbungen` array
3. **Data is processed**:
   - Added to `state.bewerbungen` (in-memory)
   - Saved to localStorage
   - UI is updated with new applications
4. **Database sync** (NEW):
   - Converted to `applications` format
   - Sent to `/api/backup/import` API
   - Creates a backup record
   - Data is now in the database

## Error Handling

### If API call fails:
- ✅ Data is already saved to localStorage (safe)
- ⚠️ Warning toast shown: "Offline-Speicherung OK, aber Datenbank-Sync fehlgeschlagen"
- The user can retry later or manually use the Backup page

### If file format is wrong:
- ❌ File must have `bewerbungen` array at top level
- Error message: "Keine Bewerbungen in der Datei gefunden!"

## Usage

### Import a Settings Backup
1. Go to **Einstellungen** (Settings) tab
2. Click **Import**
3. Select a JSON file (exported from Settings)
4. Confirm the import
5. ✅ Data is now in both localStorage AND database

### Verify Data is in Database
1. Go to **Sicherung & Export** (Backup & Export) tab
2. Look at **Backup History**
3. A new `manual_import` backup should appear
4. Click **View** to see the imported applications

## Technical Implementation

### Files Modified
- `index.html` - Updated `handleImport()` function
- `frontend/js/backup-client.js` - BackupClient API wrapper

### Code Changes
```javascript
// After saving to localStorage, the new code:
1. Converts bewerbungen → applications format
2. Creates backup JSON file
3. Calls backupClient.importBackup(file)
4. Shows success/error message
```

## Troubleshooting

### Import shows success but data isn't in database

**Check:**
1. Are you logged in? (Check for "Bitte bestätige deine E-Mail" error)
2. Is the backend running? (Check network tab for /api/backup/import call)
3. Look at browser console for error messages

**Solution:**
- Reload the page and try importing again
- If error persists, check the backup page to see if API is working

### Data appears in Settings but disappears after reload

**This means:** Data is in localStorage but NOT in database

**Cause:** Database sync failed (check browser console)

**Fix:**
- Try importing again - the API might be working now
- Or use the Backup page to manually import via the API

### File import fails with "Invalid JSON or Error"

**Check:**
1. Is the file valid JSON? (Use a JSON validator)
2. Does it have `bewerbungen` array? (Not `applications`)
3. Is the file from the Settings export?

## API Endpoint Details

### POST /api/backup/import

**Expected Format:**
```json
{
  "applications": [
    {
      "id": "string",
      "company": "string",
      "position": "string",
      "status": "string",
      "applied_date": "2026-04-24",
      "created_at": "2026-04-24T10:00:00Z",
      "updated_at": "2026-04-24T10:00:00Z"
    }
  ],
  "emails": []
}
```

**Response:**
```json
{
  "message": "Import completed",
  "imported_applications": 5,
  "imported_emails": 0,
  "backup_version": 12
}
```

## See Also
- [Backup & Export Guide](BACKUP_GUIDE.md)
- [Settings Page Documentation](SETTINGS_GUIDE.md)
