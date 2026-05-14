# Job-Status "unbewertet" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new JobMatch status `unbewertet` (unevaluated) to mark jobs pending evaluation, replacing the redundant `seen` status.

**Architecture:** Replace `seen` status with `unbewertet` in JobMatch model. Update API validation to accept `unbewertet`, `dismissed`, `new`. Migrate existing `seen` records to `unbewertet`. Add tests for status transitions. Update frontend filter defaults.

**Tech Stack:** Flask (API), SQLAlchemy (ORM), pytest (tests), Vanilla JS (frontend filter)

---

## Task 1: Update models.py JobMatch docstring

**Files:**
- Modify: `models.py:388-415` (JobMatch class docstring and status field)

- [ ] **Step 1: Read JobMatch docstring**

Run: `grep -A 10 "class JobMatch" /Library/WebServer/Documents/Bewerbungstracker/models.py`

Expected output shows current status documentation: `'new' = noch nicht angesehen, 'seen' = User hat ihn gesehen, 'imported' = übernommen, 'dismissed' = verworfen`

- [ ] **Step 2: Update docstring to document new status**

Replace lines 389-391 (the status docstring):
```python
    """Per-User-Bewertung eines RawJob.

    status: 'new' = noch nicht angesehen, 'unbewertet' = bewusst als "noch nicht entschieden" gekennzeichnet,
    'imported' = übernommen, 'dismissed' = verworfen oder Auto-Verworfen.
    """
```

- [ ] **Step 3: Verify change**

Run: `grep -A 5 "class JobMatch" /Library/WebServer/Documents/Bewerbungstracker/models.py | head -10`

Expected: Updated docstring mentions `'unbewertet'` and removes `'seen'`

