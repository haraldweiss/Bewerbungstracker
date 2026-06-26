# Feedback Learning Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve user-feedback learning so stored feedback has a more stable and concrete effect on future job scores.

**Architecture:** Keep the existing `services/job_matching/learner.py` centroid mechanism as the source of adaptive score adjustment. Add bounded balancing and reason-specific penalties inside the learner, then make missing feedback paths call the same learner update function.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy models, pytest, existing Ollama embedding helpers.

## Global Constraints

- Business logic stays in `services/`; `api/` remains thin routing.
- Do not log raw CV text, email bodies, job descriptions, or free-form feedback text.
- No database migration unless existing columns are insufficient.
- No production deploy as part of this plan.
- Use TDD: write failing tests first, run them red, implement minimal code, run green.

---

### Task 1: Balanced Adaptive Score Adjustment

**Files:**
- Modify: `tests/services/test_learner.py`
- Modify: `services/job_matching/learner.py`

**Interfaces:**
- Consumes: `compute_score_adjustment(user, raw_job_id: int, base_score: float) -> float`
- Produces: same public function, with bounded dismissed-side influence when samples are highly imbalanced.

- [ ] **Step 1: Add failing test for dismissed imbalance**

Append this test to `tests/services/test_learner.py`:

```python
def test_compute_score_adjustment_dismissed_imbalance_is_bounded(app, user_factory):
    from database import db
    from models import JobEmbedding, UserLearnProfile
    from services.job_matching.embedder import vector_pack
    from services.job_matching.learner import compute_score_adjustment

    user = user_factory()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30

    job_vec = [1.0] + [0.0] * 767
    dismissed_vec = [0.0, 1.0] + [0.0] * 766
    imported_vec = [1.0] + [0.0] * 767

    profile = UserLearnProfile(
        user_id=user.id,
        imported_centroid=vector_pack(imported_vec),
        dismissed_centroid=vector_pack(dismissed_vec),
        samples_imported=10,
        samples_dismissed=1000,
    )
    db.session.add(profile)
    db.session.add(JobEmbedding(raw_job_id=123, vector=vector_pack(job_vec)))
    db.session.commit()

    adjusted = compute_score_adjustment(user, raw_job_id=123, base_score=50.0)

    assert adjusted > 50.0
    assert adjusted <= 65.0
```

- [ ] **Step 2: Run red test**

Run:

```bash
pytest tests/services/test_learner.py::test_compute_score_adjustment_dismissed_imbalance_is_bounded -v
```

Expected: FAIL because current logic does not apply imbalance-aware weighting.

- [ ] **Step 3: Implement minimal balancing helper**

In `services/job_matching/learner.py`, add this helper near `_incremental_mean`:

```python
def _dismissed_balance_factor(samples_imported: int, samples_dismissed: int) -> float:
    """Scale dismissed similarity down when dismisses heavily outnumber imports."""
    imported = max(samples_imported or 0, 1)
    dismissed = max(samples_dismissed or 0, 1)
    if dismissed <= imported * 3:
        return 1.0
    return max(0.35, min(1.0, (imported * 3) / dismissed))
```

Then change `compute_score_adjustment()` from:

```python
adjusted = base_score * (1 + alpha * (sim_imp - sim_dis))
```

to:

```python
dismissed_factor = _dismissed_balance_factor(
    profile.samples_imported or 0,
    profile.samples_dismissed or 0,
)
adjusted = base_score * (1 + alpha * (sim_imp - (sim_dis * dismissed_factor)))
```

- [ ] **Step 4: Run green tests for learner**

Run:

```bash
pytest tests/services/test_learner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add services/job_matching/learner.py tests/services/test_learner.py
git commit -m "feat: balance feedback learning score adjustment"
```

---

### Task 2: Reason-Specific Score Penalties

**Files:**
- Modify: `tests/services/test_learner.py`
- Modify: `services/job_matching/learner.py`

**Interfaces:**
- Consumes: `UserLearnProfile.reason_counts`, `RawJob.title`, `RawJob.description`, `RawJob.location`
- Produces: private helper `_apply_reason_adjustments(user, raw_job_id: int, score: float, profile) -> float`

- [ ] **Step 1: Add failing test for seniority reason**

Append this test to `tests/services/test_learner.py`:

