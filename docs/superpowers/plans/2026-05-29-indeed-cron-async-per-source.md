# Indeed-Email Cron → Async per-Source Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Agent routing (per AGENTS.md):** This is an `api/` → `services/` extraction-style refactor — **opencode (Throughput)** territory. The IMAP credential code itself is NOT being modified — only its calling context moves from a sync gunicorn worker into the existing async task-queue. Claude Code (Care) takes over for **Task 5 (Production deploy to IONOS)** — opencode hands back after Task 4 passes locally.

**Goal:** Stop the hourly 4-minute "database is locked" outage on production by moving `/api/jobs/indeed-email-import-all` from a synchronous gunicorn handler doing one giant write transaction into per-source async tasks, each with its own short commit.

**Architecture:**
- Endpoint becomes a thin enumerator: SELECT eligible sources, enqueue ONE `cron_indeed_email_import_source` task per source, return 202 with `task_ids`.
- New handler `services/tasks/handlers/cron_indeed_email_import.py` processes a SINGLE source (fetch → dedup → reject-filter → per-job create → commit). Lock window per task: <1 second instead of 4 minutes.
- Mirrors the existing `cron_crawl_source` / `email_import` async patterns already in `services/tasks/handlers/`.

**Tech Stack:** Python 3.12, Flask, Flask-SQLAlchemy, SQLite (WAL), existing `services/tasks/` queue + worker daemon, pytest.

---

## Context the executor needs first

**Root-cause evidence (from production VPS log, 2026-05-29 08:27–08:29):**
```
[08:27:35] UPDATE job_matches SET status='dismissed', feedback_reasons='["missing_skills"]' WHERE id=2225
sqlite3.OperationalError: database is locked
[08:29:01] WORKER TIMEOUT (pid:1233)  ← cron worker started 08:25
[08:29:02] Worker (pid:1233) was sent SIGKILL!
```
Pattern: every hour at xx:25 cron fires → sync endpoint loops over all email sources with ONE big transaction (commit only at end, [api/jobs_cron.py:354](../../api/jobs_cron.py)) → 240s gunicorn timeout → SIGKILL → other writers (e.g. user clicking "Verwerfen") get "database is locked" → 500.

**Why per-source tasks fix it:**
- One commit per source (B). Even if all 3 sources run back-to-back in the worker, write locks are sub-second, not 4 minutes.
- Runs in `task-worker-daemon`, not gunicorn (A). No more `WORKER TIMEOUT` / `SIGKILL`. No more stuck transactions.

**Existing reference patterns to mirror exactly:**
- Endpoint enqueue: [api/jobs_cron.py:131-141](../../api/jobs_cron.py) (`crawl-source`)
- Handler structure: [services/tasks/handlers/cron_crawl_source.py](../../services/tasks/handlers/cron_crawl_source.py)
- User-triggered analog (per-source): [services/tasks/handlers/email_import.py](../../services/tasks/handlers/email_import.py)
- Test sync-helper: `_run_enqueued_handler_sync` at [tests/api/test_indeed_email_import.py:14](../../tests/api/test_indeed_email_import.py)

**Current sync code to extract from:** [api/jobs_cron.py:216-362](../../api/jobs_cron.py) (`indeed_email_import_all`).

---

## File Structure

- **Create:** `services/tasks/handlers/cron_indeed_email_import.py` — new per-source handler
- **Modify:** `services/tasks/handlers/__init__.py` — register new handler import
- **Modify:** `api/jobs_cron.py:216-362` — replace sync body with enqueue-per-source loop
- **Modify:** `tests/api/test_indeed_email_import.py:628-768` — adapt 5 cron tests to 202 + sync handler run

---

### Task 1: New per-source handler

**Files:**
- Create: `services/tasks/handlers/cron_indeed_email_import.py`

- [ ] **Step 1: Write the failing test**

