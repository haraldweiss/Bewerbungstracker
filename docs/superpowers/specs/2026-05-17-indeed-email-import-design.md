# Indeed Email Import Feature — Design Spec

**Date:** 2026-05-17  
**Author:** Harald Weiss  
**Status:** Approved for Implementation  
**Approach:** C — Smart Interactive Dedup + Rejection-Window Protection

---

## Overview

Enable importing job recommendations from Indeed emails as a new automated job source. Users can trigger on-demand imports of their Indeed folder. The system intelligently deduplicates jobs and protects against overwriting rejections (with user control for genuinely new positions from previously-rejected companies).

**Key Constraint:** Jobs with `Application.status='absage'` from the same company within the rejection window (default 180 days, configurable) must not be silently overwritten. User gets interactive choice: "Import as New Position" or "Skip."

---

## Architecture & Data Model

### New Components

**1. JobSource Type: `indeed_email`**
- User-owned source (not global)
- Config: `{ "imap_folder": "Indeed" }` — user configurable in Settings
- Tracks: `last_crawled_at` (timestamp of last successful import)
- Tracks: `consecutive_failures` (auto-disable after 5 failures)

**2. Email Parser (Backend Service)**
- Regex-based extraction of Indeed email format (job title, company, location, link, deadline)
- Fallback to AI (claude/ollama/openai via ai-provider-service) if regex incomplete
- Logs cost against `user.job_daily_budget_cents` (Ollama costs 0€)
- Retry logic: 5 attempts with exponential backoff, then manual-only flag

**3. Dedup & Rejection Check Logic**
- **Step A:** Link-match — `SELECT raw_job WHERE url = ? AND source_id = indeed_source`
- **Step B:** Company+Title fuzzy match — catch jobs from other sources
- **Step C:** Rejection-window check — `SELECT application WHERE company=? AND status='absage' AND (NOW() - updated_at) < user.job_reject_window_days`
- Duplicates silently skipped (no dialog entry)
- Blocked jobs marked for user approval in dialog

**4. Frontend Dialog (New UI)**
- **Tab 1: "Neue Jobs (N)"** — Auto-import on user confirm
- **Tab 2: "Absage-Block (N)"** — User chooses per job: `[✅ Als neue Stelle importieren]` / `[❌ Ignorieren]`
- Global action: `[✅ Jetzt importieren]` / `[❌ Abbrechen]`

**5. Email Retention Policy**
- User setting: `email_retention_days` (default 90, configurable in Settings)
- Auto-cleanup: daily job deletes emails older than retention window
- Force-cleanup: if disk threshold exceeded, delete oldest emails first
- Never delete if `Email.matched_application_id IS NOT NULL`

---

## Database Changes

### New/Modified Columns

**User Table:**
- ✅ `job_reject_filter_enabled` (exists) — re-use for Indeed import filter
- ✅ `job_reject_window_days` (exists, default 180) — re-use for rejection window
- NEW (future): `email_retention_days` (INTEGER, default 90, nullable) — per-user email cleanup window

**JobSource Table:**
- ✅ Existing structure supports `type='indeed_email'`, `config` JSON, `last_crawled_at`, `consecutive_failures`
- No changes needed

**RawJob Table:**
- ✅ Existing structure (`source_id`, `external_id`, `url`, `title`, `company`, `location`) fits Indeed data
- No changes needed

**JobMatch Table:**
- ✅ Existing structure (`raw_job_id`, `user_id`, `status`) sufficient
- Note: `status` can be 'new', 'seen', 'imported', 'dismissed' — no new statuses needed

**Email Table:**
- ✅ Existing structure (`user_id`, `message_id`, `subject`, `body`, `timestamp`, `created_at`) sufficient for tracking

---

## Data Flow

### 1. User Triggers Import

```
POST /api/jobs/import-from-email
Body: {
  source_type: 'indeed_email',
  folder_name: 'Indeed'  // user-configured in JobSource.config
}
```

### 2. Fetch New Emails Only

- Query `JobSource.last_crawled_at` (or NULL if first run)
- Call IMAP-Proxy: `GET /imap/folder/{folder_name}/messages?since={last_crawled_at}`
- Returns: array of new emails `[{ from, subject, body, html_body, date, message_id }, ...]`

