# Claude On-Demand + Bulk-Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude API on-demand statt automatisch (4 Wege: 1×/Tag-Cron für Top-Treffer, manuell-single, manuell-bulk, beim Import) und Bulk-Aktionen für Match-Verwaltung im UI.

**Architecture:** Backend extrahiert geteilte Helper-Funktion `_run_claude_match_for(client, user, match)` aus dem bestehenden Cron-Endpoint. Vier neue/geänderte Endpoints rufen diesen Helper. Cron läuft nur 1×/Tag mit höherem Threshold. Frontend bekommt Checkbox + Floating Action Bar + neuen "Bewerten lassen"-Button.

**Tech Stack:** Python 3.14, Flask, SQLAlchemy, Anthropic SDK, vanilla JS frontend.

---

## File Structure

**New Files:**
- (none — alle Endpoints + Helper landen in bestehenden Files)

**Modified Files:**
- `api/jobs_cron.py` — Extract `_run_claude_match_for()`, add `AUTO_CLAUDE_THRESHOLD=50`, change Filter in `claude_match()`
- `api/jobs_user.py` — Neue Endpoints: `/matches/<id>/score`, `/matches/score-bulk`, `/matches/bulk`. Geänderter Endpoint: `/matches/<id>/import` (ruft Claude wenn match_score=None)
- `tests/api/test_jobs_user.py` — Neue Tests für 4 Endpoints + import-Verhalten
- `tests/api/test_jobs_cron.py` — Test für `AUTO_CLAUDE_THRESHOLD`
- `index.html` — Card-Anzeige (Checkbox, Vor-Filter-Badge, "Bewerten lassen"-Button), Floating Action Bar, Bulk-State + Handlers
- `/etc/cron.d/job-discovery` (auf VPS) — Cron-Frequenz von `0,30 * * * *` auf `0 8 * * *`

---

## Task 1: Backend Helper extrahieren

Refactor: Bestehende Inline-Logik aus `claude_match()` cron-endpoint in eine geteilte Funktion `_run_claude_match_for(client, user, match) -> bool` extrahieren. Returns True wenn bewertet, False wenn skip (Budget oder schon bewertet).

**Files:**
- Modify: `api/jobs_cron.py` — Lines 246-310 (claude_match) refactor
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Read current claude_match implementation**

```bash
sed -n '246,310p' api/jobs_cron.py
```

Du wirst sehen: User-Loop, Budget-Check, Candidates-Query, Inner-Loop mit Claude-Call, ApiCall-Logging, commit. Wir extrahieren den **Inner-Loop-Body** in eine Helper-Funktion.

- [ ] **Step 2: Write failing test for `_run_claude_match_for` (idempotency)**

Datei: `tests/api/test_jobs_cron.py` — am Ende anhängen:

```python
def test_run_claude_match_for_idempotent(app, user_factory):
    """Wenn match_score schon gesetzt ist, returnt der Helper sofort False ohne Claude-Call."""
    from api.jobs_cron import _run_claude_match_for
    from unittest.mock import MagicMock

    user = user_factory()
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=80, match_reasoning="bereits bewertet")
    db.session.add(m); db.session.commit()

    fake_client = MagicMock()  # darf nicht aufgerufen werden
    result = _run_claude_match_for(fake_client, user, m)

    assert result is False
    assert m.match_score == 80  # unverändert
    fake_client.assert_not_called()


def test_run_claude_match_for_returns_false_when_budget_exhausted(app, user_factory, monkeypatch):
    """Wenn Tagesbudget erschöpft: Helper returnt False, kein Claude-Call."""
    from api.jobs_cron import _run_claude_match_for
    from unittest.mock import MagicMock

    user = user_factory()
    user.job_daily_budget_cents = 0  # 0 Cent = sofort erschöpft
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    # _user_today_cost_cents > 0 simulieren via ApiCall
    db.session.add(ApiCall(user_id=user.id, endpoint='/test', model='x',
                           tokens_in=0, tokens_out=0, cost=0.50, key_owner='server'))
    db.session.commit()

    fake_client = MagicMock()
    result = _run_claude_match_for(fake_client, user, m)

    assert result is False
    assert m.match_score is None
```

Falls `ApiCall` noch nicht oben importiert ist:
```python
from models import ApiCall
```
am Top der Test-Datei hinzufügen (falls nicht schon da).

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/api/test_jobs_cron.py::test_run_claude_match_for_idempotent tests/api/test_jobs_cron.py::test_run_claude_match_for_returns_false_when_budget_exhausted -v
```

Expected: FAIL with `ImportError: cannot import name '_run_claude_match_for'`

- [ ] **Step 4: Implement `_run_claude_match_for` in api/jobs_cron.py**

In `api/jobs_cron.py` direkt VOR der Funktion `claude_match()` einfügen:

```python
def _run_claude_match_for(client, user: User, match: JobMatch) -> bool:
    """Führt Claude-Match für einen einzelnen JobMatch aus.

    Returns:
        True wenn erfolgreich bewertet (DB-Update gemacht).
        False wenn geskippt (schon bewertet, Budget erschöpft, oder Claude-Error).

    Idempotent: Wenn match.match_score schon gesetzt ist, returnt sofort False.
    Budget-Check: Wenn _user_today_cost_cents(user.id) >= user.job_daily_budget_cents,
    returnt False.
    """
    # Idempotenz
    if match.match_score is not None:
        return False

    # Budget-Check
    if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return False

    raw = RawJob.query.get(match.raw_job_id)
    if raw is None:
        return False

    cv_summary = _build_cv_summary(user.cv_data_json)
    try:
        result = match_job_with_claude(
            client=client, model=DEFAULT_MODEL, cv_summary=cv_summary,
            job={"title": raw.title, "description": raw.description, "location": raw.location},
        )
    except Exception:
        return False

    match.match_score = result.score
    match.match_reasoning = result.reasoning
    match.missing_skills = result.missing_skills
    raw.crawl_status = 'matched'

    cost_cents = _estimate_cost_cents(result.tokens_in, result.tokens_out)
    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/claude-match',
        model=DEFAULT_MODEL, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_cents / 100.0,
        key_owner='server',
    ))
    return True