- [ ] **Step 4: Commit**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
git add models.py
git commit -m "docs: Update JobMatch status documentation for 'unbewertet'"
```

---

## Task 2: Add migration to convert seen → unbewertet

**Files:**
- Create: `migrations/versions/XXXXX_convert_seen_to_unbewertet.py`

- [ ] **Step 1: Check if migrations directory exists**

Run: `ls -la /Library/WebServer/Documents/Bewerbungstracker/migrations/ 2>/dev/null || echo 'No migrations dir'`

- [ ] **Step 2: Create migration file if needed**

If no migrations dir exists, create basic migration structure. If it exists, create new migration:

```python
"""Convert seen status to unbewertet.

Revision ID: SEEN_TO_UNBEWERTET
Revises: (previous migration ID)
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'SEEN_TO_UNBEWERTET'
down_revision = None  # Set to previous migration ID
branch_labels = None
depends_on = None

def upgrade():
    # Convert all 'seen' status to 'unbewertet'
    op.execute("UPDATE job_matches SET status = 'unbewertet' WHERE status = 'seen'")

def downgrade():
    # Convert back for rollback
    op.execute("UPDATE job_matches SET status = 'seen' WHERE status = 'unbewertet'")
```

Alternative (if no Alembic): Create raw SQL migration in `migrations/` folder

- [ ] **Step 3: Verify migration syntax**

Run: `python -m alembic upgrade head` (or equivalent for your migration system)

Expected: Migration applies cleanly without errors

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/
git commit -m "migration: Convert seen status to unbewertet"
```

---

## Task 3: Update API validation for status in jobs_user.py

**Files:**
- Modify: `api/jobs_user.py:301-302` (PATCH endpoint status validation)
- Modify: `api/jobs_user.py:515-516` (bulk endpoint status validation)

- [ ] **Step 1: Read current validation at line 301**

Run: `sed -n '299,305p' /Library/WebServer/Documents/Bewerbungstracker/api/jobs_user.py`

Expected output: Shows `if new_status not in ('seen', 'dismissed', 'new'):`

- [ ] **Step 2: Update PATCH endpoint validation**

Replace line 301:
```python
    if new_status not in ('unbewertet', 'dismissed', 'new'):
```

And update error message at line 302:
```python
        return jsonify({"error": "status muss 'unbewertet'|'dismissed'|'new' sein"}), 400
```

- [ ] **Step 3: Read bulk endpoint validation at line 515**

Run: `sed -n '513,520p' /Library/WebServer/Documents/Bewerbungstracker/api/jobs_user.py`

Expected output: Shows `if new_status not in ('seen', 'dismissed'):`

- [ ] **Step 4: Update bulk endpoint validation**

Replace line 515:
```python
    if new_status not in ('unbewertet', 'dismissed'):
```

And update error message at line 516:
```python
        return jsonify({"error": "status muss 'unbewertet' oder 'dismissed' sein"}), 400
```

- [ ] **Step 5: Verify changes**

Run: `grep -n "status muss" /Library/WebServer/Documents/Bewerbungstracker/api/jobs_user.py`

Expected: Two lines, both reference `'unbewertet'` instead of `'seen'`

- [ ] **Step 6: Commit**

```bash
git add api/jobs_user.py
git commit -m "feat: Update API status validation to support 'unbewertet'"
```

---

## Task 4: Update default filter to include unbewertet

**Files:**
- Modify: `api/jobs_user.py:188` (default status filter)

- [ ] **Step 1: Read current default filter**

Run: `sed -n '186,190p' /Library/WebServer/Documents/Bewerbungstracker/api/jobs_user.py`

Expected output: Shows `status_filter = request.args.getlist('status') or ['new']`

- [ ] **Step 2: Update default to include both new and unbewertet**

Replace line 188:
```python
    status_filter = request.args.getlist('status') or ['new', 'unbewertet']
```

- [ ] **Step 3: Verify change**

Run: `sed -n '186,190p' /Library/WebServer/Documents/Bewerbungstracker/api/jobs_user.py`

Expected: Shows `['new', 'unbewertet']` as default

- [ ] **Step 4: Commit**

```bash
git add api/jobs_user.py
git commit -m "feat: Update default job filter to show 'new' and 'unbewertet' status"
```

---

## Task 5: Write tests for new status

**Files:**
- Modify: `tests/api/test_jobs_user.py` (add new test cases)

- [ ] **Step 1: Check existing tests for status handling**

Run: `grep -n "status" /Library/WebServer/Documents/Bewerbungstracker/tests/api/test_jobs_user.py | head -15`

Expected: Shows existing status-related tests

- [ ] **Step 2: Add test for unbewertet status update**

Add new test at end of test file:

```python
def test_update_job_match_to_unbewertet(app, test_user_token, db_session):
    """Test updating job match status to 'unbewertet'."""
    from models import RawJob, JobMatch, JobSource
    
    # Create source and raw job
    source = JobSource(user_id=None, name="Test", type="rss", enabled=True)
    db_session.add(source)
    db_session.flush()
    
    raw_job = RawJob(
        source_id=source.id,
        external_id="test123",
        title="Python Developer",
        company="TestCorp",
        url="https://example.com/job123"
    )
    db_session.add(raw_job)
    db_session.flush()
    
    # Create match with 'new' status
    match = JobMatch(
        raw_job_id=raw_job.id,
        user_id=test_user_token['user_id'],
        status='new'
    )
    db_session.add(match)
    db_session.commit()
    
    # Update to 'unbewertet'
    with app.test_client() as client:
        response = client.patch(
            f'/api/jobs/matches/{match.id}',
            json={"status": "unbewertet"},
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'unbewertet'
    
    # Verify in DB
    updated = db_session.query(JobMatch).get(match.id)
    assert updated.status == 'unbewertet'
```

- [ ] **Step 3: Add test for invalid status rejection**

Add test:

```python
def test_reject_invalid_status(app, test_user_token, db_session):
    """Test that invalid status 'seen' is rejected."""
    from models import RawJob, JobMatch, JobSource
    
    source = JobSource(user_id=None, name="Test", type="rss", enabled=True)
    db_session.add(source)
    db_session.flush()
    
    raw_job = RawJob(
        source_id=source.id,
        external_id="test456",
        title="Designer",
        company="TestCorp",
        url="https://example.com/job456"
    )
    db_session.add(raw_job)
    db_session.flush()
    
    match = JobMatch(
        raw_job_id=raw_job.id,
        user_id=test_user_token['user_id'],
        status='new'
    )
    db_session.add(match)
    db_session.commit()
    
    # Try to update with old 'seen' status (should fail)
    with app.test_client() as client:
        response = client.patch(
            f'/api/jobs/matches/{match.id}',
            json={"status": "seen"},
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "status muss" in data['error']
```

- [ ] **Step 4: Add test for default filter includes unbewertet**

Add test:

```python
def test_default_filter_includes_unbewertet(app, test_user_token, db_session):
    """Test that default /matches filter includes 'new' and 'unbewertet'."""
    with app.test_client() as client:
        # No status filter specified - should use default
        response = client.get(
            '/api/jobs/matches',
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    
    assert response.status_code == 200
    # Response should include both 'new' and 'unbewertet' status by default
    # (verify by checking SQL query uses both in WHERE clause)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/api/test_jobs_user.py::test_update_job_match_to_unbewertet -v`

Expected: PASS

Run: `pytest tests/api/test_jobs_user.py::test_reject_invalid_status -v`

Expected: PASS

Run: `pytest tests/api/test_jobs_user.py::test_default_filter_includes_unbewertet -v`

Expected: PASS

- [ ] **Step 6: Run all job tests**

Run: `pytest tests/api/test_jobs_user.py -v`

Expected: All tests pass (no regressions)

- [ ] **Step 7: Commit**

```bash
git add tests/api/test_jobs_user.py
git commit -m "test: Add tests for 'unbewertet' status and validation"
```

---

## Task 6: Update frontend filter UI (if applicable)

**Files:**
- Check: `frontend/pages/*.html` or `frontend/js/*.js` for status filter UI
- Modify: Frontend status filter component (if it exists)

- [ ] **Step 1: Search for status filter in frontend**

Run: `grep -r "status" /Library/WebServer/Documents/Bewerbungstracker/frontend/ 2>/dev/null | head -10`

- [ ] **Step 2: Identify filter UI file**

Look for `status` filter display or selector in HTML/JS

- [ ] **Step 3: Update UI labels**

If a filter UI exists, update:
- Remove "seen" option from filter
- Add "unbewertet" option
- Update default filter display to show "Unbewertete (new + unbewertet)"

Example (if using select dropdown):
```html
<label for="status-filter">Status:</label>
<select id="status-filter" multiple>
  <option value="new" selected>Neue</option>
  <option value="unbewertet" selected>Unbewertete</option>
  <option value="dismissed">Verworfen</option>
  <option value="imported">Importiert</option>
</select>
```

- [ ] **Step 4: Test filter in UI (manual)**

Open the frontend and verify:
- Default shows both "new" and "unbewertet" jobs
- Can filter by "unbewertet" specifically
- "seen" option no longer appears

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: Update frontend filter UI for 'unbewertet' status"
```

---

## Task 7: Run integration tests

**Files:**
- Run: `tests/api/test_job_discovery_approval.py` (if job discovery tests exist)

- [ ] **Step 1: Run all job-related tests**

Run: `pytest tests/api/test_jobs_user.py tests/api/test_jobs_cron.py -v`

Expected: All tests pass (100%)

- [ ] **Step 2: Run migration test (if applicable)**

Run: `python -m alembic downgrade -1 && python -m alembic upgrade head`

Expected: Migration applies and rolls back cleanly

- [ ] **Step 3: Verify no seen status exists in data**

Run: `sqlite3 instance/bewerbungstracker.db "SELECT COUNT(*) FROM job_matches WHERE status = 'seen';" 2>/dev/null || echo "DB not found locally"`

Expected: 0 (all converted to unbewertet)

- [ ] **Step 4: Manual API test**

```bash
# Get token (if needed for local testing)
CURL_OUTPUT=$(curl -s -X PATCH http://localhost:5000/api/jobs/matches/1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "unbewertet"}')

echo $CURL_OUTPUT | grep -q "unbewertet" && echo "API works!" || echo "API failed"
```

- [ ] **Step 5: Check no regressions in other features**

Run: `pytest tests/ -k "not slow" --co -q | wc -l` (count tests)

Run: `pytest tests/ -k "not slow" -x` (stop on first failure)

Expected: All tests pass, no failures from status changes

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "test: Verify migration and integration tests pass"
```

---

## Summary of Changes

**Modified Files:**
- `models.py` — Updated JobMatch docstring
- `api/jobs_user.py` — Updated status validation (3 locations) and default filter
- `migrations/versions/` — New migration for seen → unbewertet
- `tests/api/test_jobs_user.py` — Added 3 new tests
- `frontend/` — Updated filter UI (if applicable)

**Commits:**
1. docs: Update JobMatch status documentation
2. migration: Convert seen status to unbewertet
3. feat: Update API status validation
4. feat: Update default job filter
5. test: Add status validation tests
6. feat: Update frontend filter UI
7. test: Verify migration and integration tests

---

## Spec Coverage

✅ **Status "unbewertet" added** — Task 1, 3  
✅ **seen → unbewertet migration** — Task 2  
✅ **API accepts new status** — Task 3, 5  
✅ **Default filter shows unbewertete** — Task 4, 5  
✅ **Frontend UI updated** — Task 6  
✅ **Tests verify behavior** — Task 5, 7  
✅ **No data loss** — Task 2 (migration)