### 3. Parse Jobs (Regex + AI)

For each email:
1. **Regex extraction:** job_title, company, location, link, deadline
2. **If incomplete:** AI call to ai-provider-service
   - Provider: `user.ai_provider` + fallback to `user.ai_provider_backup`
   - Prompt: "Extract structured job data: {title, company, location, link, deadline}"
   - Log: `ApiCall` (endpoint, tokens, cost)
   - Deduct cost from `user.job_daily_budget_cents` (skip if Ollama)
3. **Create RawJob:** `INSERT INTO raw_jobs (source_id, title, company, location, url, description, posted_at, external_id)`

### 4. Dedup & Rejection Check

For each parsed job:
```
Link-match?     → EXISTS raw_job.url → SKIP (duplicate)
Company+Title?  → fuzzy match existing → SKIP (duplicate)
Rejection-window? → EXISTS app(company, status='absage', age<180d) → BLOCK
                 → MARK 'rejection_blocked' with reason
Else            → MARK 'new'
```

Result: `{ new: [...], rejection_blocked: [...] }`

### 5. Return to Frontend

```json
{
  "status": "needs_approval",
  "summary": { "total": 5, "new": 2, "rejection_blocked": 2, "duplicates": 1 },
  "new_jobs": [
    { "title": "...", "company": "...", "location": "...", "link": "..." }
  ],
  "blocked_jobs": [
    {
      "title": "...",
      "company": "...",
      "location": "...",
      "link": "...",
      "rejection_date": "2026-05-01",
      "days_remaining": 90
    }
  ]
}
```

### 6. Frontend Shows Dialog

Two tabs:
- **New Jobs:** Shows count, list (auto-import on confirm)
- **Blocked Jobs:** For each job — show company, position, rejection date
  - User chooses: `[✅ Import as New]` or `[❌ Skip]`

### 7. Process User Decision

```
For each blocked_job where user chose 'import_as_new':
  → CREATE new RawJob (separate from rejection app)
  
For each new_job:
  → CREATE RawJob
  
For all jobs:
  → CREATE JobMatch (user_id, raw_job_id, status='new')

Update: JobSource.last_crawled_at = NOW()
Return: { imported: 4, skipped: 1 }
```

### 8. Frontend Confirmation

```
✅ 4 neue Job-Vorschläge hinzugefügt.
→ Tab 🔍 Job-Vorschläge ansehen
```

---

## Error Handling & Retries

### Email Parsing Failures

- **Attempt 1-5:** Auto-retry with exponential backoff (30s, 2m, 10m, 10m, 10m)
- **After 5 failures:** 
  - Set `JobSource.enabled = false` (soft-disable)
  - Set `JobSource.last_error = "Max retries exceeded (5x). Manual retry only."`
  - Frontend shows: "🚩 Indeed import paused (too many errors). Retry manually in Settings."
- **Manual retry:** User clicks "Retry" in Settings → resets `consecutive_failures`, tries again

### AI Provider Failure

- Primary provider fails → fallback to `user.ai_provider_backup`
- Both fail → email skipped, cost=0€, marked for retry
- Returns: `{ status: 'ai_error', message: 'AI parser unavailable. Retry later.' }`

### Budget Exceeded

- If `job_daily_budget_cents` <= 0 → reject import
- Returns: `{ status: 'budget_exceeded', message: 'Daily AI budget exceeded. Retry tomorrow.' }`

### IMAP Connection Failure

- IMAP-Proxy returns error → `JobSource.consecutive_failures++`
- If `consecutive_failures >= 5` → auto-disable source
- Frontend: "❌ Could not connect to Indeed folder. Check email settings."

### Concurrent Imports

- Handled via `JobSource.last_crawled_at`:
  - 1st import fetches new emails, updates `last_crawled_at`
  - 2nd import (same user, seconds later) fetches 0 new emails → silent return

### Network Interruption

- Transactions: `JobSource.last_crawled_at` only updated after all JobMatches created
- If error mid-import → rollback, user can retry (no duplicate JobMatches)

---

## Testing Strategy

### Unit Tests

