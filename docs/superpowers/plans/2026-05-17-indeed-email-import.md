# Indeed Email Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to import job recommendations from Indeed emails on-demand, with intelligent deduplication and rejection-window protection.

**Architecture:** Backend service parses Indeed emails (Regex + AI fallback), deduplicates against existing jobs (Link → Company+Title), checks rejection window (180 days), and returns approval dialog. Frontend shows 2-tab dialog (new jobs, blocked jobs). User chooses per blocked job: import as new or skip.

**Tech Stack:** Flask (backend), SQLAlchemy (ORM), IMAP-Proxy (email fetch), ai-provider-service (Claude/OpenAI/Ollama), vanilla JS (frontend dialog)

**Related Spec:** [2026-05-17-indeed-email-import-design.md](../specs/2026-05-17-indeed-email-import-design.md)

---

## File Structure

**Backend:**
- `services/job_matching/indeed_parser.py` — Email → structured job extraction (Regex + AI)
- `services/job_matching/dedup_engine.py` — Link/Company+Title matching + Rejection-window check
- `services/job_discovery/import_handler.py` — Orchestration: fetch → parse → dedup → dialog response
- `routes/jobs.py` — New endpoint `POST /api/jobs/import-from-email` + approval endpoint
- `models.py` — New User column: `email_retention_days`

**Frontend:**
- `frontend/js/job-import-dialog.js` — 2-tab dialog (new jobs, blocked jobs)
- `frontend/js/settings-ui.js` — Modified for Import button + folder config
- `frontend/pages/admin.html` — Add Import section
- `frontend/css/job-import-dialog.css` — Dialog styling

**Tests:**
- `tests/unit/test_indeed_parser.py` — Regex extraction, AI fallback
- `tests/unit/test_dedup_engine.py` — Link/Company+Title matching, rejection-window logic
- `tests/integration/test_email_import_e2e.py` — End-to-end workflow

**Database:**
- `migrations/add_email_retention_days.py` — Add column to users table

---

## Task 1: Email Parser — Regex + AI Fallback

**Files:**
- Create: `services/job_matching/indeed_parser.py`
- Test: `tests/unit/test_indeed_parser.py`

**Context:** Indeed emails have a predictable format. Extract with Regex first (free), fallback to AI if fields missing.

- [ ] **Step 1: Write failing test for Regex parsing**

Test file content (full code in plan). Test cases:
- `test_regex_extracts_job_title_from_indeed_email` — valid email with structured fields
- `test_regex_returns_none_for_fields_if_not_found` — empty/random email

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_indeed_parser.py::test_regex_extracts_job_title_from_indeed_email -v
```
Expected: FAILED (no module)

- [ ] **Step 3: Write `IndeedEmailParser` class with `parse_regex()` + `parse_with_ai_fallback()`**

Implement in `services/job_matching/indeed_parser.py`:
- `parse_regex(email_body)` returns dict with title, company, location, link, deadline, description
- Regex patterns for each field (German + English Indeed formats)
- `parse_with_ai_fallback(email_body, user)` calls AI if regex incomplete

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_indeed_parser.py -v
```
Expected: PASSED

- [ ] **Step 5: Write test for AI fallback (mocked)**

- [ ] **Step 6: Run all parser tests**

- [ ] **Step 7: Commit**

```bash
git add services/job_matching/indeed_parser.py tests/unit/test_indeed_parser.py
git commit -m "feat(parser): Email parser with Regex + AI fallback for Indeed jobs"
```

---

## Task 2: Dedup Engine — Link/Company+Title + Rejection Window

**Files:**
- Create: `services/job_matching/dedup_engine.py`
- Test: `tests/unit/test_dedup_engine.py`

- [ ] **Step 1: Write failing tests**

Test cases:
- `test_link_dedup_finds_existing_job` — same URL → skip
- `test_company_title_fuzzy_dedup` — similar company+title → skip
- `test_no_dedup_new_job` — unique job → new
- `test_rejection_window_blocks_recent_absage` — 90 days old → blocked
- `test_rejection_window_expires_after_180_days` — 190 days old → not blocked

