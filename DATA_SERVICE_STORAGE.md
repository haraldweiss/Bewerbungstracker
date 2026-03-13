# 📦 Data Service - SQLite Storage Architecture

## Overview

The Bewerbungs-Tracker now uses **SQLite** for persistent data storage instead of browser localStorage. This provides:

- ✅ **Persistent Storage**: Data survives browser cache clears and reinstalls
- ✅ **Better Reliability**: SQLite is more robust than localStorage
- ✅ **Offline Fallback**: Falls back to localStorage if service is unavailable
- ✅ **Advanced Queries**: SQLite supports complex queries for future features
- ✅ **Backup/Restore**: Export/import full database snapshots

## Architecture

```
┌─────────────────────────────────────────────┐
│     Browser (index.html)                    │
│  - Frontend UI                              │
│  - localStorage cache (fallback)            │
└────────────┬────────────────────────────────┘
             │ HTTP REST API (localhost:8767)
             │
┌────────────▼────────────────────────────────┐
│  Data Service (data_service.py)             │
│  - REST API Server                          │
│  - SQLite Database Management               │
│  - Backup/Restore                           │
└────────────┬────────────────────────────────┘
             │
┌────────────▼────────────────────────────────┐
│  SQLite Database (bewerbungen.db)           │
│  - Applications Table                       │
│  - Settings Table                           │
│  - Indices for Performance                  │
└─────────────────────────────────────────────┘
```

## Database Schema

### `bewerbungen` Table (Applications)

```sql
CREATE TABLE bewerbungen (
    id TEXT PRIMARY KEY,                -- Unique application ID
    firma TEXT NOT NULL,                -- Company name
    position TEXT,                      -- Job position
    status TEXT,                        -- Status (beworben, interview, etc)
    datum TEXT,                         -- Application date
    gehalt TEXT,                        -- Salary
    ort TEXT,                           -- Location
    email TEXT,                         -- Contact email
    quelle TEXT,                        -- Source (gmail, script, imap, etc)
    link TEXT,                          -- Job posting link
    notizen TEXT,                       -- Notes
    createdAt TEXT,                     -- Creation timestamp
    updatedAt TEXT                      -- Last update timestamp
);

-- Indices for fast lookups
CREATE INDEX idx_status ON bewerbungen(status);
CREATE INDEX idx_firma ON bewerbungen(firma);
CREATE INDEX idx_createdAt ON bewerbungen(createdAt);
```

### `settings` Table

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,               -- Setting key
    value TEXT                          -- JSON-encoded value
);
```

## REST API Endpoints

### Applications (Bewerbungen)

#### List All Applications
```
GET /api/applications
Response:
{
  "status": "ok",
  "count": 5,
  "applications": [
    {
      "id": "bew_1234567890_abc",
      "firma": "Microsoft GmbH",
      "position": "Software Engineer",
      "status": "interview",
      "datum": "2026-03-10",
      ...
    }
  ]
}
```

#### Get Single Application
```
GET /api/applications/:id
Response:
{
  "status": "ok",
  "application": { ... }
}
```

#### Create Application
```
POST /api/applications
Content-Type: application/json

{
  "id": "bew_1234567890_abc",
  "firma": "Microsoft GmbH",
  "position": "Software Engineer",
  "status": "beworben",
  "datum": "2026-03-10",
  "gehalt": "80000",
  "ort": "Munich",
  "email": "contact@microsoft.de",
  "quelle": "script",
  "link": "https://jobs.microsoft.com/...",
  "notizen": "Good match",
  "createdAt": "2026-03-10T10:00:00Z",
  "updatedAt": "2026-03-10T10:00:00Z"
}

Response: 201 Created
```

#### Update Application
```
PUT /api/applications/:id
Content-Type: application/json

{
  "status": "interview",
  "notizen": "Phone interview scheduled"
}

Response: 200 OK
```

#### Delete Application
```
DELETE /api/applications/:id
Response: 200 OK
```

### Settings

#### Get All Settings
```
GET /api/settings
Response:
{
  "status": "ok",
  "settings": {
    "keywords": "Bewerbung,Stelle,...",
    "ghostingDays": 30,
    "emailSummaryEnabled": true,
    ...
  }
}
```

#### Update Settings
```
PUT /api/settings
Content-Type: application/json

{
  "emailSummaryEnabled": true,
  "emailSummaryRecipient": "user@example.com",
  "ghostingDays": 45
}

Response: 200 OK
```

### Backup & Restore

#### Export All Data
```
GET /api/export
Response:
{
  "bewerbungen": [...],
  "settings": {...},
  "exportedAt": "2026-03-13T14:00:00Z"
}
```

#### Import Data
```
POST /api/import
Content-Type: application/json