```

- [ ] **Step 5: Run helper-tests — verify they pass**

```bash
pytest tests/api/test_jobs_cron.py::test_run_claude_match_for_idempotent tests/api/test_jobs_cron.py::test_run_claude_match_for_returns_false_when_budget_exhausted -v
```

Expected: PASS (2 tests)

- [ ] **Step 6: Refactor `claude_match()` to use the helper**

In `api/jobs_cron.py` die Funktion `claude_match()` (Zeilen ~246-310) ersetzen. **Den Inner-Loop-Body durch einen Helper-Call ersetzen, NICHT die ganze Funktion umschreiben.** Nach dem Refactor sieht der Inner-Loop so aus:

```python
        cv_summary = _build_cv_summary(user.cv_data_json)  # noch unbenutzt — kann weg
        for match in candidates:
            if time.time() - started > HARD_TIME_LIMIT_SEC:
                break
            if _run_claude_match_for(client, user, match):
                matched += 1
            else:
                # Wenn Budget gerade erschöpft wurde mid-loop, weiter zum nächsten User
                if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
                    break

        db.session.commit()
```

Du kannst die `cv_summary`-Zeile entfernen, weil der Helper sie selbst lädt.

- [ ] **Step 7: Run all jobs_cron tests — verify no regression**

```bash
pytest tests/api/test_jobs_cron.py -v
```

Expected: PASS (alle bestehenden + 2 neue Tests)

- [ ] **Step 8: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "refactor: extract _run_claude_match_for helper from claude_match cron

Idempotent + budget-aware. Will be reused by 4 new endpoints in next tasks."
```

---

## Task 2: Auto-Threshold AUTO_CLAUDE_THRESHOLD = 50

Den Filter in `claude_match()` von `PREFILTER_DISMISS_THRESHOLD` (15) auf `AUTO_CLAUDE_THRESHOLD` (50) umstellen.

**Files:**
- Modify: `api/jobs_cron.py` (Konstante hinzufügen, Filter ändern)
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Write failing test**

Datei: `tests/api/test_jobs_cron.py` — am Ende anhängen:

```python
def test_auto_cron_skips_jobs_below_auto_threshold(app, user_factory, monkeypatch):
    """Auto-Cron bewertet nur prefilter_score >= AUTO_CLAUDE_THRESHOLD (50).

    Job mit prefilter_score=40 wird übersprungen, mit 60 wird bewertet.
    """
    from unittest.mock import patch, MagicMock
    from api.jobs_cron import AUTO_CLAUDE_THRESHOLD

    assert AUTO_CLAUDE_THRESHOLD == 50

    user = user_factory(cv_data_json='{"cv": {"summary": "Python Dev", "skills": ["python"]}}')
    user.job_discovery_enabled = True
    user.job_claude_budget_per_tick = 5
    user.job_daily_budget_cents = 1000

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()

    raw_low = RawJob(source_id=src.id, external_id="low", title="Low", url="https://j/low")
    raw_high = RawJob(source_id=src.id, external_id="high", title="High", url="https://j/high")
    db.session.add_all([raw_low, raw_high]); db.session.flush()

    m_low = JobMatch(raw_job_id=raw_low.id, user_id=user.id,
                     status='new', prefilter_score=40, match_score=None)
    m_high = JobMatch(raw_job_id=raw_high.id, user_id=user.id,
                      status='new', prefilter_score=60, match_score=None)
    db.session.add_all([m_low, m_high]); db.session.commit()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    fake_result = MagicMock(score=85, reasoning="ok",
                            missing_skills=[], tokens_in=10, tokens_out=10)
    with patch("api.jobs_cron._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        client_t = app.test_client()
        r = client_t.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})
        assert r.status_code == 200

    db.session.refresh(m_low)
    db.session.refresh(m_high)
    assert m_low.match_score is None    # geskippt (prefilter < 50)
    assert m_high.match_score == 85     # bewertet (prefilter >= 50)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/api/test_jobs_cron.py::test_auto_cron_skips_jobs_below_auto_threshold -v
```

Expected: FAIL with `ImportError: cannot import name 'AUTO_CLAUDE_THRESHOLD'` (oder, wenn Konstante schon `15` ist: assertion error im Threshold-Wert)

- [ ] **Step 3: Add constant + change filter**

In `api/jobs_cron.py` direkt nach `PREFILTER_DISMISS_THRESHOLD = 15` (Zeile ~30) einfügen:

```python
# Auto-Cron bewertet nur prefilter_score >= AUTO_CLAUDE_THRESHOLD.
# User-getriggerte Bewertungen (single, bulk, import) ignorieren diesen Threshold.
AUTO_CLAUDE_THRESHOLD = 50
```

In `claude_match()`-Funktion: ALLE Vorkommen von `PREFILTER_DISMISS_THRESHOLD` durch `AUTO_CLAUDE_THRESHOLD` ersetzen — das sind 2 Stellen (im Outer- und Inner-Filter, bei Zeilen ~260 und ~275).

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/api/test_jobs_cron.py::test_auto_cron_skips_jobs_below_auto_threshold -v
```

Expected: PASS

- [ ] **Step 5: Run all cron tests — no regressions**

```bash
pytest tests/api/test_jobs_cron.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat: AUTO_CLAUDE_THRESHOLD=50 für Auto-Cron (sparsamer Claude-Verbrauch)"
```

---

## Task 3: Single-Score-Endpoint POST /api/jobs/matches/<id>/score

User-facing Endpoint: triggert Claude-Match für einen einzelnen Match. Budget-aware.

**Files:**
- Modify: `api/jobs_user.py` (neuer Endpoint)
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Write failing tests**

Datei: `tests/api/test_jobs_user.py` — am Ende anhängen:

```python
def test_score_single_returns_match_data(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: ruft Claude, schreibt Score, returnt Daten."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Python Dev", "skills": ["python"]}}'
    user.job_daily_budget_cents = 1000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1",
                 description="Wir suchen Python")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 prefilter_score=42, match_score=None)
    db.session.add(m); db.session.commit()

    fake_result = MagicMock(score=80, reasoning="passt gut",
                            missing_skills=["docker"], tokens_in=20, tokens_out=20)
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body["match_score"] == 80
    assert body["match_reasoning"] == "passt gut"
    assert body["missing_skills"] == ["docker"]