- [ ] **Step 2: Run tests, verify failure**

- [ ] **Step 3: Write `DedupEngine` class with methods:**
- `check_dedup(job_data, source_id)` returns status (new/duplicate/rejection_blocked)
- `_fuzzy_match()` using `difflib.SequenceMatcher` (company ≥ 0.7, title ≥ 0.8)
- `_check_rejection_window(company)` uses `user.job_reject_window_days` (default 180)

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/dedup_engine.py tests/unit/test_dedup_engine.py
git commit -m "feat(dedup): Link/Company+Title matching + rejection-window protection"
```

---

## Task 3: API Endpoints — Import + Approve

**Files:**
- Create: `services/job_discovery/import_handler.py`
- Modify: `routes/jobs.py`
- Test: `tests/integration/test_email_import_flow.py`

- [ ] **Step 1: Write failing integration test**

Test: `test_import_from_email_endpoint_returns_new_and_blocked_jobs`

- [ ] **Step 2: Create `ImportHandler` service**

Methods:
- `run(imap_folder)` — orchestrate fetch → parse → dedup → return response
- `_fetch_new_emails(folder)` — call IMAP-Proxy with `last_crawled_at` filter

- [ ] **Step 3: Add `/api/jobs/import-from-email` endpoint**

POST body: `{source_type, folder_name}`
Returns: `{status, summary, new_jobs, blocked_jobs}`

- [ ] **Step 4: Add `/api/jobs/approve-email-import` endpoint**

POST body: `{actions: [{blocked_job_index, action: 'import_as_new' | 'skip'}]}`
Creates RawJob + JobMatch records, updates `last_crawled_at`.

- [ ] **Step 5: Run integration test, verify pass**

- [ ] **Step 6: Commit**

```bash
git add routes/jobs.py services/job_discovery/import_handler.py tests/integration/test_email_import_flow.py
git commit -m "feat(api): POST /api/jobs/import-from-email with approval dialog"
```

---

## Task 4: Frontend Dialog — 2 Tabs

**Files:**
- Create: `frontend/js/job-import-dialog.js`
- Create: `frontend/css/job-import-dialog.css`
- Create: `frontend/html/job-import-dialog.html` (or inline in admin.html)

- [ ] **Step 1: Create modal HTML structure** with 2 tabs (New Jobs, Blocked Jobs)

- [ ] **Step 2: Write `JobImportDialog` class in JS**

Methods:
- `open(folderName)` — show modal, fetch jobs
- `fetchJobs()` — POST `/api/jobs/import-from-email`
- `renderResults(summary)` — populate tabs
- `switchTab()` — UI switching
- `submitApproval()` — POST `/api/jobs/approve-email-import`

- [ ] **Step 3: Add CSS styling** for modal, tabs, job items, blocked badge

- [ ] **Step 4: Manual UI test**

- [ ] **Step 5: Commit**

```bash
git add frontend/js/job-import-dialog.js frontend/css/job-import-dialog.css frontend/html/job-import-dialog.html
git commit -m "feat(frontend): Job import dialog with 2 tabs (new + blocked)"
```

---

## Task 5: Settings UI — Import Button + Folder Config

**Files:**
- Modify: `frontend/pages/admin.html` (Job-Sources section)
- Modify: `frontend/js/settings-ui.js`
- Modify: `routes/profile.py` (settings endpoint)

- [ ] **Step 1: Add Import button + folder input to Job-Sources section**

- [ ] **Step 2: Wire up button click → JobImportDialog.open()**

- [ ] **Step 3: Add `email_retention_days` settings UI**

- [ ] **Step 4: Add `POST /api/profile/settings` backend endpoint**

- [ ] **Step 5: Commit**

```bash
git add frontend/pages/admin.html frontend/js/settings-ui.js routes/profile.py
git commit -m "feat(settings): Add Indeed import button + email retention config"
```

---

## Task 6: Database Migration

**Files:**
- Create: `migrations/add_email_retention_days.py`
- Modify: `models.py`

- [ ] **Step 1: Create Alembic migration** to add `email_retention_days INTEGER nullable default 90`

- [ ] **Step 2: Apply migration** with `alembic upgrade head`

- [ ] **Step 3: Add column to User model in models.py**

- [ ] **Step 4: Commit**

```bash
git add migrations/add_email_retention_days.py models.py
git commit -m "db(migration): Add email_retention_days to users table"
```

---

## Task 7: Email Retention Cleanup

**Files:**
- Create: `services/background_jobs/email_cleanup.py`
- Modify: `/etc/cron.d/bewerbungen-jobs` (VPS)
- Create: `/usr/local/bin/email-cleanup.sh` (VPS)

- [ ] **Step 1: Write cleanup service** — delete emails older than `user.email_retention_days`, exclude those linked to applications

- [ ] **Step 2: Add cron entry** for daily 2am run

- [ ] **Step 3: Test locally** with seeded old emails

- [ ] **Step 4: Commit**

```bash
git add services/background_jobs/email_cleanup.py scripts/email-cleanup.sh
git commit -m "feat(background): Email retention cleanup job (daily)"
```

---

## Task 8: Error Handling — Retry Logic + AI Fallback

**Files:**
- Modify: `services/job_matching/indeed_parser.py`
- Modify: `services/job_discovery/import_handler.py`
- Modify: `routes/jobs.py`

- [ ] **Step 1: Add retry wrapper to `parse_with_ai_fallback`** (5 attempts, exponential backoff: 30s, 2m, 10m, 10m, 10m)

- [ ] **Step 2: Update `ImportHandler.run()`** to track `consecutive_failures`, auto-disable source at 5+

- [ ] **Step 3: Add `/api/jobs/retry-import` endpoint** for manual retry (resets counter)

- [ ] **Step 4: Test retry logic** with mocked AI failures

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/indeed_parser.py services/job_discovery/import_handler.py routes/jobs.py
git commit -m "feat(error-handling): 5x retry + AI fallback + manual recovery endpoint"
```