File: `tests/services/tasks/test_handler_cron_indeed_email_import.py` (new)

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für cron_indeed_email_import_source Handler."""
from unittest.mock import patch

import pytest

from database import db
from models import JobSource, User
from services.job_sources.base import FetchedJob


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def user_with_imap(app):
    from imap_service import IMAPCredentialManager
    u = User(email="u@example.com", password_hash="x", is_active=True,
            job_discovery_enabled=True)
    u.imap_host = "imap.example.com"
    u.imap_user = "u@example.com"
    u.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def indeed_source(user_with_imap):
    src = JobSource(user_id=user_with_imap.id, type="indeed_email",
                    name="Indeed", enabled=True, crawl_interval_min=60)
    src.config = {}
    db.session.add(src)
    db.session.commit()
    return src


def test_handler_imports_one_source_and_commits(app, indeed_source):
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    fetched = [FetchedJob(
        external_id="https://de.indeed.com/viewjob?jk=t1",
        title="Dev", url="https://de.indeed.com/viewjob?jk=t1",
        company="Acme", location="Berlin", description="...",
    )]
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["status"] == "ok"
    assert result["imported"] == 1
    assert result["mode"] == "imap"
    # last_crawled_at gesetzt → kommit erfolgt
    db.session.refresh(indeed_source)
    assert indeed_source.last_crawled_at is not None


def test_handler_returns_skipped_when_no_credentials(app):
    """User ohne IMAP/Apps-Script → skipped, KEIN raise."""
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    u = User(email="b@example.com", password_hash="x", is_active=True,
             job_discovery_enabled=True)
    db.session.add(u)
    db.session.commit()
    src = JobSource(user_id=u.id, type="indeed_email", name="x",
                    enabled=True, crawl_interval_min=60)
    src.config = {}
    db.session.add(src)
    db.session.commit()

    result = handle_cron_indeed_email_import_source(
        {"source_id": src.id}, progress_cb=None,
    )
    assert result["status"] == "skipped_no_credentials"


def test_handler_records_failure_and_auto_disables_after_threshold(app, indeed_source):
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    indeed_source.consecutive_failures = 4  # one more failure → 5 → disable
    db.session.commit()

    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("IMAP boom")):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["status"] == "error"
    assert "IMAP boom" in result["error"]
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 5
    assert indeed_source.enabled is False


def test_handler_blocked_company_creates_dismissed_match(app, indeed_source, user_with_imap):
    """Company in Reject-Window → JobMatch(status='dismissed',
    feedback_text='auto_blocked_by_rejection')."""
    from models import Application
    user_with_imap.job_reject_filter_enabled = True
    user_with_imap.job_reject_window_days = 180
    # Application mit company='Acme' und Rejection-Status
    app_rec = Application(
        user_id=user_with_imap.id, company="Acme", position="Old",
        status="abgelehnt", applied_date=__import__('datetime').date.today(),
    )
    db.session.add(app_rec)
    db.session.commit()

    fetched = [FetchedJob(
        external_id="https://de.indeed.com/viewjob?jk=blocked1",
        title="Dev2", url="https://de.indeed.com/viewjob?jk=blocked1",
        company="Acme", location="Berlin", description="...",
    )]
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["imported"] == 0
    assert result["blocked_auto"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/services/tasks/test_handler_cron_indeed_email_import.py -v
```
Expected: FAIL with `ModuleNotFoundError: services.tasks.handlers.cron_indeed_email_import`.

- [ ] **Step 3: Write the handler**

File: `services/tasks/handlers/cron_indeed_email_import.py` (new)

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/indeed-email-import-all (per-Source).

Logik aus api/jobs_cron.py::indeed_email_import_all extrahiert: jeder Source
läuft als eigener Task mit eigenem Commit. Verhindert die 4-Minuten-
Write-Lock-Phase, die im sync-Endpoint "database is locked"-500er bei
parallelen User-Writes (Verwerfen etc.) produziert hat.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

from database import db
from models import User, JobSource
from services.tasks.registry import register


_AUTO_DISABLE_THRESHOLD = 5


@register('cron_indeed_email_import_source')
def handle_cron_indeed_email_import_source(
    payload: dict, *, progress_cb: Optional[Callable] = None,
) -> dict:
    """Importiert Emails für GENAU EINE JobSource.

    Payload: {"source_id": int}

    Returns: per-source Run-Dict (gleiches Format wie früher `runs[i]` im
    sync-Endpoint), z.B.:
      {"source_id": 7, "status": "ok", "mode": "imap",
       "total_emails": 12, "duplicates": 2, "imported": 8, "blocked_auto": 2}

    Raises NICHT bei Fetch-Errors — gibt status=error zurück damit der Task
    als 'completed' (statt 'failed') geloggt wird; consecutive_failures +
    auto_disable werden im DB-Record festgehalten.
    """
    from services.job_sources import get_adapter
    from services.job_sources import dedup as _dedup
    from services.email_import_utils import (
        get_rejected_companies_lower,
        create_raw_job_and_match,
        fetch_apps_script_emails,
    )

    src = JobSource.query.get(payload['source_id'])
    if src is None:
        return {"source_id": payload['source_id'], "status": "skipped_no_source"}
    if not src.enabled:
        return {"source_id": src.id, "status": "skipped_disabled"}

    user = User.query.get(src.user_id) if src.user_id else None
    if user is None:
        return {"source_id": src.id, "status": "skipped_no_owner"}

    settings = {}
    if user.settings_json:
        try:
            settings = json.loads(user.settings_json) or {}
        except (TypeError, ValueError):
            settings = {}
    script_url = (settings.get('indeedScriptUrl') or '').strip()
    has_imap = bool(user.imap_password_encrypted)

    if progress_cb:
        progress_cb(5, 'fetching')

    try:
        adapter = get_adapter(src.type, src.config, user=user)
        if script_url:
            emails, _cache_hit = fetch_apps_script_emails(
                script_url, user_id=user.id, use_cache=False,  # Cron: immer frisch
            )
            fetched = adapter.parse_emails(emails)
            mode = 'apps_script_proxy'
        elif has_imap:
            fetched = adapter.fetch()
            mode = 'imap'
        else:
            return {"source_id": src.id, "status": "skipped_no_credentials"}
    except Exception as e:
        src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
        src.consecutive_failures = (src.consecutive_failures or 0) + 1
        if src.consecutive_failures >= _AUTO_DISABLE_THRESHOLD:
            src.enabled = False
        db.session.commit()
        return {
            "source_id": src.id,
            "status": "error",
            "error": src.last_error,
            "auto_disabled": not src.enabled,
        }

    src.consecutive_failures = 0
    src.last_error = None

    if progress_cb:
        progress_cb(60, f'parsed {len(fetched)} jobs')

    existing_urls = _dedup.get_existing_job_urls()
    fresh = _dedup.deduplicate(fetched, existing_urls)
    duplicates_count = len(fetched) - len(fresh)

    window_days = int(user.job_reject_window_days or 180)
    rejected_companies = (
        get_rejected_companies_lower(user.id, window_days)
        if user.job_reject_filter_enabled else set()
    )

    imported_count = 0
    blocked_auto_count = 0
    for fjob in fresh:
        company_lower = (fjob.company or '').strip().lower()
        is_blocked = bool(company_lower) and company_lower in rejected_companies
        payload_job = {
            'title': fjob.title, 'company': fjob.company,
            'location': fjob.location, 'url': fjob.url,
            'external_id': fjob.external_id, 'description': fjob.description,
            'raw': fjob.raw or {},
        }
        if is_blocked:
            create_raw_job_and_match(
                src, user.id, payload_job,
                match_status='dismissed',
                feedback_text='auto_blocked_by_rejection',
            )
            blocked_auto_count += 1
        else:
            create_raw_job_and_match(src, user.id, payload_job, match_status='new')
            imported_count += 1

    src.last_crawled_at = datetime.utcnow()
    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "source_id": src.id,
        "status": "ok",
        "mode": mode,
        "total_emails": len(fetched),
        "duplicates": duplicates_count,
        "imported": imported_count,
        "blocked_auto": blocked_auto_count,
    }
```

- [ ] **Step 4: Register handler import**

Modify `services/tasks/handlers/__init__.py`:

```python
# Existing imports
from services.tasks.handlers import email_import  # noqa: F401
# Add this line:
from services.tasks.handlers import cron_indeed_email_import  # noqa: F401
```

(Add it next to whichever line already exists for `email_import` / other cron_* handlers. Do NOT remove existing imports.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/services/tasks/test_handler_cron_indeed_email_import.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 6: Commit**

```bash
git add services/tasks/handlers/cron_indeed_email_import.py \
        services/tasks/handlers/__init__.py \
        tests/services/tasks/test_handler_cron_indeed_email_import.py
git commit -m "feat(tasks): cron_indeed_email_import_source handler (per-source, own commit)"
```

---

### Task 2: Endpoint becomes thin enqueue-per-source loop

**Files:**
- Modify: `api/jobs_cron.py:216-362` — replace `indeed_email_import_all` body

- [ ] **Step 1: Write the failing test (endpoint returns 202 + task_ids)**

Add to `tests/api/test_indeed_email_import.py` near line 768 (after the existing cron tests):

```python
def test_cron_endpoint_returns_202_and_enqueues_one_task_per_eligible_source(
    client, auth_header, monkeypatch,
):
    """Endpoint enqueueT EINE Task pro eligible Source und returnt 202+task_ids."""
    headers, user = auth_header
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from imap_service import IMAPCredentialManager
    user.imap_host = "imap.example.com"
    user.imap_user = "u@example.com"
    user.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.commit()

    for stype, name in [("indeed_email", "I"), ("linkedin_email", "L"),
                        ("xing_email", "X")]:
        s = JobSource(user_id=user.id, type=stype, name=name, enabled=True,
                      crawl_interval_min=60)
        s.config = {}
        db.session.add(s)
    db.session.commit()

    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    data = r.get_json()
    assert data["enqueued"] == 3
    assert len(data["task_ids"]) == 3


def test_cron_endpoint_skips_not_due_sources_at_enqueue_time(
    client, auth_header, indeed_source, monkeypatch,
):
    """Source mit last_crawled_at < interval → KEINE Task wird enqueueT."""
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    indeed_source.last_crawled_at = datetime.utcnow()
    indeed_source.crawl_interval_min = 60
    db.session.commit()

    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    data = r.get_json()
    assert data["enqueued"] == 0
    assert data["task_ids"] == []
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/api/test_indeed_email_import.py::test_cron_endpoint_returns_202_and_enqueues_one_task_per_eligible_source -v
```
Expected: FAIL — endpoint currently returns 200.

- [ ] **Step 3: Replace the endpoint body**

In `api/jobs_cron.py`, REPLACE lines 216–362 (the entire `indeed_email_import_all` function and its docstring) with:

```python
@jobs_cron_bp.post('/indeed-email-import-all')
@require_cron_token
def indeed_email_import_all():
    """Enqueued pro eligible Email-Source einen cron_indeed_email_import_source-Task.

    Hintergrund: bis 2026-05-29 war dieser Endpoint synchron und iterierte
    über ALLE Email-Sources in einer einzigen Write-Transaktion. Bei mehreren
    Usern dauerte das >180s → gunicorn WORKER TIMEOUT/SIGKILL und 4 Minuten
    "database is locked" für andere Writer (z.B. User-"Verwerfen").

    Jetzt: kurzer Read (Eligibility), ein Task pro Source, jeder Task
    committet eigenständig. Lock-Fenster pro Task ist sub-Sekunden.

    Returns: 202 + {"enqueued": N, "task_ids": [...]}.
    Die per-Source-Resultate stehen unter GET /api/tasks/<id> bereit.
    """
    from services.tasks.queue import enqueue_task

    now = datetime.utcnow()
    eligible = JobSource.query.filter(
        JobSource.type.in_(_email_source_types()),
        JobSource.enabled == True,  # noqa: E712
    ).all()

    task_ids: list[str] = []
    skipped_not_due = 0
    for src in eligible:
        if src.last_crawled_at is not None:
            next_due = src.last_crawled_at + timedelta(
                minutes=src.crawl_interval_min or 60,
            )
            if next_due > now:
                skipped_not_due += 1
                continue
        tid = enqueue_task(
            'cron_indeed_email_import_source',
            _system_user_id(),
            {'source_id': src.id},
        )
        task_ids.append(tid)

    return jsonify({
        'enqueued': len(task_ids),
        'task_ids': task_ids,
        'skipped_not_due': skipped_not_due,
        'total_eligible': len(eligible),
    }), 202
```

- [ ] **Step 4: Run new tests to confirm PASS**

```bash
pytest tests/api/test_indeed_email_import.py::test_cron_endpoint_returns_202_and_enqueues_one_task_per_eligible_source \
       tests/api/test_indeed_email_import.py::test_cron_endpoint_skips_not_due_sources_at_enqueue_time -v
```
Expected: 2/2 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_cron.py tests/api/test_indeed_email_import.py
git commit -m "refactor(jobs-cron): /indeed-email-import-all enqueues per-source tasks

Replaces the synchronous loop with one task per eligible source.
Fixes hourly 'database is locked' 500s caused by 4-minute write
transactions blocking other writers (e.g. user dismiss)."
```

---

### Task 3: Adapt 4 stale sync-shape tests

The old tests assert `status_code == 200` and a `runs`/`total_imported`/`total_sources` payload. After Task 2 the endpoint returns 202 + `task_ids`. Adapt them to enqueue+run-sync — same helper pattern as the rest of the file.

**Files:**
- Modify: `tests/api/test_indeed_email_import.py:628-768`

- [ ] **Step 1: Add a sync-runner helper for the new task type**

Add near the existing `_run_enqueued_handler_sync` at line 14:

```python
def _run_enqueued_cron_source_tasks_sync(client_response):
    """Führt alle gerade per /indeed-email-import-all enqueuten Tasks
    synchron aus. Returnt list[per-source result dict] in Enqueue-Reihenfolge.
    """
    import json
    from models import TaskQueue
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    task_ids = client_response.get_json()['task_ids']
    results = []
    for tid in task_ids:
        row = db.session.get(TaskQueue, tid)
        results.append(
            handle_cron_indeed_email_import_source(
                json.loads(row.payload), progress_cb=None,
            )
        )
    return results
```

- [ ] **Step 2: Update `test_cron_indeed_email_import_skips_source_without_credentials` (line ~628)**

Replace its body with:

```python
def test_cron_indeed_email_import_skips_source_without_credentials(
    client, auth_header, indeed_source, monkeypatch,
):
    """Source ohne IMAP/Apps-Script → handler returnt skipped_no_credentials."""
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    results = _run_enqueued_cron_source_tasks_sync(r)
    assert len(results) == 1
    assert results[0]["status"] == "skipped_no_credentials"
```

- [ ] **Step 3: Update `test_cron_indeed_email_import_runs_via_imap_when_credentials_present` (line ~641)**

Replace its assertion block with:

```python
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post("/api/jobs/indeed-email-import-all",
                        headers={"X-Cron-Token": "test-token"})
        assert r.status_code == 202
        results = _run_enqueued_cron_source_tasks_sync(r)
    assert any(rr.get("status") == "ok" and rr.get("mode") == "imap"
               and rr.get("imported") == 1
               for rr in results)
```

- [ ] **Step 4: Update `test_cron_skips_not_due_sources` (line ~672)**

Replace `data["processed_runs"] == 0` assertion with the new shape:

```python
    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    data = r.get_json()
    assert data["total_eligible"] == 1
    assert data["enqueued"] == 0
    assert data["skipped_not_due"] == 1
```

- [ ] **Step 5: Update `test_cron_endpoint_iterates_all_three_email_types` (line ~720)**

Replace its final block with:

```python
    resp = client.post("/api/jobs/indeed-email-import-all",
                       headers={"X-Cron-Token": "test-token"})
    assert resp.status_code == 202
    results = _run_enqueued_cron_source_tasks_sync(resp)
    assert len(results) == 3
    assert set(seen_types) == {"indeed", "linkedin", "xing"}
```

(`test_cron_requires_token` at line 693 stays as-is — it only checks 401/403, which is still correct.)

- [ ] **Step 6: Run the full cron-test slice**

```bash
pytest tests/api/test_indeed_email_import.py -v -k "cron"
```
Expected: all `cron_*` tests pass.

- [ ] **Step 7: Run the FULL test suite to catch unrelated regressions**

```bash
pytest tests/ -q
```
Expected: 0 failed. (If anything else asserts on the old 200/`runs` payload anywhere, fix it the same way.)

- [ ] **Step 8: Commit**

```bash
git add tests/api/test_indeed_email_import.py
git commit -m "test(jobs-cron): adapt indeed-email-import-all tests to 202+enqueue shape"
```

---

### Task 4: Local smoke test against test DB

The unit tests are unit tests — verify the actual Flask wiring once.

- [ ] **Step 1: Start the app in test mode**

```bash
ANTHROPIC_API_KEY=sk-test JOB_CRON_TOKEN=local-token \
  FLASK_ENV=testing python app.py &
APP_PID=$!
sleep 2
```

- [ ] **Step 2: Hit the cron endpoint**

```bash
curl -i -X POST -H "X-Cron-Token: local-token" \
  http://127.0.0.1:5000/api/jobs/indeed-email-import-all
```
Expected: `HTTP/1.1 202` with JSON `{"enqueued": ..., "task_ids": [...], ...}`. Response should come back in **<200ms** (vs. the old multi-second/minute response).

- [ ] **Step 3: Stop the app**

```bash
kill $APP_PID
```

- [ ] **Step 4: Verification statement for the PR/commit**

Use the standard format from AGENTS.md §4:
```
Verified: pytest tests/ (N passed), endpoint returns 202 in <200ms locally,
NOT deployed to IONOS yet — hand back to Claude Code for prod deploy.
```

---

### Task 5 (Claude Code — Care): Production deploy + monitoring

> **Do not execute as opencode.** Hand back to Claude Code per AGENTS.md §2 (production deploys to IONOS).

Steps Claude Code will run:

1. `ssh ionos-vps /usr/local/bin/bewerbungen-deploy.sh` (per `reference_vps_deploy_routine.md` — pull + pip + alembic + restart + smoke).
2. Tail logs through the next xx:25 cron firing and verify:
   - `/var/log/bewerbungen/cron.log` shows `[…] indeed-email-import-all: {"enqueued": N, "task_ids": […]}` instead of the old long sync output.
   - `/var/log/bewerbungen/error.log` does NOT show `WORKER TIMEOUT` at xx:29.
   - `/var/log/bewerbungen/task-worker.log` (or wherever the task-worker daemon logs) shows N `cron_indeed_email_import_source` tasks completing within seconds.
3. Manual check: try "Verwerfen" during xx:25–xx:29 window — must NOT fail anymore.
4. Watch the `bewerbungstracker.db-wal` file size — should NOT grow large during cron (was ~4MB before).

---

## Self-Review

**Spec coverage:**
- A (async via task-queue): Task 1 + Task 2 ✓
- B (per-source commits): Task 1's `db.session.commit()` per call ✓
- Test updates after refactor: Task 3 ✓
- Production deploy gated to Claude Code: Task 5 ✓

**Placeholder scan:** No TBD / "appropriate" / "similar to" / "add error handling" patterns. All file paths, line ranges, code blocks complete.

**Type consistency:** Handler name `cron_indeed_email_import_source` used consistently in registry decorator, import, test calls. Payload key `source_id` consistent. Return-dict keys (`status`, `imported`, `blocked_auto`, `mode`) match between handler and tests.

**Frontend impact:** None. The frontend never called `/indeed-email-import-all` directly — only cron does. The user-facing `Verwerfen` path is the *beneficiary*, not a caller of the changed endpoint. No frontend changes needed.

---

## Out of scope (explicit)

- Generalising other cron stages — `crawl-source`, `prefilter`, `claude-match`, `notify`, `cleanup`, `url-health-check` already enqueue tasks (per [api/jobs_cron.py:131-209](../../api/jobs_cron.py)). They are not touched.
- IMAP credential handling, encryption, OAuth tokens. The adapter `.fetch()` call is moved verbatim from sync endpoint to async handler.
- DB schema migrations. No model changes.
- Removing the WAL/busy_timeout safety net in `database.py` — those stay as defence in depth.