1. **Parser (Regex + AI)**
   - Valid Indeed email → all fields extracted
   - Malformed email → graceful AI fallback
   - AI returns null → error logged, email skipped
   - Ollama cost = 0€, Claude cost = N€

2. **Dedup**
   - Link-match: duplicate URL → skip
   - Company+Title: fuzzy match → skip
   - No match → new

3. **Rejection Window**
   - Company rejected 90 days ago (window=180) → blocked
   - Company rejected 190 days ago (window=180) → NOT blocked
   - Status != 'absage' → NOT blocked

4. **Retry Logic**
   - 1st failure → retry with backoff
   - 5th failure → disabled, manual-only
   - Manual retry clears counter

### Integration Tests

1. **End-to-End: 5 emails imported**
   - 2 new, 1 duplicate (silent), 2 blocked
   - User approves 1 blocked job
   - Result: 3 JobMatches created
   - `JobSource.last_crawled_at` updated
   - Rerun import → 0 new emails (only new fetched)

2. **AI Fallback**
   - Primary provider fails → fallback triggered
   - Both fail → email skipped, cost=0

3. **Budget Enforcement**
   - Import uses 50¢ from 200¢ → 150¢ remaining
   - Reach limit → next import blocked until reset

4. **IMAP Errors**
   - Folder not found → clear error message
   - Auth fails → consecutive_failures++
   - 5 failures → source auto-disabled

### Manual Verification

- [ ] Settings → "📡 Job-Quellen" shows "Import from Indeed Folder" button
- [ ] Click opens folder selector, shows parsing progress
- [ ] Dialog displays correct tabs (new, blocked)
- [ ] User approve/skip blocked jobs → correct JobMatches created
- [ ] Rerun → shows "0 new emails"
- [ ] ApiCall log shows correct costs (0€ for Ollama, N€ for Claude)
- [ ] Simulate AI timeout → retries, then flags
- [ ] Check `job_reject_window_days` setting → blocks/unblocks as expected
- [ ] Email retention: old emails auto-deleted after `email_retention_days`

---

## Frontend Changes

**Settings → "📡 Job-Quellen"**
- Existing: CRUD for custom job sources
- NEW: Button "📧 Import from Indeed Folder"
  - Opens modal: Folder name selector (default "Indeed")
  - Shows parsing progress
  - Shows approval dialog (2 tabs)
- NEW: Setting `email_retention_days` (if not exists)

**Job-Vorschläge Tab**
- No changes (imports appear as regular JobMatches)

---

## Backend Changes

**New Endpoints:**
- `POST /api/jobs/import-from-email` — trigger import
  - Params: `source_type`, `folder_name`
  - Returns: `{ status, summary, new_jobs, blocked_jobs }`

**Modified Endpoints:**
- `POST /api/jobs/approve-email-import` — user confirms/skips blocked jobs
  - Body: `{ blocked_job_id, action: 'import_as_new' | 'skip' }`

**New Background Jobs:**
- Email retention cleanup: daily delete old emails (if `email_retention_days` configured)
- Retry failed sources: daily check `JobSource.consecutive_failures < 5 AND last_error IS NOT NULL`

---

## Constraints & Assumptions

1. **IMAP-Proxy assumes Indeed folder exists** — user must set up or we guide them
2. **Indeed email format is stable** — regex patterns may need maintenance if Indeed changes
3. **AI cost is predictable** — cost estimate per email ~0.2€ (Claude Haiku)
4. **Rejection window is monotonic** — once status='absage', it stays until window expires or user upgrades
5. **User can have only one Indeed source** (assumption, not enforced — could have multiple folders)

---

## Success Criteria

- ✅ User can import Indeed emails on-demand without manual job entry
- ✅ No duplicate jobs in suggestions
- ✅ Rejected companies protected (can't overwrite status without user choice)
- ✅ AI parser fallback keeps feature working even with regex failures
- ✅ Cost tracking prevents budget overruns
- ✅ Email storage is configurable and auto-cleaned

---

## Open Questions / Future Phases

1. **Multiple Indeed folders?** Current design assumes 1 folder per source. Could extend.
2. **Email→Insight extraction** (Phase 2): Extract interview dates, salary feedback, etc. from emails
3. **BYOK for Indeed scraping?** User's own Indeed API key instead of email-based