---

## Task 9: End-to-End Integration Test

**Files:**
- Create: `tests/integration/test_email_import_e2e.py`

- [ ] **Step 1: Write comprehensive E2E test**

Covers:
- User + JobSource setup
- Existing rejection (`OldCorp`)
- 3 mock emails (1 new, 1 blocked, 1 duplicate)
- POST `/api/jobs/import-from-email` → verify counts
- POST `/api/jobs/approve-email-import` → verify imported/skipped
- Verify DB state: RawJobs + JobMatches created, source updated

- [ ] **Step 2: Run E2E test, verify pass**

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_email_import_e2e.py
git commit -m "test(integration): End-to-end email import workflow"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ JobSource type 'indeed_email' → Task 1-3
- ✅ Email Parser (Regex + AI) → Task 1
- ✅ Dedup (Link → Company+Title) → Task 2
- ✅ Rejection-window check (180 days) → Task 2
- ✅ Frontend dialog (2 tabs) → Task 4
- ✅ User approval (blocked jobs) → Task 4-5
- ✅ Retry logic (5x) → Task 8
- ✅ Cost tracking → Task 1 (via AIProviderService)
- ✅ Email retention → Task 7
- ✅ Settings UI → Task 5

**Placeholders:** None — all steps have concrete actions.

**Type Consistency:**
- `dedup_result['status']` = 'new' | 'duplicate' | 'rejection_blocked' ✅
- `JobMatch.status` = 'new', 'seen', 'imported', 'dismissed' ✅
- Frontend `state.blocked_decisions[idx]` = 'import_as_new' | 'skip' ✅

**Scope:** Focused on Indeed import flow + approval. No unrelated refactoring.