{
  "bewerbungen": [...],
  "settings": {...}
}

Response: 200 OK
```

### Status

#### Service Status
```
GET /api/status
Response:
{
  "status": "ok",
  "service": "Bewerbungs-Tracker Data Service"
}
```

## Frontend Integration

The frontend (`index.html`) automatically:

1. **On Startup** (`init()`):
   - Calls `/api/applications` to load applications
   - Calls `/api/settings` to load settings
   - Falls back to localStorage if Data Service is unavailable

2. **On Save** (`saveToStorage()`):
   - Syncs all applications to Data Service
   - Updates settings on Data Service
   - Falls back to localStorage if offline

3. **On Import** (`handleImport()`):
   - Imports applications and settings to Data Service
   - Updates SQLite database

4. **Browser Console Logs**:
   - `✅ Data loaded from SQLite (Data Service)` - Successfully loaded
   - `⚠️ Data Service unavailable, loading from localStorage` - Using fallback

## Offline Functionality

If the Data Service is not running or unavailable:

1. Frontend still works normally
2. Data is cached in browser localStorage
3. Console shows warning message
4. When Data Service comes back online, data syncs automatically

This ensures the application works even if the backend service crashes temporarily.

## Database File Location

The SQLite database file is created in the application's root directory:

```
Bewerbungstracker/
├── index.html
├── data_service.py
├── email_service.py
├── bewerbungen.db ← Database file (auto-created)
└── ...
```

## Starting the Data Service

### Using Startup Scripts

```bash
# macOS & Linux
./start.sh

# Windows CMD
start.bat

# Windows PowerShell
.\start.ps1
```

### Manual Start

```bash
python3 data_service.py
```

Expected output:
```
✅ Bewerbungs-Tracker Data Service running on http://127.0.0.1:8767
📦 SQLite database: bewerbungen.db
📚 API Endpoints:
   GET  /api/applications - List all applications
   POST /api/applications - Create application
   ...
```

## Performance

### Indices

The Data Service creates three indices for fast lookups:

- `idx_status` - Fast filtering by application status
- `idx_firma` - Fast search by company name
- `idx_createdAt` - Fast sorting by date

### Response Times

- List applications: ~5-10ms (typical)
- Get single application: ~1-2ms
- Create/Update: ~2-5ms
- Full export: ~20-50ms

## Backup Strategy

### Automatic Backups

Currently, the application exports backups to JSON files manually:

1. Click **"📥 JSON"** in the footer
2. Save `bewerbungen_backup_YYYY-MM-DD.json`
3. Browser downloads the file

### Restore from Backup

1. Click **"📤 Importieren"** button
2. Select backup JSON file
3. Choose merge/replace strategy

### Scheduled Backups (Planned)

Future feature: Automatic daily backups to SQLite with:
- Version history
- Point-in-time restore
- Automatic cleanup of old backups

## Security

### Authentication

Currently, Data Service binds to **127.0.0.1:8767** (localhost only):
- Not accessible from other machines
- No authentication required (local-only access)
- Suitable for local development

### Future: Remote Deployment

For remote deployments, consider adding:
- API key authentication
- HTTPS/TLS encryption
- Rate limiting
- CORS validation

## Troubleshooting

### "Data Service unavailable" Warning

**Problem**: Frontend shows warning and uses localStorage fallback

**Solutions**:
1. Ensure `python3 data_service.py` is running
2. Check port 8767 is not blocked: `lsof -i :8767`
3. Restart Data Service
4. Check console for specific error messages

### Database is Locked

**Problem**: SQLite error "database is locked"

**Solution**: Only one Data Service instance can write to the database
- Kill any duplicate processes: `pkill -f data_service.py`
- Restart the service

### Slow Performance

**Problem**: Queries are slow

**Possible causes**:
1. Large database (1000+ applications) - not expected
2. System disk is slow
3. Antivirus scanning database file

**Solution**:
- Check database size: `ls -lh bewerbungen.db`
- Run `vacuum` to optimize: `sqlite3 bewerbungen.db "VACUUM;"`

## Switching Back to localStorage

If you need to use localStorage instead (not recommended):

1. Edit `loadFromStorage()` in index.html
2. Remove Data Service API calls
3. Keep only the localStorage fallback code

However, this loses the benefits of persistent SQLite storage.

## Future Enhancements

Planned improvements:

- [ ] Full-text search across applications
- [ ] Advanced filtering and sorting
- [ ] Data export to CSV/Excel
- [ ] Scheduled database backups
- [ ] Database encryption
- [ ] Multi-user support
- [ ] Cloud sync (optional)

---

**Version**: 1.0
**Last Updated**: 2026-03-13
**Database Format**: SQLite 3