def test_score_single_returns_402_when_budget_exhausted(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: Tagesbudget aufgebraucht → 402 Payment Required."""
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 50
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 prefilter_score=42, match_score=None)
    db.session.add(m)
    # Budget durch existing ApiCall erschöpfen (cost=1.00 EUR > 0.50 budget)
    db.session.add(ApiCall(user_id=user.id, endpoint='/test', model='x',
                           tokens_in=0, tokens_out=0, cost=1.00, key_owner='server'))
    db.session.commit()

    from unittest.mock import patch, MagicMock
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()):
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)

    assert r.status_code == 402
    assert "budget" in r.get_json()["error"].lower()


def test_score_single_returns_403_when_not_owner(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: anderer User → 403."""
    headers, user = auth_header
    other = user_factory(email="other@example.com")
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=other.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)
    assert r.status_code == 403


def test_score_single_returns_existing_score_when_already_matched(client, app, user_factory, auth_header):
    """Wenn match_score schon gesetzt: 200 mit Daten, kein Claude-Call."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=88, match_reasoning="alt", missing_skills=[])
    db.session.add(m); db.session.commit()

    fake_client = MagicMock()
    with patch("api.jobs_user._get_anthropic_client", return_value=fake_client), \
         patch("api.jobs_cron.match_job_with_claude") as mock_claude:
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)
        mock_claude.assert_not_called()

    assert r.status_code == 200
    assert r.get_json()["match_score"] == 88
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/api/test_jobs_user.py::test_score_single_returns_match_data tests/api/test_jobs_user.py::test_score_single_returns_402_when_budget_exhausted tests/api/test_jobs_user.py::test_score_single_returns_403_when_not_owner tests/api/test_jobs_user.py::test_score_single_returns_existing_score_when_already_matched -v
```

Expected: FAIL — Endpoint existiert noch nicht (404).

- [ ] **Step 3: Implement endpoint**

In `api/jobs_user.py` am Top folgende Imports hinzufügen (falls noch nicht vorhanden):

```python
from api.jobs_cron import _run_claude_match_for, _user_today_cost_cents
```

Dazu lokal in `api/jobs_user.py` eine Helper-Funktion für den Anthropic-Client (DRY mit jobs_cron):

```python
def _get_anthropic_client():
    """Phase A: einziger Server-Key. Phase B ersetzt dies durch Factory."""
    import os
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=api_key)
```

Dann den Endpoint hinzufügen (nach `import_match`):

```python
@jobs_user_bp.post('/matches/<int:match_id>/score')
@token_required
def score_match(user, match_id: int):
    """Triggert Claude-Match für einen einzelnen Match. Budget-aware."""
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403

    # Schon bewertet → existing data zurückgeben (kein Claude-Call)
    if m.match_score is not None:
        return jsonify({
            "match_score": m.match_score,
            "match_reasoning": m.match_reasoning,
            "missing_skills": m.missing_skills,
        }), 200

    # Budget-Check VOR Anthropic-Client-Init (spart unnötigen API-Key-Check)
    if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return jsonify({"error": "Tagesbudget für Claude-Bewertungen erschöpft"}), 402

    client = _get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY nicht gesetzt"}), 503

    success = _run_claude_match_for(client, user, m)
    if not success:
        # Helper hat False returnt — entweder Budget gerade erschöpft, oder Claude-Error
        db.session.rollback()
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            return jsonify({"error": "Tagesbudget für Claude-Bewertungen erschöpft"}), 402
        return jsonify({"error": "Bewertung fehlgeschlagen"}), 500

    db.session.commit()
    return jsonify({
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
    }), 200
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/api/test_jobs_user.py -k "score_single" -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat: POST /api/jobs/matches/<id>/score (on-demand single Claude-Match)"
```

---

## Task 4: Bulk-Score-Endpoint POST /api/jobs/matches/score-bulk

User-facing Endpoint: triggert Claude für mehrere Matches. Stoppt bei Budget-Erschöpfung.

**Files:**
- Modify: `api/jobs_user.py`
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Write failing tests**

Am Ende von `tests/api/test_jobs_user.py`:

```python
def test_score_bulk_evaluates_all_when_budget_sufficient(client, app, user_factory, auth_header):
    """3 Matches, alle bewerten → scored hat 3, skipped_budget leer."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 10000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raws = []
    for i in range(3):
        r = RawJob(source_id=src.id, external_id=f"r{i}", title=f"Job {i}",
                   url=f"https://j/{i}")
        db.session.add(r); raws.append(r)
    db.session.flush()
    matches = []
    for r in raws:
        m = JobMatch(raw_job_id=r.id, user_id=user.id, status='new', match_score=None)
        db.session.add(m); matches.append(m)
    db.session.commit()
    ids = [m.id for m in matches]

    fake_result = MagicMock(score=70, reasoning="ok", missing_skills=[],
                            tokens_in=10, tokens_out=10)
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post("/api/jobs/matches/score-bulk",
                        json={"match_ids": ids}, headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert len(body["scored"]) == 3
    assert body["skipped_budget"] == []
    assert body["errors"] == []


def test_score_bulk_stops_at_budget(client, app, user_factory, auth_header):
    """Wenn Budget mid-loop aufgebraucht: scored = N, skipped_budget = Rest."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 50  # nur ~1 Job (jeder Call kostet ~3 cent)
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    matches = []
    for i in range(3):
        r = RawJob(source_id=src.id, external_id=f"r{i}", title=f"Job {i}",
                   url=f"https://j/{i}")
        db.session.add(r); db.session.flush()
        m = JobMatch(raw_job_id=r.id, user_id=user.id, status='new', match_score=None)
        db.session.add(m); matches.append(m)
    db.session.commit()
    ids = [m.id for m in matches]

    # Erste Call füllt Budget, zweiter wird geskippt durch _run_claude_match_for's Budget-Check
    fake_result = MagicMock(score=70, reasoning="ok", missing_skills=[],
                            tokens_in=10000, tokens_out=10000)  # high tokens → high cost
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post("/api/jobs/matches/score-bulk",
                        json={"match_ids": ids}, headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    # Mindestens einer wird gescored, der Rest skipped (high tokens → big cost → quick budget exhaustion)
    assert len(body["scored"]) >= 1
    assert len(body["skipped_budget"]) >= 1
    assert len(body["scored"]) + len(body["skipped_budget"]) == 3


def test_score_bulk_handles_mixed_ownership(client, app, user_factory, auth_header):
    """Match-IDs von anderem User landen in 'forbidden', kein 403 für ganzen Request."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    other = user_factory(email="other@example.com")
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Job", url="https://j/1")
    db.session.add(raw); db.session.flush()

    m_mine = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    m_other = JobMatch(raw_job_id=raw.id, user_id=other.id, status='new', match_score=None)
    db.session.add_all([m_mine, m_other]); db.session.commit()

    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 1000
    db.session.commit()

    fake_result = MagicMock(score=70, reasoning="ok", missing_skills=[],
                            tokens_in=10, tokens_out=10)
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post("/api/jobs/matches/score-bulk",
                        json={"match_ids": [m_mine.id, m_other.id]}, headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert len(body["scored"]) == 1
    assert m_other.id in body["forbidden"]


def test_score_bulk_validates_input(client, app, auth_header):
    """match_ids fehlt oder leer → 400."""
    headers, _ = auth_header
    r = client.post("/api/jobs/matches/score-bulk", json={}, headers=headers)
    assert r.status_code == 400
    r = client.post("/api/jobs/matches/score-bulk",
                    json={"match_ids": []}, headers=headers)
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/api/test_jobs_user.py -k "score_bulk" -v
```

Expected: FAIL — endpoint nicht da (404).

- [ ] **Step 3: Implement endpoint**

In `api/jobs_user.py` nach `score_match`:

```python
@jobs_user_bp.post('/matches/score-bulk')
@token_required
def score_match_bulk(user):
    """Bulk-Claude-Match. Stoppt bei Budget-Erschöpfung, returnt Status pro Match."""
    data = request.get_json() or {}
    ids = data.get("match_ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "match_ids muss nicht-leere Liste sein"}), 400

    matches = JobMatch.query.filter(JobMatch.id.in_(ids)).all()
    found_ids = {m.id for m in matches}
    not_found = [i for i in ids if i not in found_ids]

    forbidden = [m.id for m in matches if m.user_id != user.id]
    own = [m for m in matches if m.user_id == user.id]

    client = _get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY nicht gesetzt"}), 503

    scored = []
    skipped_budget = []
    errors = []

    for m in own:
        # Budget-Check vor jedem Match (kann sich mid-loop ändern)
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget.append(m.id)
            continue
        try:
            success = _run_claude_match_for(client, user, m)
            if success:
                scored.append({"id": m.id, "match_score": m.match_score})
            else:
                # Helper returnt False wenn schon bewertet ODER Budget gerade voll
                if m.match_score is not None:
                    scored.append({"id": m.id, "match_score": m.match_score})
                else:
                    skipped_budget.append(m.id)
        except Exception as e:
            errors.append({"id": m.id, "error": str(e)})

    db.session.commit()

    return jsonify({
        "scored": scored,
        "skipped_budget": skipped_budget,
        "errors": errors,
        "forbidden": forbidden,
        "not_found": not_found,
    }), 200
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/api/test_jobs_user.py -k "score_bulk" -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat: POST /api/jobs/matches/score-bulk (Bulk-Claude-Match, Budget-aware)"
```

---

## Task 5: Bulk-Status-Endpoint PATCH /api/jobs/matches/bulk

Bulk-Statuswechsel (seen|dismissed) für mehrere Matches.

**Files:**
- Modify: `api/jobs_user.py`
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Write failing tests**

```python
def test_bulk_status_update_dismisses_matches(client, app, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Job", url="https://j/1")
    db.session.add(raw); db.session.flush()

    matches = []
    for _ in range(3):
        m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
        db.session.add(m); matches.append(m)
    db.session.commit()
    ids = [m.id for m in matches]

    r = client.patch("/api/jobs/matches/bulk",
                     json={"match_ids": ids, "status": "dismissed"},
                     headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["updated"] == 3
    for m in matches:
        db.session.refresh(m)
        assert m.status == "dismissed"


def test_bulk_status_update_skips_other_users_matches(client, app, user_factory, auth_header):
    headers, user = auth_header
    other = user_factory(email="other@example.com")
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Job", url="https://j/1")
    db.session.add(raw); db.session.flush()

    m_mine = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    m_other = JobMatch(raw_job_id=raw.id, user_id=other.id, status='new')
    db.session.add_all([m_mine, m_other]); db.session.commit()

    r = client.patch("/api/jobs/matches/bulk",
                     json={"match_ids": [m_mine.id, m_other.id], "status": "seen"},
                     headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["updated"] == 1
    assert m_other.id in body["forbidden"]

    db.session.refresh(m_mine)
    db.session.refresh(m_other)
    assert m_mine.status == "seen"
    assert m_other.status == "new"  # unverändert


def test_bulk_status_validates_input(client, app, auth_header):
    headers, _ = auth_header
    r = client.patch("/api/jobs/matches/bulk", json={}, headers=headers)
    assert r.status_code == 400

    r = client.patch("/api/jobs/matches/bulk",
                     json={"match_ids": [], "status": "seen"}, headers=headers)
    assert r.status_code == 400

    r = client.patch("/api/jobs/matches/bulk",
                     json={"match_ids": [1], "status": "invalid"}, headers=headers)
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/api/test_jobs_user.py -k "bulk_status" -v
```

Expected: FAIL — endpoint nicht da.

- [ ] **Step 3: Implement endpoint**

In `api/jobs_user.py` nach `score_match_bulk`:

```python
@jobs_user_bp.patch('/matches/bulk')
@token_required
def update_match_bulk(user):
    """Bulk-Statuswechsel. Akzeptiert nur 'seen' und 'dismissed' (kein 'new')."""
    data = request.get_json() or {}
    ids = data.get("match_ids")
    new_status = data.get("status")

    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "match_ids muss nicht-leere Liste sein"}), 400
    if new_status not in ('seen', 'dismissed'):
        return jsonify({"error": "status muss 'seen' oder 'dismissed' sein"}), 400

    matches = JobMatch.query.filter(JobMatch.id.in_(ids)).all()
    found_ids = {m.id for m in matches}
    not_found = [i for i in ids if i not in found_ids]
    forbidden = []
    updated = 0

    for m in matches:
        if m.user_id != user.id:
            forbidden.append(m.id)
            continue
        m.status = new_status
        updated += 1

    db.session.commit()
    return jsonify({
        "updated": updated,
        "forbidden": forbidden,
        "not_found": not_found,
    }), 200
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/api/test_jobs_user.py -k "bulk_status" -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat: PATCH /api/jobs/matches/bulk (Bulk-Status seen|dismissed)"
```

---

## Task 6: Import-Endpoint mit Auto-Claude-Match

Bestehender Endpoint `/matches/<id>/import` ruft Claude wenn `match_score=None`.

**Files:**
- Modify: `api/jobs_user.py` (existing import_match function)
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Write failing tests**

Am Ende von `tests/api/test_jobs_user.py`:

```python
def test_import_runs_claude_when_match_score_none(client, app, user_factory, auth_header):
    """Import bei match_score=None → Claude wird gerufen, Score landet in DB + Notes."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 1000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1",
                 company="ACME", description="Python role")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 prefilter_score=42, match_score=None)
    db.session.add(m); db.session.commit()

    fake_result = MagicMock(score=88, reasoning="passt sehr gut",
                            missing_skills=["docker"], tokens_in=20, tokens_out=20)
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)

    assert r.status_code == 201
    body = r.get_json()
    db.session.refresh(m)
    assert m.match_score == 88
    assert m.match_reasoning == "passt sehr gut"

    app_obj = Application.query.get(body["application_id"])
    assert "passt sehr gut" in app_obj.notes
    assert "88" in app_obj.notes


def test_import_skips_claude_when_budget_exhausted_but_creates_application(
    client, app, user_factory, auth_header
):
    """Import bei Budget-Erschöpfung: kein Claude, aber Application wird trotzdem angelegt."""
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 50
    db.session.add(ApiCall(user_id=user.id, endpoint='/test', model='x',
                           tokens_in=0, tokens_out=0, cost=1.00, key_owner='server'))
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1",
                 company="ACME")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    from unittest.mock import patch, MagicMock
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()):
        r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)

    assert r.status_code == 201
    body = r.get_json()
    app_obj = Application.query.get(body["application_id"])
    assert "Bewertung übersprungen" in app_obj.notes  # Notes-Text bei Budget-Skip
    db.session.refresh(m)
    assert m.match_score is None  # nicht bewertet
    assert m.status == "imported"  # Import trotzdem erfolgreich
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/api/test_jobs_user.py -k "import_runs_claude or import_skips_claude" -v
```

Expected: FAIL — bestehender Endpoint ruft Claude noch nicht.

- [ ] **Step 3: Modify import_match**

Bestehende Funktion `import_match` in `api/jobs_user.py` (Zeilen ~210-246) ersetzen:

```python
@jobs_user_bp.post('/matches/<int:match_id>/import')
@token_required
def import_match(user, match_id: int):
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    raw = RawJob.query.get(m.raw_job_id)
    src = JobSource.query.get(raw.source_id)

    # NEU: Wenn noch nicht bewertet, Claude versuchen (mit Budget-Check)
    budget_skipped = False
    if m.match_score is None:
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            budget_skipped = True
        else:
            client = _get_anthropic_client()
            if client is not None:
                _run_claude_match_for(client, user, m)
                # Wenn _run_claude_match_for False zurückgibt (z.B. Claude-Error),
                # bleibt match_score weiter None — kein Hard-Fail.

    score_str = f"{m.match_score:.0f}" if m.match_score is not None else "–"
    if budget_skipped:
        reasoning = "Bewertung übersprungen — Tagesbudget erschöpft"
        missing_str = "–"
    else:
        reasoning = m.match_reasoning or "–"
        missing_str = ', '.join(m.missing_skills) if m.missing_skills else '–'

    note_text = (
        f"Aus Job-Vorschlag importiert (Match-Score {score_str}).\n\n"
        f"Begruendung: {reasoning}\n\n"
        f"Fehlende Skills: {missing_str}\n\n"
        f"Original-Link: {raw.url}"
    )

    application = Application(
        user_id=user.id,
        company=raw.company or "Unbekannt",
        position=raw.title,
        status='beworben',
        applied_date=raw.posted_at.date() if raw.posted_at else None,
        location=raw.location,
        source=src.name if src else None,
        link=raw.url,
        notes=note_text,
    )
    db.session.add(application)
    db.session.flush()

    m.status = 'imported'
    m.imported_application_id = application.id
    db.session.commit()

    return jsonify({"application_id": application.id}), 201
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/api/test_jobs_user.py -k "import" -v
```

Expected: PASS — sowohl die neuen 2 Tests als auch der existierende `test_import_match_creates_application`, `test_import_match_other_user_forbidden`, `test_import_match_null_score`, `test_import_match_transfers_all_fields`.

Falls `test_import_match_null_score` nun fehlschlägt (weil das alte Verhalten für `match_score=None` anders war), den Test prüfen — wahrscheinlich wird er noch passen, weil ohne API-Key bzw. ohne Claude-Mock Claude geskippt wird und Notes-Text "–" enthält.

Wenn dieser bestehende Test jetzt einen anderen Notes-Text erwartet, anpassen:
```python
# In test_import_match_null_score:
# Ändern: assert "Match-Score –" in app_obj.notes  (bleibt korrekt)
# Falls der Test ANTHROPIC_API_KEY = None setzt und kein Mock benutzt, läuft Claude nicht → "–" bleibt richtig.
```

- [ ] **Step 5: Run full jobs_user tests**

```bash
pytest tests/api/test_jobs_user.py -v
```

Expected: PASS (alle Tests)

- [ ] **Step 6: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat: import_match ruft Claude wenn match_score=None (mit Budget-Check)"
```

---

## Task 7: Frontend — Card-Anzeige + "Bewerten lassen"-Button

Card mit `match_score=null` zeigt prefilter_score + neuen Button. Card mit match_score behält bisherige Anzeige. Beide bekommen Checkbox.

**Files:**
- Modify: `index.html` (Lines ~2787-2830, renderCard + badge functions)

- [ ] **Step 1: Add prefilter_score to /matches response**

Erst sicherstellen dass das Backend `prefilter_score` ausgibt. Datei: `api/jobs_user.py`, Funktion `_serialize_match` (~Line 140):

```python
def _serialize_match(m: JobMatch, raw: RawJob, src: JobSource) -> dict:
    return {
        "id": m.id,
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
        "prefilter_score": m.prefilter_score,    # NEU
        "status": m.status,
        "notified_at": m.notified_at.isoformat() if m.notified_at else None,
        "imported_application_id": m.imported_application_id,
        "raw_job": {
            "id": raw.id, "title": raw.title, "company": raw.company,
            "location": raw.location, "url": raw.url, "description": raw.description,
            "posted_at": raw.posted_at.isoformat() if raw.posted_at else None,
            "source_name": src.name, "source_id": src.id,
        },
    }
```

- [ ] **Step 2: Run jobs_user tests — verify keine Regression**

```bash
pytest tests/api/test_jobs_user.py -v
```

Expected: PASS

- [ ] **Step 3: Modify renderCard in index.html**

In `index.html` die Funktion `renderCard` (~Zeile 2797-2831) ersetzen:

```javascript
    function renderCard(m) {
        const r = m.raw_job || {};
        const date = r.posted_at ? new Date(r.posted_at).toLocaleDateString('de-DE') : '';
        const isSelected = state.selectedIds.has(m.id);

        const hasClaudeScore = m.match_score != null;
        const score = hasClaudeScore ? m.match_score.toFixed(0)
                                     : (m.prefilter_score != null ? m.prefilter_score.toFixed(0) : '–');
        const scoreLabel = hasClaudeScore ? '' : 'Vor-Filter: ';
        const scoreBadgeBg = hasClaudeScore ? 'var(--bg-card2)' : '#444';
        const scoreEmoji = hasClaudeScore ? badge(m.match_score) : '⚪';

        const missing = (m.missing_skills || []).slice(0, 5).map(s => escapeHtml(s));

        const evaluateBtn = hasClaudeScore ? '' : `
            <button class="btn btn-primary btn-sm" onclick="JobsView.requestSingleScore(${m.id})">
                🤖 Bewerten lassen
            </button>`;

        return `
            <div class="card" style="margin-bottom:1rem;padding:1rem">
                <div style="display:flex;align-items:flex-start;gap:0.75rem;flex-wrap:wrap">
                    <input type="checkbox" class="job-bulk-checkbox" data-match-id="${m.id}"
                           ${isSelected ? 'checked' : ''}
                           onchange="JobsView.toggleSelection(${m.id}, this.checked)"
                           style="margin-top:0.5rem;cursor:pointer">
                    <span style="background:${scoreBadgeBg};padding:6px 12px;border-radius:999px;font-weight:600;font-size:1.05em">
                        ${scoreEmoji} ${scoreLabel}${score}
                    </span>
                    <h3 style="margin:0;flex:1;min-width:240px;font-size:1.1em">${escapeHtml(r.title)}</h3>
                </div>
                <div style="color:var(--text-muted);font-size:0.85em;margin-top:0.5rem">
                    ${escapeHtml(r.company || '')}${r.location ? ' · ' + escapeHtml(r.location) : ''}${date ? ' · ' + date : ''}${r.source_name ? ' · ' + escapeHtml(r.source_name) : ''}
                </div>
                ${m.match_reasoning ? `
                    <p style="margin:0.75rem 0;border-left:3px solid var(--primary);padding-left:0.75rem;font-style:italic">
                        ${escapeHtml(m.match_reasoning)}
                    </p>
                ` : ''}
                ${missing.length ? `
                    <p style="color:var(--warning);margin:0.5rem 0;font-size:0.9em">
                        ⚠ Fehlt im CV:
                        ${missing.map(s => `<span style="display:inline-block;background:var(--bg-card2);padding:2px 8px;border-radius:4px;margin-right:4px;font-size:0.85em">${s}</span>`).join('')}
                    </p>
                ` : ''}
                <div style="display:flex;gap:0.5rem;margin-top:0.75rem;flex-wrap:wrap">
                    <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">🔗 Original</a>
                    ${evaluateBtn}
                    <button class="btn btn-success btn-sm" onclick="JobsView.importMatch(${m.id})">📥 Übernehmen</button>
                    <button class="btn btn-secondary btn-sm" onclick="JobsView.markSeen(${m.id})">👁 Verbergen</button>
                    <button class="btn btn-danger btn-sm" onclick="JobsView.dismissMatch(${m.id})">🗑️ Verwerfen</button>
                </div>
            </div>`;
    }
```

- [ ] **Step 4: Add `requestSingleScore` and `toggleSelection` handlers**

In `index.html` im `JobsView`-Module (such nach `JobsView.importMatch =` o.ä.) folgende Handler hinzufügen — nach `dismissMatch`:

```javascript
    JobsView.requestSingleScore = async function(id) {
        try {
            const r = await Auth.fetch(`/jobs/matches/${id}/score`, { method: 'POST' });
            if (r && r.match_score != null) {
                showToast(`Bewertung erstellt: ${r.match_score.toFixed(0)}/100`, 'success');
                await fetchMatches();
            } else if (r && r.error) {
                showToast(r.error, 'warning');
            }
        } catch (e) {
            showToast('Bewertung fehlgeschlagen', 'error');
        }
    };

    JobsView.toggleSelection = function(id, isChecked) {
        if (isChecked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        renderBulkActionBar();
    };
```

`showToast` ist eine bestehende UI-Helper-Funktion im File — falls nicht vorhanden, fall back auf `alert(...)`.

- [ ] **Step 5: Add selectedIds to state**

In `index.html` such nach `const state = {` im JobsView-Module. Füge `selectedIds: new Set(),` hinzu:

```javascript
    const state = {
        // ... bestehende Felder
        selectedIds: new Set(),
    };
```

- [ ] **Step 6: Add stub `renderBulkActionBar` (will be filled in Task 8)**

```javascript
    function renderBulkActionBar() {
        // TODO: Task 8 implementiert die Floating Bar
        const count = state.selectedIds.size;
        console.log(`[JobsView] Selection: ${count} matches selected`);
    }
```

- [ ] **Step 7: Manual Test im Browser**

Browser öffnen, einloggen, zu Job-Vorschlägen navigieren. Du solltest sehen:
- Cards mit `match_score=null` zeigen graues Badge "⚪ Vor-Filter: 42" + "🤖 Bewerten lassen"-Button
- Cards mit match_score zeigen farbiges Badge ohne "Bewerten lassen"-Button
- Checkboxes links auf jeder Card; Klick zeigt console.log

Wenn das passt, weiter zu Task 8.

- [ ] **Step 8: Commit**

```bash
git add index.html api/jobs_user.py
git commit -m "feat(ui): Card mit prefilter_score-Badge + Bewerten-lassen-Button + Checkbox"
```

---

## Task 8: Frontend — Floating Action Bar + Bulk-Handlers

Floating Bar erscheint bei Auswahl ≥ 1, mit 3 Buttons + Counter + Cancel.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add Floating Action Bar HTML**

In `index.html` such nach dem Container der Job-Vorschläge (oft `<section id="jobs-section">` oder ähnlich). Direkt am ENDE des `<body>` (vor schließendem `</body>`) ein neues Element einfügen:

```html
<div id="jobs-bulk-bar" style="position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);
    display:none;background:var(--bg-card);border:1px solid var(--border);border-radius:999px;
    padding:0.75rem 1.25rem;box-shadow:0 4px 12px rgba(0,0,0,0.3);z-index:100;
    align-items:center;gap:0.75rem">
    <span id="jobs-bulk-count" style="font-weight:600">0 ausgewählt</span>
    <button class="btn btn-primary btn-sm" onclick="JobsView.bulkScore()">🤖 Bewerten</button>
    <button class="btn btn-secondary btn-sm" onclick="JobsView.bulkSeen()">👁 Verbergen</button>
    <button class="btn btn-danger btn-sm" onclick="JobsView.bulkDismiss()">🗑️ Verwerfen</button>
    <button class="btn btn-secondary btn-sm" onclick="JobsView.clearSelection()" title="Auswahl aufheben">✕</button>
</div>
```

- [ ] **Step 2: Replace `renderBulkActionBar` stub**

In `index.html` die stub-Funktion ersetzen:

```javascript
    function renderBulkActionBar() {
        const bar = document.getElementById('jobs-bulk-bar');
        const count = state.selectedIds.size;
        if (count === 0) {
            bar.style.display = 'none';
        } else {
            bar.style.display = 'flex';
            document.getElementById('jobs-bulk-count').textContent = `${count} ausgewählt`;
        }
    }
```

- [ ] **Step 3: Add bulk handlers**

In `index.html` im `JobsView`-Module nach `requestSingleScore`:

```javascript
    JobsView.bulkScore = async function() {
        const ids = Array.from(state.selectedIds);
        if (ids.length === 0) return;
        try {
            const r = await Auth.fetch('/jobs/matches/score-bulk', {
                method: 'POST',
                body: JSON.stringify({ match_ids: ids }),
            });
            if (r) {
                const scoredCount = (r.scored || []).length;
                const skippedCount = (r.skipped_budget || []).length;
                let msg = `${scoredCount} bewertet`;
                if (skippedCount > 0) msg += `, ${skippedCount} wegen Budget übersprungen`;
                showToast(msg, skippedCount > 0 ? 'warning' : 'success');
                JobsView.clearSelection();
                await fetchMatches();
            }
        } catch (e) {
            showToast('Bulk-Bewertung fehlgeschlagen', 'error');
        }
    };

    JobsView.bulkSeen = async function() {
        const ids = Array.from(state.selectedIds);
        if (ids.length === 0) return;
        try {
            const r = await Auth.fetch('/jobs/matches/bulk', {
                method: 'PATCH',
                body: JSON.stringify({ match_ids: ids, status: 'seen' }),
            });
            if (r) {
                showToast(`${r.updated} verborgen`, 'success');
                JobsView.clearSelection();
                await fetchMatches();
            }
        } catch (e) {
            showToast('Bulk-Verbergen fehlgeschlagen', 'error');
        }
    };

    JobsView.bulkDismiss = async function() {
        const ids = Array.from(state.selectedIds);
        if (ids.length === 0) return;
        if (!confirm(`${ids.length} Jobs verwerfen?`)) return;
        try {
            const r = await Auth.fetch('/jobs/matches/bulk', {
                method: 'PATCH',
                body: JSON.stringify({ match_ids: ids, status: 'dismissed' }),
            });
            if (r) {
                showToast(`${r.updated} verworfen`, 'success');
                JobsView.clearSelection();
                await fetchMatches();
            }
        } catch (e) {
            showToast('Bulk-Verwerfen fehlgeschlagen', 'error');
        }
    };

    JobsView.clearSelection = function() {
        state.selectedIds.clear();
        renderBulkActionBar();
        // Re-render Cards damit Checkboxen visuell zurückgesetzt werden
        fetchMatches();
    };
```

- [ ] **Step 4: Reset selection on filter / pagination change**

Such in `index.html` nach den Filter-Change-Handlers (z.B. wo `state.filters.status` gesetzt wird, oder wo `state.offset` geändert wird). In jedem davon **am Anfang** hinzufügen:

```javascript
state.selectedIds.clear();
renderBulkActionBar();
```

Ein typischer Ort: in `setStatusFilter`, `setMinScoreFilter`, `applyQueryFilter`, `goToPage` oder ähnlich. Such mit `grep -n "state.offset = \|state.filters\." index.html` und reset Selection an jeder Stelle wo state mutiert wird.

- [ ] **Step 5: Manual Test im Browser**

- 3 Cards anklicken (Checkbox) → Bar erscheint mit "3 ausgewählt"
- "🗑️ Verwerfen" klicken → Confirm → Cards verschwinden, Bar verschwindet
- 2 Cards selektieren, "👁 Verbergen" → Cards verschwinden
- Cards mit `match_score=null` selektieren, "🤖 Bewerten" → Toast bestätigt, Cards refreshen mit echtem Score
- Filter wechseln (z.B. status=seen) → Selection wird leer, Bar verschwindet

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(ui): Floating Action Bar mit Bulk-Bewerten/Verbergen/Verwerfen"
```

---

## Task 9: Cron-Schedule auf VPS umstellen

Frequenz von alle 30 min auf 1×/Tag.

**Files:**
- Modify (auf VPS): `/etc/cron.d/job-discovery`

- [ ] **Step 1: SSH to VPS and view current cron**

```bash
ssh ionos-vps 'cat /etc/cron.d/job-discovery'
```

Erwartete Zeile (Stage 3):
```
0,30 * * * *        root /usr/local/bin/job-discovery-cron.sh claude-match
```

- [ ] **Step 2: Replace with daily schedule**

```bash
ssh ionos-vps 'sed -i "s|^0,30 \* \* \* \*\(.*claude-match.*\)|0 8 * * *\1|" /etc/cron.d/job-discovery && cat /etc/cron.d/job-discovery'
```

Erwartete neue Zeile:
```
0 8 * * *        root /usr/local/bin/job-discovery-cron.sh claude-match
```

- [ ] **Step 3: Reload cron daemon**

```bash
ssh ionos-vps 'systemctl reload crond && systemctl status crond | head -5'
```

Expected: `active (running)`.

- [ ] **Step 4: Verify cron entries are picked up**

```bash
ssh ionos-vps 'sudo run-parts --test /etc/cron.daily 2>/dev/null; sudo crontab -l 2>/dev/null; sudo cat /etc/cron.d/job-discovery'
```

(Hauptsache der File ist auf neuem Stand. crond reload reicht; kein Restart nötig.)

- [ ] **Step 5: Document in DEPLOYMENT.md**

In `/Library/WebServer/Documents/Bewerbungstracker/DEPLOYMENT.md`, Section "VPS Production", such nach "Cron" oder "job-discovery" und ergänze (oder erstelle neue Section "Job-Discovery Cron-Tuning"):

```markdown
### Claude-Match Cron-Frequenz

`claude-match` Stage läuft 1×/Tag um 08:00 UTC und bewertet nur prefilter_score ≥ 50.
User-getriggerte Bewertungen (Single, Bulk, Import) ignorieren diesen Threshold und
respektieren das Tagesbudget.

Wenn User-Volume wächst oder mehr Auto-Bewertungen gewünscht sind, in
`/etc/cron.d/job-discovery` Zeile anpassen (z.B. auf `0 8,18 * * *` für 2×/Tag).
```

- [ ] **Step 6: Commit doc update**

```bash
git add DEPLOYMENT.md
git commit -m "docs: claude-match cron läuft 1×/Tag (siehe spec/plan)"
```

---

## Task 10: Final Validation

**Files:** None (manual checks)

- [ ] **Step 1: Run full backend test suite**

```bash
pytest tests/ -v 2>&1 | tail -10
```

Expected: ALL PASS, keine Regressionen.

- [ ] **Step 2: Push to origin + deploy to VPS**

```bash
git push origin master
ssh ionos-vps 'cd /var/www/bewerbungen && git pull origin master && systemctl restart bewerbungen'
```

- [ ] **Step 3: Smoke test on VPS**

```bash
# Single-Score-Endpoint testen (mit JWT-Token aus Browser-DevTools)
TOKEN="..."  # aus localStorage.access_token
curl -X POST -H "Authorization: Bearer $TOKEN" \
    "https://bewerbungen.wolfinisoftware.de/api/jobs/matches/<id>/score"
# Erwarte 200 mit match_score ODER 402 wenn Budget aus
```

- [ ] **Step 4: Browser-Test im Live-System**

- Login → Jobvorschläge öffnen
- Cards sehen prefilter_score (alte Matches haben vermutlich schon match_score)
- "🤖 Bewerten lassen" auf einer Card mit match_score=null → score erscheint
- 3 Cards selektieren → Floating Bar
- "🗑️ Verwerfen" Bulk → Cards verschwinden

- [ ] **Step 5: Monitor logs first 24h**

```bash
ssh ionos-vps 'tail -f /var/log/bewerbungen/cron.log /var/log/bewerbungen/app.log 2>/dev/null'
```

Beobachten: claude-match-Cron um 08:00 UTC läuft genau 1× (nicht alle 30min). Score-Endpoint-Aufrufe werden korrekt verbucht.

---

## Self-Review Notes

**Spec coverage:**
- ✅ Auto-Cron 1×/Tag, threshold 50 → Tasks 2 + 9
- ✅ POST /matches/<id>/score → Task 3
- ✅ POST /matches/score-bulk → Task 4
- ✅ PATCH /matches/bulk → Task 5
- ✅ Import ruft Claude → Task 6
- ✅ _run_claude_match_for shared helper → Task 1
- ✅ Card mit prefilter_score + "Bewerten lassen" → Task 7
- ✅ Checkbox + Floating Action Bar → Tasks 7 + 8
- ✅ Filter-/Pagination-Reset der Auswahl → Task 8 Step 4
- ✅ Edge cases (mixed ownership, validation, idempotency) → Tests in Tasks 3-5

**Type consistency:**
- `_run_claude_match_for(client, user, match) -> bool` — gleicher Signature in Tasks 1, 3, 4, 6
- `prefilter_score` Feld in Serializer (Task 7) + verwendet in JS (Task 7)
- `state.selectedIds` als Set (Tasks 7, 8) — konsistent

**Notes for implementation:**
- `pytest tests/api/test_jobs_user.py` muss `auth_header` und `user_factory` bereits als Fixtures haben (sind in `tests/conftest.py`)
- `_get_anthropic_client` wird in `api/jobs_user.py` neu definiert (lokale Kopie). Optional refactor in Task 11+: in shared `services/claude_client.py`, aber out-of-scope hier (YAGNI).
- Frontend-Tests sind manuell. Wenn Browser-Tests automatisiert werden sollen, separater Plan.