```python
def test_compute_score_adjustment_penalizes_repeated_wrong_seniority(app, user_factory):
    import json
    from database import db
    from models import JobEmbedding, JobSource, RawJob, UserLearnProfile
    from services.job_matching.embedder import vector_pack
    from services.job_matching.learner import compute_score_adjustment

    user = user_factory()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30

    source = JobSource(name="test", type="rss", url="https://example.test/feed")
    db.session.add(source)
    db.session.flush()

    raw = RawJob(
        source_id=source.id,
        external_id="seniority-1",
        title="Senior Principal Enterprise Architect",
        description="Very senior leadership role with architecture governance.",
        url="https://example.test/job",
        crawl_status="matched",
    )
    db.session.add(raw)
    db.session.flush()

    vec = [1.0] + [0.0] * 767
    profile = UserLearnProfile(
        user_id=user.id,
        imported_centroid=vector_pack(vec),
        dismissed_centroid=vector_pack(vec),
        samples_imported=5,
        samples_dismissed=5,
        reason_counts=json.dumps({"wrong_seniority": 5}),
    )
    db.session.add(profile)
    db.session.add(JobEmbedding(raw_job_id=raw.id, vector=vector_pack(vec)))
    db.session.commit()

    adjusted = compute_score_adjustment(user, raw_job_id=raw.id, base_score=80.0)

    assert adjusted == 72.0
```

- [ ] **Step 2: Run red test**

Run:

```bash
pytest tests/services/test_learner.py::test_compute_score_adjustment_penalizes_repeated_wrong_seniority -v
```

Expected: FAIL because reason-specific penalties do not exist.

- [ ] **Step 3: Implement reason adjustment helpers**

In `services/job_matching/learner.py`, add:

```python
_SENIORITY_TERMS = (
    "senior", "principal", "lead", "leiter", "leitung", "head of",
    "director", "chief", "junior", "werkstudent", "praktikant", "intern",
)


def _load_reason_counts(profile) -> dict[str, int]:
    try:
        counts = json.loads(profile.reason_counts) if profile.reason_counts else {}
    except (ValueError, TypeError):
        return {}
    return {str(k): int(v) for k, v in counts.items() if isinstance(v, int)}


def _strong_reason(counts: dict[str, int], reason: str) -> bool:
    return counts.get(reason, 0) >= 3


def _apply_reason_adjustments(user, raw_job_id: int, score: float, profile) -> float:
    from models import RawJob

    counts = _load_reason_counts(profile)
    if not counts:
        return score

    raw = RawJob.query.get(raw_job_id)
    if raw is None:
        return score

    adjusted = score
    title_desc = f"{raw.title or ''} {raw.description or ''}".lower()

    if _strong_reason(counts, "wrong_seniority"):
        if any(term in title_desc for term in _SENIORITY_TERMS):
            adjusted *= 0.90

    if _strong_reason(counts, "missing_skills"):
        adjusted *= 0.95

    return max(0.0, min(100.0, round(adjusted, 2)))
```

Then apply it at the end of `compute_score_adjustment()`:

```python
adjusted = base_score * (1 + alpha * (sim_imp - (sim_dis * dismissed_factor)))
adjusted = max(0.0, min(100.0, adjusted))
return _apply_reason_adjustments(user, raw_job_id, adjusted, profile)
```

- [ ] **Step 4: Run green learner tests**

Run:

```bash
pytest tests/services/test_learner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add services/job_matching/learner.py tests/services/test_learner.py
git commit -m "feat: apply feedback reason penalties"
```

---

### Task 3: Close Feedback Update Paths

**Files:**
- Modify: `tests/api/test_quick_actions_endpoint.py`
- Modify: `tests/api/test_jobs_user.py`
- Modify: `api/jobs_user.py`

**Interfaces:**
- Consumes: `update_centroid_for_feedback(user, match) -> None`
- Produces: quick-action and bulk dismissal paths update `UserLearnProfile` when embeddings exist.

- [ ] **Step 1: Add failing quick-action learner test**

Append to `tests/api/test_quick_actions_endpoint.py`:

```python
def test_quick_action_updates_learning_profile(client, setup):
    from database import db
    from models import JobEmbedding, UserLearnProfile
    from services.job_matching.embedder import vector_pack

    user, raw, m, headers = setup
    db.session.add(JobEmbedding(raw_job_id=raw.id, vector=vector_pack([1.0] + [0.0] * 767)))
    db.session.commit()

    r = client.patch(
        f"/api/jobs/matches/{m.id}",
        json={"quick_action": "job_unavailable"},
        headers=headers,
    )

    assert r.status_code == 200
    profile = UserLearnProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.samples_dismissed == 1
```

- [ ] **Step 2: Run red quick-action test**

Run:

```bash
pytest tests/api/test_quick_actions_endpoint.py::test_quick_action_updates_learning_profile -v
```

Expected: FAIL because quick-action dismissal does not update the learner.

- [ ] **Step 3: Update quick-action endpoint**

In `api/jobs_user.py`, after the quick-action `db.session.commit()`, add:

```python
        from services.job_matching.learner import update_centroid_for_feedback
        try:
            update_centroid_for_feedback(user, m)
        except Exception as e:
            current_app.logger.warning('Centroid update failed: %s', e)
```

Keep the existing JSON response unchanged.

- [ ] **Step 4: Add failing bulk-dismiss learner test**

Append to `tests/api/test_jobs_user.py`:

```python
def test_bulk_dismiss_updates_learning_profile(client, app, user_factory, auth_header):
    from database import db
    from models import JobEmbedding, JobMatch, JobSource, RawJob, UserLearnProfile
    from services.job_matching.embedder import vector_pack

    user = user_factory()
    headers = auth_header(user)
    source = JobSource(name="bulk-learn", type="rss", url="https://example.test/feed")
    db.session.add(source)
    db.session.flush()

    raw = RawJob(
        source_id=source.id,
        external_id="bulk-learn-1",
        title="Security Engineer",
        url="https://example.test/job",
        crawl_status="matched",
    )
    db.session.add(raw)
    db.session.flush()
    match = JobMatch(raw_job_id=raw.id, user_id=user.id, status="new", match_score=70)
    db.session.add(match)
    db.session.flush()
    db.session.add(JobEmbedding(raw_job_id=raw.id, vector=vector_pack([1.0] + [0.0] * 767)))
    db.session.commit()

    r = client.patch(
        "/api/jobs/matches/bulk-status",
        json={"match_ids": [match.id], "status": "dismissed"},
        headers=headers,
    )

    assert r.status_code == 200
    profile = UserLearnProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.samples_dismissed == 1
```

- [ ] **Step 5: Run red bulk-dismiss test**

Run:

```bash
pytest tests/api/test_jobs_user.py::test_bulk_dismiss_updates_learning_profile -v
```

Expected: FAIL because bulk dismissal does not update the learner.

- [ ] **Step 6: Update bulk-status endpoint**

In `api/jobs_user.py`, inside the bulk-status path after setting a match to
`dismissed`, call:

```python
from services.job_matching.learner import update_centroid_for_feedback

for m in matches:
    m.status = 'dismissed'
    try:
        update_centroid_for_feedback(user, m)
    except Exception as e:
        current_app.logger.warning('Centroid update failed: %s', e)
```

If the existing endpoint already loops differently, keep its response format and
authorization checks exactly as-is; only add the learner update after the status
change for authorized matches.

- [ ] **Step 7: Run endpoint tests**

Run:

```bash
pytest tests/api/test_quick_actions_endpoint.py tests/api/test_jobs_user.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add api/jobs_user.py tests/api/test_quick_actions_endpoint.py tests/api/test_jobs_user.py
git commit -m "feat: update learner from feedback actions"
```

---

### Task 4: Final Verification and Notes

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: implementation from Tasks 1-3.
- Produces: session note documenting behavior and verification.

- [ ] **Step 1: Run focused verification**

Run:

```bash
pytest tests/services/test_learner.py tests/services/test_prefilter_learner.py tests/api/test_quick_actions_endpoint.py tests/api/test_jobs_user.py tests/integration/test_learning_e2e.py -v
```

Expected: PASS. If `tests/api/test_jobs_user.py` is too slow, still run it and record exact failure or pass count.

- [ ] **Step 2: Run cron regression if learner changed prefilter behavior**

Run:

```bash
pytest tests/api/test_jobs_cron.py -v
```

Expected: PASS.

- [ ] **Step 3: Add changelog entry**

Prepend a dated entry to `CHANGELOG.md`:

```markdown
### 2026-06-26 — Feedback-Learning verbessert

- Adaptive Job-Score-Anpassung balanciert stark ungleiche imported/dismissed-Samples.
- Wiederholte strukturierte Feedback-Gründe wirken konservativ auf spätere Scores.
- Quick-Actions und Bulk-Dismisses aktualisieren das Lernprofil konsistenter.
- Verifikation: `pytest ...` mit den tatsächlich gelaufenen Tests und Ergebnissen.
```

- [ ] **Step 4: Commit verification note**

Run:

```bash
git add CHANGELOG.md
git commit -m "docs: note feedback learning improvements"
```

- [ ] **Step 5: Final git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree, branch ahead of `origin/master` by the new local commits.
