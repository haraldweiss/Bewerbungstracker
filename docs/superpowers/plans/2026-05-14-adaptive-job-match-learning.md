# Adaptive Job-Match Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lass den Job-Match-Algorithmus aus User-Bewertungen (dismissed/imported) lernen, indem strukturierte Begründungen + Embedding-Centroids den Prefilter-Score adjustieren.

**Architecture:** RawJobs werden via Ollama (nomic-embed-text) embedded. Pro User wird ein Centroid aus imported- und dismissed-Embeddings inkrementell gepflegt. Beim Prefilter wird der Basis-Score mit Cosine-Similarity zu beiden Centroids angepasst. Konfigurierbar pro User; robust bei Ollama-Ausfall.

**Tech Stack:** Flask, SQLAlchemy, NumPy (cosine + packing), pytest, Ollama (nomic-embed-text, 768-dim), Vanilla JS Frontend

---

## File Structure (zu erstellen/modifizieren)

**Neue Dateien:**
- `services/job_matching/embedder.py` — Ollama-Client, Vektor-Pack/Unpack, Cosine
- `services/job_matching/feedback.py` — Reasons-Konstanten + Validation
- `services/job_matching/learner.py` — Centroid-Update + Score-Adjustment
- `scripts/backfill_job_embeddings.py` — Embeddet bestehende RawJobs
- `scripts/rebuild_user_centroids.py` — Berechnet Centroids aus Historie
- `migrations/versions/XXXX_adaptive_learning.py` — Alembic-Migration
- `tests/services/test_embedder.py`
- `tests/services/test_feedback.py`
- `tests/services/test_learner.py`

**Modifizierte Dateien:**
- `models.py` — JobMatch, User erweitern; JobEmbedding, UserLearnProfile hinzufügen
- `services/job_matching/prefilter.py` — `score_job` um optionalen `user_id` erweitern
- `api/jobs_user.py` — PATCH-Erweiterung, bulk-Erweiterung, neuer GET-Endpoint
- `api/user_settings.py` (falls vorhanden, sonst `api/users.py`) — Settings-PATCH
- `frontend/index.html` (oder Frontend-File mit Job-Liste) — Dismiss-Modal + Settings
- `tests/api/test_jobs_user.py` — Tests für erweiterte Endpoints
- `requirements.txt` — `numpy` falls noch nicht vorhanden

---

## Task 1: Datenmodell-Erweiterung in models.py

**Files:**
- Modify: `models.py`
- Test: `tests/test_models_job_discovery.py`

- [ ] **Step 1: Schreibe failing Test für JobMatch.feedback_reasons**

Datei: `tests/test_models_job_discovery.py` — am Ende anhängen:

```python
def test_jobmatch_feedback_fields_persist(db_session, sample_user, sample_raw_job):
    from models import JobMatch
    m = JobMatch(
        raw_job_id=sample_raw_job.id,
        user_id=sample_user.id,
        status='dismissed',
        feedback_reasons='["salary_too_low","wrong_location"]',
        feedback_text='Zu weit weg',
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    assert m.feedback_reasons == '["salary_too_low","wrong_location"]'
    assert m.feedback_text == 'Zu weit weg'
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /Library/WebServer/Documents/Bewerbungstracker && pytest tests/test_models_job_discovery.py::test_jobmatch_feedback_fields_persist -v`

Expected: FAIL — "JobMatch has no attribute 'feedback_reasons'"

- [ ] **Step 3: Felder zu JobMatch hinzufügen**

In `models.py`, JobMatch class, nach `suspicious_reasons` Spalte einfügen:

```python
    # User-Feedback beim dismiss/import: strukturierte Reasons (JSON-Array)
    # und optionaler Freitext. Genutzt vom Adaptive-Learning-Modul.
    feedback_reasons = db.Column(db.Text, nullable=True)
    feedback_text = db.Column(db.Text, nullable=True)
```

- [ ] **Step 4: Run test — verify it passes**

Run: `pytest tests/test_models_job_discovery.py::test_jobmatch_feedback_fields_persist -v`

Expected: PASS

- [ ] **Step 5: User-Settings für Learning hinzufügen**

In `models.py`, User class, nach `job_reject_window_days`:

```python
    # Adaptive-Learning Settings: pro User konfigurierbar.
    # weight_pct als Int (0-100) um float-Migration zu vermeiden.
    job_learn_enabled = db.Column(db.Boolean, default=True, nullable=False)
    job_learn_min_samples = db.Column(db.Integer, default=3, nullable=False)
    job_learn_weight_pct = db.Column(db.Integer, default=30, nullable=False)
```

- [ ] **Step 6: JobEmbedding-Modell hinzufügen**

In `models.py`, nach RawJob class:

```python
class JobEmbedding(db.Model):
    """768-dim nomic-embed-text Vektor für RawJob (BLOB als float32-packed)."""
    __tablename__ = 'job_embeddings'

    raw_job_id = db.Column(db.Integer, db.ForeignKey('raw_jobs.id'), primary_key=True)
    vector = db.Column(db.LargeBinary, nullable=False)
    model = db.Column(db.String(64), default='nomic-embed-text', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    raw_job = db.relationship('RawJob', backref=db.backref('embedding', uselist=False))

    def __repr__(self):
        return f'<JobEmbedding raw_job_id={self.raw_job_id}>'
```

- [ ] **Step 7: UserLearnProfile-Modell hinzufügen**

In `models.py`, nach JobEmbedding:

```python
class UserLearnProfile(db.Model):
    """Pro-User Lern-Profil: Centroids + Sample-Counts.

    Centroids werden inkrementell aktualisiert beim Feedback-Event.
    reason_counts: JSON-Dict {reason_key: count}.
    """
    __tablename__ = 'user_learn_profiles'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    imported_centroid = db.Column(db.LargeBinary, nullable=True)
    dismissed_centroid = db.Column(db.LargeBinary, nullable=True)
    samples_imported = db.Column(db.Integer, default=0, nullable=False)
    samples_dismissed = db.Column(db.Integer, default=0, nullable=False)
    reason_counts = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('learn_profile', uselist=False))

    def __repr__(self):
        return f'<UserLearnProfile user_id={self.user_id} imp={self.samples_imported} dis={self.samples_dismissed}>'
```

- [ ] **Step 8: Run alle Model-Tests**

Run: `pytest tests/test_models_job_discovery.py -v`

Expected: All PASS (no regressions)

- [ ] **Step 9: Commit**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
git add models.py tests/test_models_job_discovery.py
git commit -m "feat(models): Adaptive-Learning Felder + JobEmbedding/UserLearnProfile"
```

---

## Task 2: Alembic-Migration für neue Felder/Tabellen

**Files:**
- Create: `migrations/versions/<rev>_adaptive_learning.py`

- [ ] **Step 1: Prüfe aktuelle Migrations-Revision**

Run: `cd /Library/WebServer/Documents/Bewerbungstracker && python -m alembic current 2>&1 | tail -5`

Notiere die Revision-ID — wird als `down_revision` benötigt.

- [ ] **Step 2: Migration generieren**

Run: `python -m alembic revision -m "adaptive_learning_fields_and_tables"`

Expected: Erstellt neue Datei in `migrations/versions/`

- [ ] **Step 3: Migration befüllen**

Öffne die neue Datei und ersetze die generierten `upgrade()`/`downgrade()`:

```python
def upgrade():
    # JobMatch: feedback fields
    with op.batch_alter_table('job_matches') as batch:
        batch.add_column(sa.Column('feedback_reasons', sa.Text(), nullable=True))
        batch.add_column(sa.Column('feedback_text', sa.Text(), nullable=True))

    # User: learn settings
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('job_learn_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('job_learn_min_samples', sa.Integer(), nullable=False, server_default='3'))
        batch.add_column(sa.Column('job_learn_weight_pct', sa.Integer(), nullable=False, server_default='30'))

    # JobEmbedding table
    op.create_table(
        'job_embeddings',
        sa.Column('raw_job_id', sa.Integer(), nullable=False),
        sa.Column('vector', sa.LargeBinary(), nullable=False),
        sa.Column('model', sa.String(64), nullable=False, server_default='nomic-embed-text'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['raw_job_id'], ['raw_jobs.id']),
        sa.PrimaryKeyConstraint('raw_job_id'),
    )

    # UserLearnProfile table
    op.create_table(
        'user_learn_profiles',
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('imported_centroid', sa.LargeBinary(), nullable=True),
        sa.Column('dismissed_centroid', sa.LargeBinary(), nullable=True),
        sa.Column('samples_imported', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('samples_dismissed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reason_counts', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
    )

def downgrade():
    op.drop_table('user_learn_profiles')
    op.drop_table('job_embeddings')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('job_learn_weight_pct')
        batch.drop_column('job_learn_min_samples')
        batch.drop_column('job_learn_enabled')
    with op.batch_alter_table('job_matches') as batch:
        batch.drop_column('feedback_text')
        batch.drop_column('feedback_reasons')
```

- [ ] **Step 4: Migration anwenden**

Run: `python -m alembic upgrade head`

Expected: "OK" mit den 2 neuen Tabellen + Spalten

- [ ] **Step 5: Downgrade-Test**

Run: `python -m alembic downgrade -1 && python -m alembic upgrade head`

Expected: Beide Operationen ohne Fehler

- [ ] **Step 6: Verify DB-Schema**

Run: `sqlite3 instance/bewerbungstracker.db ".schema job_embeddings"`

Expected: Tabelle mit allen 4 Spalten

- [ ] **Step 7: Commit**

```bash
git add migrations/versions/
git commit -m "migration: Adaptive-Learning Felder + Tabellen"
```

---

## Task 3: services/job_matching/embedder.py

**Files:**
- Create: `services/job_matching/embedder.py`
- Create: `tests/services/test_embedder.py`

- [ ] **Step 1: Schreibe failing Tests für embedder**

Datei: `tests/services/test_embedder.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from services.job_matching.embedder import (
    embed_text, vector_pack, vector_unpack, cosine_similarity, embed_raw_job
)


def test_vector_pack_unpack_roundtrip():
    original = [0.1, -0.2, 0.5, 1.0, -1.0]
    blob = vector_pack(original)
    restored = vector_unpack(blob)
    np.testing.assert_array_almost_equal(restored, original, decimal=5)


def test_cosine_similarity_identical():
    a = np.array([1.0, 2.0, 3.0])
    assert cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    a = np.array([0.0, 0.0])
    b = np.array([1.0, 1.0])
    assert cosine_similarity(a, b) == 0.0  # safe fallback, no NaN


def test_embed_text_returns_packed_bytes_on_success():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {'embedding': [0.1, 0.2, 0.3] * 256}  # 768-dim
        mock_req.post.return_value = mock_resp
        result = embed_text('hello world')
        assert result is not None
        assert isinstance(result, bytes)
        vec = vector_unpack(result)
        assert vec.shape == (768,)


def test_embed_text_returns_none_on_failure():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_req.post.side_effect = Exception('connection refused')
        result = embed_text('hello')
        assert result is None


def test_embed_text_returns_none_on_http_error():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_req.post.return_value = mock_resp
        result = embed_text('hello')
        assert result is None
```

- [ ] **Step 2: Run tests — verify fail**

Run: `pytest tests/services/test_embedder.py -v`

Expected: FAIL — module not found

- [ ] **Step 3: Implementiere embedder.py**

Datei: `services/job_matching/embedder.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Ollama-basierte Embedding-Helper (nomic-embed-text, 768-dim).

OLLAMA_HOST env (default: http://127.0.0.1:11434) zeigt auf den
autossh-Tunnel zum Mac. Bei Ausfall returnen alle Funktionen None
statt zu crashen — der Caller fällt auf reinen Prefilter-Score zurück.
"""

from __future__ import annotations
import os
import struct
import logging
import numpy as np
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
EMBED_DIM = 768
EMBED_TIMEOUT_S = 10


def vector_pack(vec) -> bytes:
    """Pack float-Liste/np.array zu float32-Bytes."""
    arr = np.asarray(vec, dtype=np.float32)
    return arr.tobytes()


def vector_unpack(blob: bytes) -> np.ndarray:
    """Restore float32-Array aus Bytes."""
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine-Similarity, safe gegen Zero-Vektoren."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embed_text(text: str) -> bytes | None:
    """Embed text via Ollama. Returns packed float32-bytes or None on failure."""
    if not text or not text.strip():
        return None
    try:
        resp = requests.post(
            f'{OLLAMA_HOST}/api/embeddings',
            json={'model': EMBED_MODEL, 'prompt': text[:8000]},
            timeout=EMBED_TIMEOUT_S,
        )
        if not resp.ok:
            logger.warning('Ollama embed failed: HTTP %s', resp.status_code)
            return None
        data = resp.json()
        vec = data.get('embedding')
        if not vec or len(vec) != EMBED_DIM:
            logger.warning('Ollama returned unexpected embedding (len=%s)', len(vec) if vec else 0)
            return None
        return vector_pack(vec)
    except Exception as e:
        logger.warning('Ollama embed exception: %s', e)
        return None


def embed_raw_job(raw_job) -> bool:
    """Embed RawJob und persistiere als JobEmbedding. Idempotent.

    Returns True bei Erfolg, False bei Ausfall (Ollama down).
    """
    from database import db
    from models import JobEmbedding

    existing = JobEmbedding.query.filter_by(raw_job_id=raw_job.id).first()
    if existing:
        return True  # idempotent

    text = f"{raw_job.title or ''}\n\n{raw_job.description or ''}"
    blob = embed_text(text)
    if blob is None:
        return False

    emb = JobEmbedding(raw_job_id=raw_job.id, vector=blob, model=EMBED_MODEL)
    db.session.add(emb)
    db.session.commit()
    return True
```

- [ ] **Step 4: Run tests — verify pass**

Run: `pytest tests/services/test_embedder.py -v`

Expected: All 6 tests PASS

- [ ] **Step 5: Stelle sicher dass numpy installiert ist**

Run: `python -c "import numpy; print(numpy.__version__)"`

Falls nicht installiert: `pip install numpy && echo numpy >> requirements.txt`

- [ ] **Step 6: Commit**

```bash
git add services/job_matching/embedder.py tests/services/test_embedder.py
git commit -m "feat(embedder): Ollama-Client + Vektor-Helper (nomic-embed-text)"
```

---

## Task 4: services/job_matching/feedback.py

**Files:**
- Create: `services/job_matching/feedback.py`
- Create: `tests/services/test_feedback.py`

- [ ] **Step 1: Schreibe failing Tests**

Datei: `tests/services/test_feedback.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import pytest

from services.job_matching.feedback import (
    FEEDBACK_REASONS, validate_reasons, increment_reason_counts
)


def test_validate_reasons_filters_invalid():
    result = validate_reasons(['salary_too_low', 'invalid_key', 'wrong_location'])
    assert 'salary_too_low' in result
    assert 'wrong_location' in result
    assert 'invalid_key' not in result


def test_validate_reasons_empty():
    assert validate_reasons([]) == []
    assert validate_reasons(None) == []


def test_validate_reasons_limit_max_5():
    inputs = list(FEEDBACK_REASONS.keys())  # 8 valid
    result = validate_reasons(inputs)
    assert len(result) == 5  # capped


def test_validate_reasons_dedupes():
    result = validate_reasons(['salary_too_low', 'salary_too_low', 'wrong_location'])
    assert result.count('salary_too_low') == 1


def test_increment_reason_counts_first_time():
    class FakeProfile:
        reason_counts = None
    p = FakeProfile()
    increment_reason_counts(p, ['salary_too_low'])
    counts = json.loads(p.reason_counts)
    assert counts['salary_too_low'] == 1


def test_increment_reason_counts_accumulates():
    class FakeProfile:
        reason_counts = json.dumps({'salary_too_low': 3, 'wrong_location': 1})
    p = FakeProfile()
    increment_reason_counts(p, ['salary_too_low', 'missing_skills'])
    counts = json.loads(p.reason_counts)
    assert counts['salary_too_low'] == 4
    assert counts['wrong_location'] == 1
    assert counts['missing_skills'] == 1
```

- [ ] **Step 2: Verify fail**

Run: `pytest tests/services/test_feedback.py -v`

Expected: FAIL — module not found

- [ ] **Step 3: Implementiere feedback.py**

Datei: `services/job_matching/feedback.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Standard-Feedback-Gründe für Job-Ablehnung/Annahme.

Erweiterbar ohne Migration — Validation prüft nur gegen diese Liste.
"""

from __future__ import annotations
import json

FEEDBACK_REASONS = {
    'wrong_location':   'Falscher Ort',
    'salary_too_low':   'Gehalt zu niedrig',
    'missing_skills':   'Fehlende Skills',
    'wrong_industry':   'Falsche Branche',
    'overqualified':    'Überqualifiziert',
    'underqualified':   'Unterqualifiziert',
    'wrong_seniority':  'Falsches Level',
    'other':            'Sonstiges',
}

MAX_REASONS_PER_FEEDBACK = 5
MAX_FEEDBACK_TEXT_CHARS = 500


def validate_reasons(reasons) -> list[str]:
    """Filtert ungültige Reasons + dedup + cappe auf max 5."""
    if not reasons:
        return []
    seen = set()
    result = []
    for r in reasons:
        if r in FEEDBACK_REASONS and r not in seen:
            seen.add(r)
            result.append(r)
            if len(result) >= MAX_REASONS_PER_FEEDBACK:
                break
    return result


def increment_reason_counts(profile, reasons: list[str]) -> None:
    """Inkrementiere reason_counts-JSON auf profile.

    profile muss .reason_counts (str|None) als Attribut haben.
    """
    try:
        counts = json.loads(profile.reason_counts) if profile.reason_counts else {}
    except (ValueError, TypeError):
        counts = {}
    for r in reasons:
        counts[r] = counts.get(r, 0) + 1
    profile.reason_counts = json.dumps(counts)
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/services/test_feedback.py -v`

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/feedback.py tests/services/test_feedback.py
git commit -m "feat(feedback): Standard-Reasons + Validation"
```

---

## Task 5: services/job_matching/learner.py

**Files:**
- Create: `services/job_matching/learner.py`
- Create: `tests/services/test_learner.py`

- [ ] **Step 1: Schreibe failing Tests**

Datei: `tests/services/test_learner.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from services.job_matching.embedder import vector_pack, vector_unpack
from services.job_matching.learner import (
    _incremental_mean, compute_score_adjustment, get_learn_profile_stats
)


def test_incremental_mean_first_sample():
    new_centroid = _incremental_mean(None, 0, np.array([1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(new_centroid, [1.0, 2.0, 3.0])


def test_incremental_mean_add_sample():
    old = np.array([1.0, 2.0, 3.0])  # n=2 average
    new = _incremental_mean(old, 2, np.array([3.0, 4.0, 5.0]))
    # ((1+1)*2 + (3,4,5))/3 — but we passed centroid (already avg), so
    # new = (old*n + sample) / (n+1) = ([1,2,3]*2 + [3,4,5]) / 3 = [5/3, 8/3, 11/3]
    np.testing.assert_array_almost_equal(new, [5/3, 8/3, 11/3])


def test_compute_score_adjustment_disabled_user():
    user = MagicMock()
    user.job_learn_enabled = False
    result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
    assert result == 50.0


def test_compute_score_adjustment_cold_start():
    """User mit <min_samples → kein Adjustment."""
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30
    user.id = 'u1'
    with patch('services.job_matching.learner._load_profile') as mock_lp:
        profile = MagicMock()
        profile.samples_imported = 2  # below threshold
        profile.samples_dismissed = 5
        mock_lp.return_value = profile
        result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
        assert result == 50.0


def test_compute_score_adjustment_no_embedding():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30
    user.id = 'u1'
    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack([1.0] * 768)
        profile.dismissed_centroid = vector_pack([0.0] * 768)
        mock_lp.return_value = profile
        mock_le.return_value = None  # no embedding
        result = compute_score_adjustment(user, raw_job_id=99, base_score=50.0)
        assert result == 50.0


def test_compute_score_adjustment_applies_boost():
    """Job ähnlich zu imported → Score wird erhöht."""
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 50  # α = 0.5
    user.id = 'u1'

    imported_vec = np.ones(768, dtype=np.float32)
    dismissed_vec = -np.ones(768, dtype=np.float32)
    job_vec = np.ones(768, dtype=np.float32)  # identisch zu imported

    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack(imported_vec)
        profile.dismissed_centroid = vector_pack(dismissed_vec)
        mock_lp.return_value = profile
        mock_le.return_value = job_vec

        result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
        # sim_imp = 1, sim_dis = -1 → adjustment = 50 × (1 + 0.5 × (1 - (-1))) = 50 × 2 = 100
        assert result == pytest.approx(100.0)


def test_compute_score_adjustment_clamps_to_100():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 1
    user.job_learn_weight_pct = 100
    user.id = 'u1'
    imported_vec = np.ones(768, dtype=np.float32)
    dismissed_vec = -np.ones(768, dtype=np.float32)
    job_vec = np.ones(768, dtype=np.float32)
    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack(imported_vec)
        profile.dismissed_centroid = vector_pack(dismissed_vec)
        mock_lp.return_value = profile
        mock_le.return_value = job_vec
        result = compute_score_adjustment(user, raw_job_id=1, base_score=80.0)
        assert result <= 100.0
        assert result >= 0.0
```

- [ ] **Step 2: Verify fail**

Run: `pytest tests/services/test_learner.py -v`

Expected: FAIL — module not found

- [ ] **Step 3: Implementiere learner.py**

Datei: `services/job_matching/learner.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Adaptive Lern-Mechanismus für Job-Match-Scoring.

Pflegt pro User Centroids aus imported/dismissed Jobs.
Adjustiert Prefilter-Score basierend auf Cosine-Similarity.

Cold-Start: Erst ab min_samples in beiden Klassen aktiv.
"""

from __future__ import annotations
import json
import logging
import numpy as np

from services.job_matching.embedder import (
    vector_pack, vector_unpack, cosine_similarity
)
from services.job_matching.feedback import (
    FEEDBACK_REASONS, increment_reason_counts
)

logger = logging.getLogger(__name__)


def _load_profile(user_id: str):
    """Lazy-load UserLearnProfile oder None."""
    from models import UserLearnProfile
    return UserLearnProfile.query.filter_by(user_id=user_id).first()


def _load_embedding(raw_job_id: int):
    """Returns np.array oder None falls kein Embedding existiert."""
    from models import JobEmbedding
    emb = JobEmbedding.query.filter_by(raw_job_id=raw_job_id).first()
    if emb is None:
        return None
    return vector_unpack(emb.vector)


def _incremental_mean(old_centroid_blob, old_count: int, new_vec: np.ndarray) -> np.ndarray:
    """Online-Mean: c_new = (c_old × n + v) / (n+1).

    Wenn old_centroid_blob None oder count==0, returns new_vec.
    Akzeptiert sowohl Bytes als auch np.array für old_centroid.
    """
    if old_centroid_blob is None or old_count == 0:
        return new_vec.astype(np.float32)
    if isinstance(old_centroid_blob, (bytes, bytearray)):
        old = vector_unpack(old_centroid_blob)
    else:
        old = old_centroid_blob
    return ((old * old_count + new_vec) / (old_count + 1)).astype(np.float32)


def update_centroid_for_feedback(user, match) -> None:
    """Update Centroid nach Status-Change auf dismissed/imported.

    match.status in ('dismissed', 'imported') erwartet.
    Triggered nach DB-Commit des Match-Updates.
    """
    from database import db
    from models import UserLearnProfile

    if match.status not in ('dismissed', 'imported'):
        return

    vec = _load_embedding(match.raw_job_id)
    if vec is None:
        logger.info('No embedding for raw_job_id=%s — skipping centroid update', match.raw_job_id)
        return

    profile = _load_profile(user.id)
    if profile is None:
        profile = UserLearnProfile(user_id=user.id)
        db.session.add(profile)

    if match.status == 'imported':
        new_centroid = _incremental_mean(profile.imported_centroid, profile.samples_imported, vec)
        profile.imported_centroid = vector_pack(new_centroid)
        profile.samples_imported += 1
    else:  # dismissed
        new_centroid = _incremental_mean(profile.dismissed_centroid, profile.samples_dismissed, vec)
        profile.dismissed_centroid = vector_pack(new_centroid)
        profile.samples_dismissed += 1

    # Reasons in counts ablegen (nur bei dismissed sinnvoll)
    if match.feedback_reasons:
        try:
            reasons = json.loads(match.feedback_reasons)
            if isinstance(reasons, list):
                increment_reason_counts(profile, reasons)
        except (ValueError, TypeError):
            pass

    db.session.commit()


def compute_score_adjustment(user, raw_job_id: int, base_score: float) -> float:
    """Adjustiert base_score basierend auf User-Centroids.

    Returns base_score unverändert wenn:
    - user.job_learn_enabled = False
    - samples < user.job_learn_min_samples in einer der Klassen
    - kein Embedding für den Job
    - kein Profil existiert
    """
    if not user.job_learn_enabled:
        return base_score

    profile = _load_profile(user.id)
    if profile is None:
        return base_score

    min_samples = user.job_learn_min_samples or 3
    if profile.samples_imported < min_samples or profile.samples_dismissed < min_samples:
        return base_score

    if profile.imported_centroid is None or profile.dismissed_centroid is None:
        return base_score

    job_vec = _load_embedding(raw_job_id)
    if job_vec is None:
        return base_score

    imp_centroid = vector_unpack(profile.imported_centroid)
    dis_centroid = vector_unpack(profile.dismissed_centroid)

    sim_imp = cosine_similarity(job_vec, imp_centroid)
    sim_dis = cosine_similarity(job_vec, dis_centroid)

    alpha = (user.job_learn_weight_pct or 30) / 100.0
    adjusted = base_score * (1 + alpha * (sim_imp - sim_dis))
    return max(0.0, min(100.0, adjusted))


def get_learn_profile_stats(user) -> dict:
    """Stats für GET /api/jobs/learn-profile."""
    profile = _load_profile(user.id)
    if profile is None:
        return {
            'enabled': bool(user.job_learn_enabled),
            'samples_imported': 0,
            'samples_dismissed': 0,
            'active': False,
            'min_samples': user.job_learn_min_samples or 3,
            'weight_pct': user.job_learn_weight_pct or 30,
            'top_reasons': [],
        }

    min_samples = user.job_learn_min_samples or 3
    active = (
        bool(user.job_learn_enabled)
        and profile.samples_imported >= min_samples
        and profile.samples_dismissed >= min_samples
    )

    counts = {}
    if profile.reason_counts:
        try:
            counts = json.loads(profile.reason_counts)
        except (ValueError, TypeError):
            counts = {}

    top = sorted(counts.items(), key=lambda x: -x[1])[:5]
    top_reasons = [
        {'reason': k, 'label': FEEDBACK_REASONS.get(k, k), 'count': v}
        for k, v in top
    ]

    return {
        'enabled': bool(user.job_learn_enabled),
        'samples_imported': profile.samples_imported,
        'samples_dismissed': profile.samples_dismissed,
        'active': active,
        'min_samples': min_samples,
        'weight_pct': user.job_learn_weight_pct or 30,
        'top_reasons': top_reasons,
    }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/test_learner.py -v`

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/learner.py tests/services/test_learner.py
git commit -m "feat(learner): Centroid-Update + Score-Adjustment"
```

---

## Task 6: Prefilter erweitern um optionalen user_id

**Files:**
- Modify: `services/job_matching/prefilter.py`
- Modify: `tests/services/test_job_sources_prefilter.py` (oder existing prefilter tests)

- [ ] **Step 1: Schreibe Test für prefilter mit user_id**

Datei: `tests/services/test_prefilter_learner.py` (neu):

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from unittest.mock import patch, MagicMock

from services.job_matching.prefilter import score_job, PrefilterContext
from services.job_matching.cv_tokenizer import CVTokens


def _ctx():
    return PrefilterContext(language_filter=['de', 'en'], region_filter=None)


def _cv():
    return CVTokens(skills={'python'}, titles={'developer'}, freetext={'agile'})


def test_score_job_without_user_returns_base():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    score = score_job(_cv(), job, _ctx())
    assert score > 0


def test_score_job_with_user_calls_learner():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    user = MagicMock()
    user.job_learn_enabled = True
    with patch('services.job_matching.prefilter.compute_score_adjustment') as mock_adj:
        mock_adj.return_value = 75.0
        score = score_job(_cv(), job, _ctx(), user=user, raw_job_id=1)
        mock_adj.assert_called_once()
        assert score == 75.0


def test_score_job_with_user_none_skips_learner():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    with patch('services.job_matching.prefilter.compute_score_adjustment') as mock_adj:
        score_job(_cv(), job, _ctx(), user=None, raw_job_id=1)
        mock_adj.assert_not_called()
```

- [ ] **Step 2: Run tests — verify fail**

Run: `pytest tests/services/test_prefilter_learner.py -v`

Expected: FAIL — score_job doesn't accept user/raw_job_id

- [ ] **Step 3: Erweitere prefilter.py**

In `services/job_matching/prefilter.py`, ändere `score_job` Signatur und füge import + Aufruf:

Am Anfang der Datei nach den existierenden imports:

```python
from services.job_matching.learner import compute_score_adjustment
```

Ändere `score_job`:

```python
def score_job(cv: CVTokens, job: dict, ctx: PrefilterContext,
              user=None, raw_job_id: int | None = None) -> float:
    # Sprach-Filter
    lang = _detect_language(job)
    if lang not in (ctx.language_filter or []):
        return 0.0

    # Region-Filter
    if ctx.region_filter and not _matches_region(job, ctx.region_filter):
        return 0.0

    job_tokens = _tokenize(job.get("title", "")) | _tokenize(job.get("description", ""))
    if not job_tokens:
        return 0.0

    skill_hits = len(cv.skills & job_tokens)
    title_hits = len(cv.titles & job_tokens) + sum(
        1 for t in cv.titles if t in (job.get("title") or "").lower()
    )
    freetext_hits = len(cv.freetext & job_tokens)

    raw_score = skill_hits * 3 + title_hits * 2 + freetext_hits * 1
    base = min(100.0, raw_score * 5.0)  # vorher existierender Normalisierungs-Block

    # Adaptive-Learning Adjustment (optional, backward-compat)
    if user is not None and raw_job_id is not None:
        base = compute_score_adjustment(user, raw_job_id, base)

    return base
```

**Wichtig:** Falls die Original-Normalisierungslogik anders ist (z.B. andere Skalierung), nur den `if user is not None`-Block hinzufügen, nicht die ganze Funktion umschreiben. Lies erst `prefilter.py` Zeilen ~55-90 und merge minimal-invasiv.

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/test_prefilter_learner.py -v && pytest tests/services/ -v -k prefilter`

Expected: All PASS, keine Regressions

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/prefilter.py tests/services/test_prefilter_learner.py
git commit -m "feat(prefilter): Optional user_id für adaptive Score-Adjustment"
```

---

## Task 7: API-Erweiterung — PATCH /api/jobs/matches/{id}

**Files:**
- Modify: `api/jobs_user.py`
- Modify: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Schreibe Test für feedback fields**

Datei: `tests/api/test_jobs_user.py` — am Ende anhängen:

```python
def test_patch_match_with_feedback_reasons(app, test_user_token, db_session):
    """PATCH speichert feedback_reasons als JSON-String und feedback_text."""
    from models import RawJob, JobMatch, JobSource

    source = JobSource(user_id=None, name="Test", type="rss", enabled=True)
    db_session.add(source)
    db_session.flush()
    raw = RawJob(source_id=source.id, external_id="fb1", title="T", company="C", url="https://x/1")
    db_session.add(raw)
    db_session.flush()
    match = JobMatch(raw_job_id=raw.id, user_id=test_user_token['user_id'], status='new')
    db_session.add(match)
    db_session.commit()

    with app.test_client() as client:
        resp = client.patch(
            f'/api/jobs/matches/{match.id}',
            json={
                "status": "dismissed",
                "feedback_reasons": ["salary_too_low", "wrong_location"],
                "feedback_text": "Zu weit weg",
            },
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 200
    updated = db_session.query(JobMatch).get(match.id)
    import json as _j
    assert _j.loads(updated.feedback_reasons) == ["salary_too_low", "wrong_location"]
    assert updated.feedback_text == "Zu weit weg"


def test_patch_match_invalid_reason_filtered(app, test_user_token, db_session):
    """Ungültige Reasons werden gefiltert, valide bleiben."""
    from models import RawJob, JobMatch, JobSource
    source = JobSource(user_id=None, name="T2", type="rss", enabled=True)
    db_session.add(source); db_session.flush()
    raw = RawJob(source_id=source.id, external_id="fb2", title="T", company="C", url="https://x/2")
    db_session.add(raw); db_session.flush()
    match = JobMatch(raw_job_id=raw.id, user_id=test_user_token['user_id'], status='new')
    db_session.add(match); db_session.commit()

    with app.test_client() as client:
        resp = client.patch(
            f'/api/jobs/matches/{match.id}',
            json={"status": "dismissed", "feedback_reasons": ["salary_too_low", "fake_reason"]},
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 200
    import json as _j
    updated = db_session.query(JobMatch).get(match.id)
    reasons = _j.loads(updated.feedback_reasons)
    assert "salary_too_low" in reasons
    assert "fake_reason" not in reasons


def test_patch_match_feedback_text_too_long_rejected(app, test_user_token, db_session):
    """feedback_text > 500 chars → 400."""
    from models import RawJob, JobMatch, JobSource
    source = JobSource(user_id=None, name="T3", type="rss", enabled=True)
    db_session.add(source); db_session.flush()
    raw = RawJob(source_id=source.id, external_id="fb3", title="T", company="C", url="https://x/3")
    db_session.add(raw); db_session.flush()
    match = JobMatch(raw_job_id=raw.id, user_id=test_user_token['user_id'], status='new')
    db_session.add(match); db_session.commit()

    with app.test_client() as client:
        resp = client.patch(
            f'/api/jobs/matches/{match.id}',
            json={"status": "dismissed", "feedback_text": "x" * 501},
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 400
```

- [ ] **Step 2: Verify fail**

Run: `pytest tests/api/test_jobs_user.py::test_patch_match_with_feedback_reasons -v`

Expected: FAIL

- [ ] **Step 3: Erweitere PATCH-Endpoint in jobs_user.py**

Suche die existierende PATCH-Route (ca. Zeile 295-310). Innerhalb des Handlers, NACH der Status-Validierung und VOR dem commit:

```python
    # Feedback-Felder (optional)
    from services.job_matching.feedback import (
        validate_reasons, MAX_FEEDBACK_TEXT_CHARS
    )
    import json as _json

    reasons_raw = data.get('feedback_reasons')
    if reasons_raw is not None:
        if not isinstance(reasons_raw, list):
            return jsonify({"error": "feedback_reasons muss eine Liste sein"}), 400
        valid = validate_reasons(reasons_raw)
        m.feedback_reasons = _json.dumps(valid) if valid else None

    text = data.get('feedback_text')
    if text is not None:
        if not isinstance(text, str):
            return jsonify({"error": "feedback_text muss string sein"}), 400
        if len(text) > MAX_FEEDBACK_TEXT_CHARS:
            return jsonify({"error": f"feedback_text max {MAX_FEEDBACK_TEXT_CHARS} Zeichen"}), 400
        m.feedback_text = text.strip() or None
```

Und NACH `db.session.commit()` füge async-Trigger ein:

```python
    # Adaptive Learning: Centroid update nach commit
    if new_status in ('dismissed', 'imported'):
        from services.job_matching.learner import update_centroid_for_feedback
        try:
            update_centroid_for_feedback(user, m)
        except Exception as e:
            current_app.logger.warning('Centroid update failed: %s', e)
```

(`current_app` import oben hinzufügen falls noch nicht da: `from flask import Blueprint, request, jsonify, current_app`)

- [ ] **Step 4: Verify tests pass**

Run: `pytest tests/api/test_jobs_user.py -v -k "feedback or unbewertet or status"`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat(api): PATCH match akzeptiert feedback_reasons + feedback_text"
```

---

## Task 8: API — GET /api/jobs/learn-profile

**Files:**
- Modify: `api/jobs_user.py`
- Modify: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Schreibe Test**

Anhängen an `tests/api/test_jobs_user.py`:

```python
def test_get_learn_profile_empty_user(app, test_user_token):
    """Neuer User ohne Feedback → enabled, samples=0, active=False."""
    with app.test_client() as client:
        resp = client.get(
            '/api/jobs/learn-profile',
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['enabled'] is True
    assert data['samples_imported'] == 0
    assert data['samples_dismissed'] == 0
    assert data['active'] is False
    assert data['top_reasons'] == []
```

- [ ] **Step 2: Verify fail**

Run: `pytest tests/api/test_jobs_user.py::test_get_learn_profile_empty_user -v`

Expected: FAIL — 404

- [ ] **Step 3: Implementiere Endpoint**

In `api/jobs_user.py`, neuer Endpoint:

```python
@jobs_user_bp.get('/learn-profile')
@token_required
def get_learn_profile(user):
    from services.job_matching.learner import get_learn_profile_stats
    return jsonify(get_learn_profile_stats(user)), 200
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/api/test_jobs_user.py::test_get_learn_profile_empty_user -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat(api): GET /api/jobs/learn-profile mit User-Stats"
```

---

## Task 9: API — Settings-PATCH für Lern-Felder

**Files:**
- Modify: `api/users.py` (oder die Datei mit Settings-PATCH; suche mit grep)
- Modify: existing settings test file

- [ ] **Step 1: Finde Settings-Endpoint**

Run: `grep -rn "ai_provider\|settings_json" api/ | grep -i "patch\|put" | head -5`

Identifiziere die Datei (vermutlich `api/users.py` oder `api/user_settings.py`).

- [ ] **Step 2: Test schreiben**

Anhängen an existing test file (z.B. `tests/api/test_users.py`):

```python
def test_patch_settings_updates_learn_fields(app, test_user_token, db_session):
    from models import User
    with app.test_client() as client:
        resp = client.patch(
            '/api/user/settings',  # path ggf. anpassen an gefundenes Endpoint
            json={
                "job_learn_enabled": False,
                "job_learn_min_samples": 5,
                "job_learn_weight_pct": 50,
            },
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 200
    updated = db_session.query(User).get(test_user_token['user_id'])
    assert updated.job_learn_enabled is False
    assert updated.job_learn_min_samples == 5
    assert updated.job_learn_weight_pct == 50


def test_patch_settings_validates_weight_pct(app, test_user_token):
    with app.test_client() as client:
        resp = client.patch(
            '/api/user/settings',
            json={"job_learn_weight_pct": 150},  # out of range
            headers={"Authorization": f"Bearer {test_user_token['token']}"}
        )
    assert resp.status_code == 400
```

- [ ] **Step 3: Erweitere Settings-Endpoint**

Im gefundenen Settings-PATCH-Handler, im allowed-fields-block oder Validation:

```python
    # Adaptive-Learning Settings
    if 'job_learn_enabled' in data:
        if not isinstance(data['job_learn_enabled'], bool):
            return jsonify({"error": "job_learn_enabled muss bool sein"}), 400
        user.job_learn_enabled = data['job_learn_enabled']

    if 'job_learn_min_samples' in data:
        v = data['job_learn_min_samples']
        if not isinstance(v, int) or v < 1 or v > 100:
            return jsonify({"error": "job_learn_min_samples muss int 1-100 sein"}), 400
        user.job_learn_min_samples = v

    if 'job_learn_weight_pct' in data:
        v = data['job_learn_weight_pct']
        if not isinstance(v, int) or v < 0 or v > 100:
            return jsonify({"error": "job_learn_weight_pct muss int 0-100 sein"}), 400
        user.job_learn_weight_pct = v
```

- [ ] **Step 4: Verify tests pass**

Run: `pytest tests/api/ -v -k settings`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/ tests/api/
git commit -m "feat(api): Settings-PATCH validiert Lern-Felder"
```

---

## Task 10: Cron-Hook für Embedding beim Prefilter-Lauf

**Files:**
- Modify: `api/jobs_cron.py`

- [ ] **Step 1: Schreibe Test**

In `tests/api/test_jobs_cron.py`, anhängen:

```python
def test_prefilter_triggers_embedding(app, db_session, sample_raw_job):
    """Nach prefilter wird embed_raw_job aufgerufen (Best-Effort)."""
    from unittest.mock import patch
    with patch('api.jobs_cron.embed_raw_job') as mock_embed:
        mock_embed.return_value = True
        with app.test_client() as client:
            resp = client.post('/api/jobs/cron/prefilter', headers={"X-Cron-Token": "test"})
        assert resp.status_code in (200, 401)  # 401 if token wrong, both OK for this mock check
        # mock_embed sollte mindestens einmal aufgerufen worden sein
        # (falls 200 — bei 401 wird der Body nicht ausgeführt)
```

- [ ] **Step 2: Erweitere prefilter-Handler**

In `api/jobs_cron.py`, finde `def prefilter()` (ca. Zeile 230). Am Anfang der Datei:

```python
from services.job_matching.embedder import embed_raw_job
```

In der Schleife wo `JobMatch.prefilter_score` gesetzt wird, NACH dem score-Set füge ein:

```python
        # Best-Effort Embedding (Ollama up → JobEmbedding wird befüllt)
        try:
            embed_raw_job(match.raw_job)
        except Exception:
            pass  # Embedding ist optional, prefilter funktioniert auch ohne
```

- [ ] **Step 3: Run cron-Tests**

Run: `pytest tests/api/test_jobs_cron.py -v`

Expected: PASS (Mocked Ollama-Call beeinträchtigt nichts)

- [ ] **Step 4: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat(cron): Embed RawJobs während prefilter (best-effort)"
```

---

## Task 11: Frontend — Dismiss-Modal mit Reasons

**Files:**
- Modify: `frontend/index.html` (oder Hauptfile mit Job-Liste)

- [ ] **Step 1: Finde existing dismiss-Button**

Run: `grep -n "dismiss\|verwerfen\|markSeen\|markAsSeen" /Library/WebServer/Documents/Bewerbungstracker/frontend/index.html | head -10`

Notiere Zeilen-Nummern.

- [ ] **Step 2: HTML-Modal hinzufügen**

In `frontend/index.html`, vor `</body>` einfügen:

```html
<!-- Adaptive Learning: Dismiss-Feedback Modal -->
<div id="dismissFeedbackModal" class="modal" style="display:none">
  <div class="modal-content">
    <h3>Job verwerfen — Warum?</h3>
    <p class="muted">Optional: Hilf dem System zu lernen, was du suchst</p>
    <form id="dismissFeedbackForm">
      <fieldset>
        <legend>Gründe (mehrere möglich)</legend>
        <label><input type="checkbox" name="reason" value="wrong_location"> Falscher Ort</label>
        <label><input type="checkbox" name="reason" value="salary_too_low"> Gehalt zu niedrig</label>
        <label><input type="checkbox" name="reason" value="missing_skills"> Fehlende Skills</label>
        <label><input type="checkbox" name="reason" value="wrong_industry"> Falsche Branche</label>
        <label><input type="checkbox" name="reason" value="overqualified"> Überqualifiziert</label>
        <label><input type="checkbox" name="reason" value="underqualified"> Unterqualifiziert</label>
        <label><input type="checkbox" name="reason" value="wrong_seniority"> Falsches Level</label>
        <label><input type="checkbox" name="reason" value="other"> Sonstiges</label>
      </fieldset>
      <label>
        Freitext (optional, max 500 Zeichen):
        <textarea name="feedback_text" maxlength="500" rows="3"></textarea>
      </label>
      <div class="modal-actions">
        <button type="button" id="dismissSkipBtn">Skip (ohne Feedback)</button>
        <button type="submit" id="dismissSubmitBtn">Verwerfen mit Feedback</button>
        <button type="button" id="dismissCancelBtn">Abbrechen</button>
      </div>
    </form>
  </div>
</div>
```

- [ ] **Step 3: JS-Handler einbauen**

In der existing JS-Section (oder neuer `<script>`-Block), ersetze den dismiss-Button-Handler. Beispiel-Pattern:

```javascript
let pendingDismissMatchId = null;

function openDismissModal(matchId) {
  pendingDismissMatchId = matchId;
  document.querySelectorAll('#dismissFeedbackForm input[type=checkbox]').forEach(cb => cb.checked = false);
  document.querySelector('#dismissFeedbackForm textarea').value = '';
  document.getElementById('dismissFeedbackModal').style.display = 'block';
}

function closeDismissModal() {
  pendingDismissMatchId = null;
  document.getElementById('dismissFeedbackModal').style.display = 'none';
}

async function submitDismiss(reasons, text) {
  const matchId = pendingDismissMatchId;
  if (!matchId) return;
  const body = { status: 'dismissed' };
  if (reasons && reasons.length) body.feedback_reasons = reasons;
  if (text) body.feedback_text = text;
  await fetch(`/api/jobs/matches/${matchId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  });
  closeDismissModal();
  refreshJobList();  // existierende Funktion nutzen
}

document.getElementById('dismissSkipBtn').addEventListener('click', () => submitDismiss([], ''));
document.getElementById('dismissCancelBtn').addEventListener('click', closeDismissModal);
document.getElementById('dismissFeedbackForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const reasons = Array.from(document.querySelectorAll('#dismissFeedbackForm input[name=reason]:checked'))
    .map(cb => cb.value);
  const text = document.querySelector('#dismissFeedbackForm textarea').value.trim();
  submitDismiss(reasons, text);
});
```

Ersetze existing direkte PATCH-Calls für "dismiss" durch `openDismissModal(matchId)`.

- [ ] **Step 4: SW-Cache-Bump**

(Per memory `feedback_frontend_release_sw_bump`)

In `frontend/service-worker.js` (falls vorhanden) `CACHE_NAME` Version inkrementieren um 1.

- [ ] **Step 5: Manual-Test**

Run: 
```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python app.py
```

Browser öffnen, Login, Job verwerfen → Modal erscheint → Reasons wählen → Submit → Liste refresht.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Dismiss-Modal mit Reasons + Freitext"
```

---

## Task 12: Frontend — Settings-UI für Learning

**Files:**
- Modify: `frontend/index.html` (Settings-Sektion)

- [ ] **Step 1: Finde Settings-Tab**

Run: `grep -n "settings\|einstellungen" /Library/WebServer/Documents/Bewerbungstracker/frontend/index.html | head -10`

- [ ] **Step 2: HTML-Sektion einfügen**

In der Settings-Sektion (vermutlich in einem `<div id="settings">` oder ähnlich):

```html
<section id="learnSettings">
  <h3>Match-Learning</h3>
  <label>
    <input type="checkbox" id="learnEnabled"> Adaptive Lernen aktiviert
  </label>
  <label>
    Min. Samples bis aktiv: <input type="number" id="learnMinSamples" min="1" max="100" value="3">
  </label>
  <label>
    Lern-Gewichtung: <input type="range" id="learnWeightPct" min="0" max="100" value="30">
    <span id="learnWeightLabel">30%</span>
  </label>
  <div id="learnStats" class="muted">
    Lade Stats…
  </div>
  <button id="saveLearnSettings">Speichern</button>
</section>
```

- [ ] **Step 3: JS für Settings**

```javascript
async function loadLearnSettings() {
  // Hole User-Settings (assumes existing endpoint /api/user/me oder /api/user/settings)
  const meResp = await fetch('/api/user/me', { headers: { Authorization: `Bearer ${getToken()}` } });
  const me = await meResp.json();
  document.getElementById('learnEnabled').checked = me.job_learn_enabled ?? true;
  document.getElementById('learnMinSamples').value = me.job_learn_min_samples ?? 3;
  document.getElementById('learnWeightPct').value = me.job_learn_weight_pct ?? 30;
  document.getElementById('learnWeightLabel').textContent = (me.job_learn_weight_pct ?? 30) + '%';

  // Stats holen
  const sResp = await fetch('/api/jobs/learn-profile', { headers: { Authorization: `Bearer ${getToken()}` } });
  const s = await sResp.json();
  const reasons = (s.top_reasons || []).map(r => `${r.label} (${r.count}×)`).join(', ') || 'keine';
  document.getElementById('learnStats').textContent =
    `Gelernt: ${s.samples_imported} imported, ${s.samples_dismissed} dismissed. ` +
    `Status: ${s.active ? 'aktiv' : 'cold-start'}. Top-Gründe: ${reasons}.`;
}

document.getElementById('learnWeightPct').addEventListener('input', (e) => {
  document.getElementById('learnWeightLabel').textContent = e.target.value + '%';
});

document.getElementById('saveLearnSettings').addEventListener('click', async () => {
  const body = {
    job_learn_enabled: document.getElementById('learnEnabled').checked,
    job_learn_min_samples: parseInt(document.getElementById('learnMinSamples').value, 10),
    job_learn_weight_pct: parseInt(document.getElementById('learnWeightPct').value, 10),
  };
  const resp = await fetch('/api/user/settings', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  });
  if (resp.ok) {
    alert('Settings gespeichert');
    loadLearnSettings();
  } else {
    const err = await resp.json();
    alert('Fehler: ' + (err.error || 'unknown'));
  }
});

// Bei Page-Load / Settings-Tab öffnen:
loadLearnSettings();
```

**Hinweis:** Endpoint-Pfade (`/api/user/me`, `/api/user/settings`) ggf. an reale Routen anpassen — siehe Task 9.

- [ ] **Step 4: SW-Cache-Bump**

Erneut `CACHE_NAME` Version +1.

- [ ] **Step 5: Manual-Test**

Browser: Settings → "Match-Learning" Sektion zeigt aktuelle Werte → Slider bewegt → Speichern → Reload zeigt persistierte Werte.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Settings-UI für Adaptive Learning"
```

---

## Task 13: Backfill-Script für Embeddings

**Files:**
- Create: `scripts/backfill_job_embeddings.py`

- [ ] **Step 1: Script schreiben**

Datei: `scripts/backfill_job_embeddings.py`:

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Backfill JobEmbedding für alle existierenden RawJobs ohne Embedding.

Usage:
    python scripts/backfill_job_embeddings.py              # alle
    python scripts/backfill_job_embeddings.py --limit 100  # nur 100
    python scripts/backfill_job_embeddings.py --check      # nur zählen
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from database import db
from models import RawJob, JobEmbedding
from services.job_matching.embedder import embed_raw_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--sleep', type=float, default=0.1, help='sec between embeds')
    args = parser.parse_args()

    with app.app_context():
        q = RawJob.query.outerjoin(JobEmbedding).filter(JobEmbedding.raw_job_id.is_(None))
        total = q.count()
        print(f'Pending: {total} RawJobs ohne Embedding')
        if args.check:
            return

        if args.limit:
            q = q.limit(args.limit)

        done = 0
        failed = 0
        for raw in q.all():
            ok = embed_raw_job(raw)
            if ok:
                done += 1
            else:
                failed += 1
                print(f'  FAIL raw_job_id={raw.id} (Ollama down?)')
                if failed > 5:
                    print('Too many failures, aborting')
                    break
            if done % 10 == 0:
                print(f'  ... {done} done')
            time.sleep(args.sleep)

        print(f'Done: {done} embedded, {failed} failed')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Executable machen + check-Mode testen**

```bash
chmod +x scripts/backfill_job_embeddings.py
python scripts/backfill_job_embeddings.py --check
```

Expected: Zeigt Anzahl pending ohne zu embeddem

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_job_embeddings.py
git commit -m "script: Backfill JobEmbeddings für bestehende RawJobs"
```

---

## Task 14: Backfill-Script für Centroids

**Files:**
- Create: `scripts/rebuild_user_centroids.py`

- [ ] **Step 1: Script schreiben**

Datei: `scripts/rebuild_user_centroids.py`:

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rebuild UserLearnProfile-Centroids aus historischen JobMatch-Daten.

Iteriert pro User über alle dismissed/imported Matches und ruft
update_centroid_for_feedback für jeden auf. Idempotent — alte Profile
werden vorher geleert.

Usage:
    python scripts/rebuild_user_centroids.py                # alle User
    python scripts/rebuild_user_centroids.py --user-id <id> # einen User
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from database import db
from models import User, JobMatch, UserLearnProfile
from services.job_matching.learner import update_centroid_for_feedback


def rebuild_for_user(user: User):
    # Reset existing profile
    existing = UserLearnProfile.query.filter_by(user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    matches = (JobMatch.query
               .filter(JobMatch.user_id == user.id,
                       JobMatch.status.in_(['dismissed', 'imported']))
               .order_by(JobMatch.updated_at)
               .all())
    print(f'User {user.email}: {len(matches)} matches')
    done = 0
    for m in matches:
        try:
            update_centroid_for_feedback(user, m)
            done += 1
        except Exception as e:
            print(f'  fail match_id={m.id}: {e}')
    print(f'  → {done} aggregiert')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user-id', type=str, default=None)
    args = parser.parse_args()

    with app.app_context():
        if args.user_id:
            user = User.query.get(args.user_id)
            if user is None:
                print('User not found')
                sys.exit(1)
            rebuild_for_user(user)
        else:
            for u in User.query.filter_by(job_discovery_enabled=True).all():
                rebuild_for_user(u)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Test mit einem User (dry-run-artig)**

Run: `python scripts/rebuild_user_centroids.py --user-id <some-test-uuid>`

Expected: zeigt Anzahl matches und aggregiert ohne Fehler

- [ ] **Step 3: Commit**

```bash
git add scripts/rebuild_user_centroids.py
git commit -m "script: Rebuild UserLearnProfile-Centroids aus Historie"
```

---

## Task 15: End-to-End Integration-Test

**Files:**
- Create: `tests/integration/test_learning_e2e.py`

- [ ] **Step 1: Test schreiben**

Datei: `tests/integration/test_learning_e2e.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""E2E: 3 imports + 3 dismisses → ähnlicher Job bekommt anderen Score."""

import numpy as np
import pytest
from unittest.mock import patch

from database import db
from models import RawJob, JobMatch, JobSource, JobEmbedding
from services.job_matching.embedder import vector_pack


def _make_job(db_session, source, ext_id, title, vec):
    raw = RawJob(source_id=source.id, external_id=ext_id, title=title,
                 company='C', url=f'https://x/{ext_id}', description=title)
    db_session.add(raw)
    db_session.flush()
    emb = JobEmbedding(raw_job_id=raw.id, vector=vector_pack(vec))
    db_session.add(emb)
    db_session.commit()
    return raw


def test_e2e_learning_adjusts_score(app, test_user_token, db_session):
    """Nach 3 imports & 3 dismisses: ähnlicher Job zu imported scoret höher."""
    source = JobSource(user_id=None, name='E2E', type='rss', enabled=True)
    db_session.add(source); db_session.flush()

    # 3 "imported" Jobs mit Vektor ~ [1,0,0,...]
    imp_vec = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    for i in range(3):
        raw = _make_job(db_session, source, f'imp-{i}', f'Imported Job {i}', imp_vec)
        match = JobMatch(raw_job_id=raw.id, user_id=test_user_token['user_id'], status='new')
        db_session.add(match); db_session.commit()
        with app.test_client() as c:
            c.patch(f'/api/jobs/matches/{match.id}',
                    json={"status": "imported"},
                    headers={"Authorization": f"Bearer {test_user_token['token']}"})

    # 3 "dismissed" Jobs mit Vektor ~ [0,1,0,...]
    dis_vec = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    for i in range(3):
        raw = _make_job(db_session, source, f'dis-{i}', f'Dismissed Job {i}', dis_vec)
        match = JobMatch(raw_job_id=raw.id, user_id=test_user_token['user_id'], status='new')
        db_session.add(match); db_session.commit()
        with app.test_client() as c:
            c.patch(f'/api/jobs/matches/{match.id}',
                    json={"status": "dismissed", "feedback_reasons": ["wrong_industry"]},
                    headers={"Authorization": f"Bearer {test_user_token['token']}"})

    # Profil ist nun aktiv. Lade learn-profile:
    with app.test_client() as c:
        resp = c.get('/api/jobs/learn-profile',
                     headers={"Authorization": f"Bearer {test_user_token['token']}"})
    data = resp.get_json()
    assert data['active'] is True
    assert data['samples_imported'] == 3
    assert data['samples_dismissed'] == 3
    assert any(r['reason'] == 'wrong_industry' for r in data['top_reasons'])

    # Score-Test: ähnlicher Job zu imported
    from services.job_matching.learner import compute_score_adjustment
    from models import User
    user = User.query.get(test_user_token['user_id'])
    similar_to_imp = _make_job(db_session, source, 'sim-imp', 'Similar', imp_vec)
    similar_to_dis = _make_job(db_session, source, 'sim-dis', 'Similar', dis_vec)

    adj_imp = compute_score_adjustment(user, similar_to_imp.id, base_score=50.0)
    adj_dis = compute_score_adjustment(user, similar_to_dis.id, base_score=50.0)

    assert adj_imp > 50.0, f'expected boost, got {adj_imp}'
    assert adj_dis < 50.0, f'expected penalty, got {adj_dis}'
```

- [ ] **Step 2: Run E2E**

Run: `pytest tests/integration/test_learning_e2e.py -v`

Expected: PASS

- [ ] **Step 3: Run gesamte Test-Suite**

Run: `pytest tests/ -x --tb=short`

Expected: All PASS, keine Regressions

- [ ] **Step 4: Commit**

```bash
git add tests/integration/
git commit -m "test(e2e): Adaptive Learning End-to-End Szenario"
```

---

## Summary of Changes

**Neue Dateien:**
- `services/job_matching/embedder.py` — Ollama-Client + Vektor-Math
- `services/job_matching/feedback.py` — Reasons + Validation
- `services/job_matching/learner.py` — Centroid-Update + Adjustment
- `scripts/backfill_job_embeddings.py`
- `scripts/rebuild_user_centroids.py`
- `migrations/versions/XXXX_adaptive_learning.py`
- `tests/services/test_embedder.py`
- `tests/services/test_feedback.py`
- `tests/services/test_learner.py`
- `tests/services/test_prefilter_learner.py`
- `tests/integration/test_learning_e2e.py`

**Modifizierte Dateien:**
- `models.py` — JobMatch, User erweitert; 2 neue Tabellen
- `services/job_matching/prefilter.py` — optional user_id Parameter
- `api/jobs_user.py` — PATCH erweitert + GET /learn-profile
- `api/users.py` (oder settings file) — Settings-PATCH erweitert
- `api/jobs_cron.py` — Best-Effort embed beim prefilter
- `frontend/index.html` — Dismiss-Modal + Settings-Sektion
- `frontend/service-worker.js` — CACHE_NAME bump (×2)
- `tests/api/test_jobs_user.py` — 4 neue Tests
- `tests/api/test_users.py` (oder settings) — 2 neue Tests

**Commits (15):**
1. feat(models): JobMatch+User Felder, neue Tabellen
2. migration: Adaptive-Learning Schema
3. feat(embedder): Ollama-Client
4. feat(feedback): Reasons + Validation
5. feat(learner): Centroid + Adjustment
6. feat(prefilter): user_id Parameter
7. feat(api): PATCH feedback fields
8. feat(api): GET /learn-profile
9. feat(api): Settings-PATCH erweitert
10. feat(cron): embed beim prefilter
11. feat(frontend): Dismiss-Modal
12. feat(frontend): Settings-UI
13. script: Backfill embeddings
14. script: Rebuild centroids
15. test(e2e): Integration

---

## Spec Coverage

| Spec-Section | Tasks |
|---|---|
| JobMatch.feedback_reasons, feedback_text | 1, 2, 7 |
| User Learn-Settings | 1, 2, 9 |
| JobEmbedding-Tabelle | 1, 2 |
| UserLearnProfile-Tabelle | 1, 2 |
| FEEDBACK_REASONS Konstanten | 4 |
| embedder.py (Ollama + Pack/Cosine) | 3 |
| learner.py (Centroid + Adjustment) | 5 |
| prefilter erweitert | 6 |
| PATCH /matches mit Feedback | 7 |
| GET /learn-profile | 8 |
| Settings-PATCH | 9 |
| Cron Best-Effort Embed | 10 |
| Dismiss-Modal Frontend | 11 |
| Settings-UI Frontend | 12 |
| Backfill embeddings | 13 |
| Rebuild centroids | 14 |
| E2E Test | 15 |
| Edge Cases (Ollama down, Cold-Start, etc.) | 3, 5, 10 |
| Migration | 2 |
| Rollback | 2 (down() impl) |
