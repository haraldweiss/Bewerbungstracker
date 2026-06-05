# Quick-Reasons-UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dismiss-Feedback-Modal um 4 Quick-Action-Buttons mit echter DB-Folgewirkung erweitern (Firma abgelehnt → Application(absage), Schon beworben → Application(beworben), Stelle weg → Marker, Falscher Job-Typ → User-Setting-Blacklist) inklusive Prefilter-Integration und Settings-UI.

**Architecture:** Backend-PATCH `/api/jobs/matches/<id>` bekommt neue Felder `quick_action` + `job_type`. Folgeaktionen in derselben Transaktion (idempotent). Job-Typ-Erkennung als reine Funktion `detect_job_type()` im Prefilter-Modul, in `cron_prefilter`-Handler vor dem Score-Check integriert. Neues User-Feld `job_type_blacklist` (TEXT, JSON-Array). Frontend: bestehendes Modal in `index.html` um Aktion-Block oben + einklappbare Lern-Reasons unten, Settings-Sektion im Profil-Tab.

**Tech Stack:** Python 3.12 + Flask + SQLAlchemy + Alembic, vanilla JS im Frontend, pytest. Test-DB ist in-memory SQLite via `tests/conftest.py::app`-Fixture.

**Spec:** [`docs/superpowers/specs/2026-06-05-quick-reasons-ui-design.md`](../specs/2026-06-05-quick-reasons-ui-design.md)

**Pre-flight (alle Tasks):**
- Branch: `claude/modest-goldberg-c98a13` (bereits aktiv) oder neuen Branch von `master` erstellen
- Git-Identity: `git config user.email` muss `harald.weiss@wolfinisoftware.de` sein (siehe AGENTS.md §0)
- Alembic-Head aktuell: `f0778653c386` (= prod head, verifiziert via `sqlite3 .../bewerbungstracker.db "SELECT version_num FROM alembic_version;"`)
- Tests laufen via `python3 -m pytest …` (lokal: `python` ist nicht im PATH)
- Lokal fehlende Module: `jsonschema` (betrifft nur pattern-learner-Tests, irrelevant für diesen Plan)

---

## File Structure

| Datei | Status | Verantwortung |
|---|---|---|
| `alembic/versions/20260605_1200_add_user_job_type_blacklist.py` | **Neu** | Migration: User-Spalte hinzufügen |
| `models.py` | **Ändern** (User-Klasse, ~Z. 169) | SQLAlchemy-Mapping für neue Spalte |
| `services/job_matching/prefilter.py` | **Ändern** (~Z. 27 nach Konstanten) | Reine Funktion `detect_job_type(title)` |
| `tests/services/test_prefilter.py` | **Ändern** | Unit-Tests für `detect_job_type` |
| `services/tasks/handlers/cron_prefilter.py` | **Ändern** (~Z. 112) | Job-Typ-Check im Prefilter-Loop |
| `tests/services/tasks/test_handler_cron_prefilter_job_type.py` | **Neu** | Handler-Test mit Blacklist |
| `api/jobs_user.py` | **Ändern** (PATCH `/matches/<id>`, ~Z. 542) | `quick_action` + Folgeaktionen |
| `services/job_matching/quick_actions.py` | **Neu** | Folgeaktions-Logik (Application-CRUD) — gekapselt für Testbarkeit |
| `tests/api/test_quick_actions.py` | **Neu** | Backend-Integration-Tests |
| `api/profile.py` | **Ändern** (~Z. 158 GET, ~Z. 178 PATCH) | `job_type_blacklist` in GET + PATCH |
| `tests/api/test_profile_job_type_blacklist.py` | **Neu** | Profile-Endpoint-Tests |
| `index.html` | **Ändern** (~Z. 12000 Modal HTML, ~Z. 12042 Modal-JS, Profil-Tab) | Quick-Action-Buttons + Settings-Checkboxes |

**Rationale**: `services/job_matching/quick_actions.py` als neues Modul kapselt die DB-Folgeaktionen — sauberer als die ~80 LoC direkt in `api/jobs_user.py::update_match` zu kippen. Spec §3 (Hard-Rule "services/ ist source of truth").

---

## Task 1: Alembic-Migration + Model-Spalte für `job_type_blacklist`

**Files:**
- Create: `alembic/versions/20260605_1200_add_user_job_type_blacklist.py`
- Modify: `models.py:169` (User-Klasse — Spalte ergänzen)
- Test: `tests/test_models.py` (falls existiert; sonst nur via Migration-Run verifizieren)

- [ ] **Step 1: Migration-Datei anlegen**

`alembic/versions/20260605_1200_add_user_job_type_blacklist.py`:
```python
"""add User.job_type_blacklist

Revision ID: a9b8c7d6e5f4
Revises: f0778653c386
Create Date: 2026-06-05 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'a9b8c7d6e5f4'
down_revision = 'f0778653c386'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column(
            'job_type_blacklist',
            sa.Text(),
            nullable=False,
            server_default="'[]'",
        ),
    )


def downgrade():
    op.drop_column('users', 'job_type_blacklist')
```

- [ ] **Step 2: Spalte im SQLAlchemy-Model ergänzen**

In `models.py`, in der `User`-Klasse (nach `job_learn_weight_pct`, der letzten existierenden Spalte):
```python
    job_type_blacklist = db.Column(db.Text, nullable=False, default='[]',
                                    server_default="'[]'")
```

- [ ] **Step 3: Migration anwenden lokal verifizieren**

```bash
alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade f0778653c386 -> a9b8c7d6e5f4, add User.job_type_blacklist`

Falls Fehler "alembic not found": `python3 -m alembic upgrade head`.

- [ ] **Step 4: Sanity-Test schreiben + ausführen**

`tests/test_user_job_type_blacklist.py` (neu, kurz):
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Sanity: neue User-Spalte job_type_blacklist hat Default '[]'."""
from models import User
from database import db


def test_user_default_job_type_blacklist_is_empty_array(app, user_factory):
    with app.app_context():
        u = user_factory()
        db.session.refresh(u)
        assert u.job_type_blacklist == '[]'
```

Run: `python3 -m pytest tests/test_user_job_type_blacklist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/20260605_1200_add_user_job_type_blacklist.py \
        models.py \
        tests/test_user_job_type_blacklist.py
git commit -m "$(cat <<'EOF'
Add: Alembic migration — User.job_type_blacklist

Neue Spalte fuer Quick-Reasons-UI (Phase 1, Spec
docs/superpowers/specs/2026-06-05-quick-reasons-ui-design.md).
TEXT, NOT NULL, Default '[]' (JSON-Array-String mit Werten aus
{'werkstudent','freelance','temp_agency'}).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Reine Funktion `detect_job_type()` + Unit-Tests

**Files:**
- Modify: `services/job_matching/prefilter.py:27` (neue Konstante + Funktion am Ende des Top-Level-Blocks, vor `score_job`)
- Modify: `tests/services/test_prefilter.py` (Tests ergänzen)

- [ ] **Step 1: Tests schreiben (TDD)**

In `tests/services/test_prefilter.py` (am Ende anhängen):
```python
from services.job_matching.prefilter import detect_job_type


def test_detect_job_type_werkstudent():
    assert detect_job_type("Werkstudent IT-Support (m/w/d)") == "werkstudent"
    assert detect_job_type("Werkstudentin Data") == "werkstudent"
    assert detect_job_type("Werkstudierende Cloud") == "werkstudent"


def test_detect_job_type_freelance():
    assert detect_job_type("Freelancer Kundenberater") == "freelance"
    assert detect_job_type("Senior Engineer (freiberuflich)") == "freelance"
    assert detect_job_type("Freiberufler Backend") == "freelance"


def test_detect_job_type_temp_agency_full_word():
    assert detect_job_type("IT-Support via Arbeitnehmerüberlassung") == "temp_agency"
    assert detect_job_type("Zeitarbeit Logistik") == "temp_agency"
    assert detect_job_type("Leiharbeit Kundenservice") == "temp_agency"


def test_detect_job_type_au_only_as_standalone_word():
    # Positivfall: "AÜ" als eigenes Wort
    assert detect_job_type("Senior Engineer (AÜ)") == "temp_agency"
    # Negativfall: "AÜ" als Substring darf NICHT matchen
    assert detect_job_type("Bautätigkeit prüfen") is None
    assert detect_job_type("Genauigkeit zählt") is None


def test_detect_job_type_returns_none_for_normal_title():
    assert detect_job_type("Senior Cyber Security Analyst (m/w/d)") is None
    assert detect_job_type("DevOps Engineer Berlin") is None


def test_detect_job_type_handles_none_and_empty():
    assert detect_job_type(None) is None
    assert detect_job_type("") is None
    assert detect_job_type("   ") is None


def test_detect_job_type_case_insensitive():
    assert detect_job_type("WERKSTUDENT") == "werkstudent"
    assert detect_job_type("FreElAnCeR") == "freelance"
```

- [ ] **Step 2: Tests ausführen (rot)**

```bash
python3 -m pytest tests/services/test_prefilter.py -v -k detect_job_type
```
Expected: 7 FAILED mit `ImportError: cannot import name 'detect_job_type'`

- [ ] **Step 3: Implementierung**

In `services/job_matching/prefilter.py`, nach Zeile 27 (nach den Top-Level-Regex-Konstanten):
```python
# Quick-Reasons-Phase-1: Job-Typ-Detection für User.job_type_blacklist.
# Reihenfolge der Keys = Match-Priorität (erster Hit gewinnt).
# Keywords case-insensitive, Word-Boundary via re.search r'\b...\b'.
_JOB_TYPE_PATTERNS = [
    ('werkstudent', re.compile(
        r'\b(?:werkstudent|werkstudentin|werkstudierende)\b',
        re.IGNORECASE,
    )),
    ('freelance', re.compile(
        r'\b(?:freelancer|freelance|freiberuflich|freiberufler|'
        r'selbstständig|auf rechnung)\b',
        re.IGNORECASE,
    )),
    ('temp_agency', re.compile(
        r'\b(?:arbeitnehmerüberlassung|aü|leiharbeit|zeitarbeit)\b',
        re.IGNORECASE,
    )),
]


def detect_job_type(title: str | None) -> str | None:
    """Liefert ersten Hit ∈ {'werkstudent','freelance','temp_agency'} oder None.

    Word-Boundary-Match (re.IGNORECASE). "AÜ" matcht nur als eigenständiges
    Wort, nicht als Substring von "Bautätigkeit" o.Ä.
    """
    if not title or not title.strip():
        return None
    for label, pattern in _JOB_TYPE_PATTERNS:
        if pattern.search(title):
            return label
    return None
```

- [ ] **Step 4: Tests ausführen (grün)**

```bash
python3 -m pytest tests/services/test_prefilter.py -v -k detect_job_type
```
Expected: 7 PASSED

- [ ] **Step 5: Vollständige Prefilter-Tests laufen lassen (Regression)**

```bash
python3 -m pytest tests/services/test_prefilter.py -v
```
Expected: alle bisherigen + 7 neue PASSED

- [ ] **Step 6: Commit**

```bash
git add services/job_matching/prefilter.py tests/services/test_prefilter.py
git commit -m "$(cat <<'EOF'
Add: detect_job_type() — Werkstudent/Freelancer/Arbeitnehmerueberlassung

Reine Funktion fuer Job-Typ-Erkennung aus Title. Word-Boundary-Match,
case-insensitive. 'AUe' nur als alleinstehendes Wort (verhindert Substring-
Match auf "Bautaetigkeit" o.Ae.).

Wird in Task 3 vom cron_prefilter-Handler genutzt, um User-spezifische
Job-Typ-Blacklist auszuwerten.

7 Unit-Tests, alle Pfade: jeder Typ + None/empty + case-insensitive + AUe-
Standalone-Word-Edge-Case.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `cron_prefilter`-Integration für Job-Typ-Blacklist

**Files:**
- Modify: `services/tasks/handlers/cron_prefilter.py` (Import + Logik im Loop)
- Create: `tests/services/tasks/test_handler_cron_prefilter_job_type.py`

- [ ] **Step 1: Test schreiben (TDD)**

`tests/services/tasks/test_handler_cron_prefilter_job_type.py`:
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cron-Prefilter dismissed Matches, deren Job-Typ in User-Blacklist steht."""
import json
import pytest
from datetime import datetime

from database import db
from models import User, RawJob, JobMatch, JobSource


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from app import create_app
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_source(user):
    src = JobSource(
        user_id=user.id, name='test-src', type='manual',
        config_json='{}', enabled=True,
    )
    db.session.add(src)
    db.session.commit()
    return src


def _make_match(user, src, title, company='Acme'):
    raw = RawJob(
        source_id=src.id, external_id=f'ext-{title}',
        title=title, company=company, url=f'https://x.test/{title}',
        description='lorem ipsum',
    )
    db.session.add(raw)
    db.session.commit()
    m = JobMatch(
        user_id=user.id, raw_job_id=raw.id, status='new',
        prefilter_score=None,
    )
    db.session.add(m)
    db.session.commit()
    return m


def test_prefilter_dismisses_blacklisted_job_type(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist=json.dumps(['werkstudent']),
            cv_data_json=json.dumps({'cv': {'skills': ['python'], 'summary': ''}}),
        )
        src = _make_source(user)
        m = _make_match(user, src, 'Werkstudent IT-Support')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        result = handle_cron_prefilter({})

        db.session.refresh(m)
        assert m.status == 'dismissed'
        assert m.feedback_text == 'wrong_job_type_blocked'
        assert result['dismissed'] >= 1


def test_prefilter_keeps_non_blacklisted_job_type(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist=json.dumps(['werkstudent']),
            cv_data_json=json.dumps({
                'cv': {'skills': ['python', 'security'],
                       'summary': 'security analyst'}
            }),
        )
        src = _make_source(user)
        # Normal job title — should NOT be blocked
        m = _make_match(user, src, 'Senior Security Analyst (m/w/d)')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        handle_cron_prefilter({})

        db.session.refresh(m)
        # Either remains 'new' (score >= threshold) or 'dismissed' for other
        # reason, but feedback_text must NOT be wrong_job_type_blocked.
        assert m.feedback_text != 'wrong_job_type_blocked'


def test_prefilter_skips_check_when_blacklist_empty(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist='[]',
            cv_data_json=json.dumps({
                'cv': {'skills': ['python'], 'summary': ''}
            }),
        )
        src = _make_source(user)
        m = _make_match(user, src, 'Werkstudent IT-Support')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        handle_cron_prefilter({})

        db.session.refresh(m)
        # Mit leerer Blacklist darf der Werkstudent-Block NICHT greifen.
        assert m.feedback_text != 'wrong_job_type_blocked'
```

- [ ] **Step 2: Tests ausführen (rot)**

```bash
python3 -m pytest tests/services/tasks/test_handler_cron_prefilter_job_type.py -v
```
Expected: 3 FAILED — entweder weil `feedback_text == 'wrong_job_type_blocked'` nicht gesetzt wird, oder weil `m.status` nicht `dismissed` ist im positiven Fall.

- [ ] **Step 3: Implementierung in `cron_prefilter.py`**

In `services/tasks/handlers/cron_prefilter.py`:

(a) Import oben ergänzen (im import-Block am Anfang von `handle_cron_prefilter`, dort wo schon `from services.job_matching.prefilter import score_job, PrefilterContext` steht):
```python
    from services.job_matching.prefilter import score_job, PrefilterContext, detect_job_type
```

(b) In der `cv_cache`-Initialisierung den `job_type_blacklist` mit-cachen:
```python
    job_type_blacklist_cache: dict = {}
```
… und in der `if match.user_id not in cv_cache:`-Block:
```python
            import json as _json
            try:
                job_type_blacklist_cache[match.user_id] = set(_json.loads(user.job_type_blacklist or '[]'))
            except (ValueError, TypeError):
                job_type_blacklist_cache[match.user_id] = set()
```

(c) Im Match-Loop, NACH dem `is_rejected_company`-Block (~Z. 113), VOR dem `is_duplicate`-Block, einfügen:
```python
        blacklist = job_type_blacklist_cache.get(match.user_id, set())
        is_blacklisted_job_type = False
        if blacklist:
            detected = detect_job_type(raw.title)
            if detected and detected in blacklist:
                is_blacklisted_job_type = True
```

(d) Im Entscheidungsbaum (`if is_rejected_company: ... elif is_duplicate: ... elif score < ...:`) einen Zweig ergänzen NACH `is_rejected_company` und VOR `is_duplicate`:
```python
        if is_rejected_company:
            ...
        elif is_blacklisted_job_type:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'wrong_job_type_blocked'
            dismissed += 1
        elif is_duplicate:
            ...
```

(e) Optional: im return-dict eine neue Zählung `wrong_job_type_dismissed: int` ergänzen (analog `rejected_company_dismissed`). Wenn ergänzt, oben Counter `wrong_job_type_dismissed = 0` initialisieren und im Branch hochzählen.

- [ ] **Step 4: Tests ausführen (grün)**

```bash
python3 -m pytest tests/services/tasks/test_handler_cron_prefilter_job_type.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Regression — bestehende Prefilter-Tests**

```bash
python3 -m pytest tests/services/tasks/ tests/services/test_prefilter.py tests/services/test_prefilter_learner.py -v
```
Expected: alle PASSED (24 vorher + neue)

- [ ] **Step 6: Commit**

```bash
git add services/tasks/handlers/cron_prefilter.py \
        tests/services/tasks/test_handler_cron_prefilter_job_type.py
git commit -m "$(cat <<'EOF'
Add: cron_prefilter respektiert User.job_type_blacklist

Vor dem Score-Check: detect_job_type(raw.title) gegen den User-Blacklist-Set
checken. Bei Match: status='dismissed', feedback_text='wrong_job_type_blocked'.

Reihenfolge im Entscheidungsbaum: rejected_company > wrong_job_type >
duplicate > low_score. wrong_job_type ist billig (Regex) und blockiert
trivial-falsche Stellen vor den teureren Checks.

Cached die Blacklist pro user_id im Tick (analog rejected_companies_cache).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Backend — `quick_actions`-Modul + Folgeaktionen

**Files:**
- Create: `services/job_matching/quick_actions.py`
- Create: `tests/services/test_quick_actions.py`

Diesen Task isoliert von der HTTP-Schicht halten (Spec §3 — services/ ist source of truth). Task 5 verdrahtet das Modul dann mit dem PATCH-Endpoint.

- [ ] **Step 1: Tests schreiben (TDD)**

`tests/services/test_quick_actions.py`:
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests fuer apply_quick_action() — DB-Folgeaktionen."""
import json
from datetime import datetime, date

import pytest
from database import db
from models import User, RawJob, JobMatch, JobSource, Application


@pytest.fixture
def setup(app, user_factory):
    with app.app_context():
        user = user_factory()
        src = JobSource(
            user_id=user.id, name='t', type='manual',
            config_json='{}', enabled=True,
        )
        db.session.add(src)
        db.session.commit()
        raw = RawJob(
            source_id=src.id, external_id='e1',
            title='Senior Security Analyst', company='Signal Iduna Group AG',
            url='https://x.test/1', description='d',
        )
        db.session.add(raw)
        db.session.commit()
        m = JobMatch(user_id=user.id, raw_job_id=raw.id, status='new')
        db.session.add(m)
        db.session.commit()
        yield (user, raw, m)


def test_company_rejected_creates_application(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='company_rejected')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        a = apps[0]
        assert a.company == 'Signal Iduna Group AG'
        assert a.position == 'Senior Security Analyst'
        assert a.status == 'absage'
        assert a.applied_date is None


def test_company_rejected_idempotent_upgrades_existing_to_absage(app, setup):
    user, raw, m = setup
    with app.app_context():
        # Bestehende Application im Status 'beworben'
        existing = Application(
            user_id=user.id, company='signal iduna group ag',
            position='senior security analyst', status='beworben',
            applied_date=date.today(),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='company_rejected')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1, "kein duplicate insert"
        assert apps[0].status == 'absage'


def test_company_rejected_does_not_downgrade_zusage(app, setup):
    user, raw, m = setup
    with app.app_context():
        existing = Application(
            user_id=user.id, company='Signal Iduna Group AG',
            position='Senior Security Analyst', status='zusage',
            applied_date=date.today(),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='company_rejected')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'zusage', "absage darf zusage NICHT ueberschreiben"


def test_already_applied_creates_application_with_today(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='already_applied')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'beworben'
        assert apps[0].applied_date == date.today()


def test_already_applied_idempotent_skips_existing(app, setup):
    user, raw, m = setup
    with app.app_context():
        existing = Application(
            user_id=user.id, company='Signal Iduna Group AG',
            position='Senior Security Analyst', status='interview',
            applied_date=date(2026, 1, 1),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='already_applied')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'interview', "kein Status-Downgrade"
        assert apps[0].applied_date == date(2026, 1, 1)


def test_job_unavailable_creates_no_application(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='job_unavailable')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert apps == []


def test_wrong_job_type_appends_to_user_blacklist(app, setup):
    user, raw, m = setup
    with app.app_context():
        assert json.loads(user.job_type_blacklist) == []
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='werkstudent')
        db.session.refresh(user)
        assert json.loads(user.job_type_blacklist) == ['werkstudent']


def test_wrong_job_type_idempotent(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='freelance')
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='freelance')
        db.session.refresh(user)
        assert json.loads(user.job_type_blacklist) == ['freelance']


def test_company_rejected_raises_on_empty_company(app, setup):
    user, raw, m = setup
    with app.app_context():
        raw.company = ''
        db.session.commit()
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='company_rejected')


def test_wrong_job_type_raises_on_missing_job_type(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='wrong_job_type', job_type=None)


def test_unknown_action_raises(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='not_a_real_action')
```

- [ ] **Step 2: Tests ausführen (rot)**

```bash
python3 -m pytest tests/services/test_quick_actions.py -v
```
Expected: 11 FAILED mit `ImportError: cannot import name 'apply_quick_action'`.

- [ ] **Step 3: Implementierung**

`services/job_matching/quick_actions.py`:
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Quick-Action-Folgeaktionen aus dem Dismiss-Feedback-Modal.

Siehe Spec docs/superpowers/specs/2026-06-05-quick-reasons-ui-design.md §3.
Caller (api/jobs_user.py PATCH /matches/<id>) ist HTTP-Schicht; diese Datei
kapselt nur die DB-Folgeaktionen und ist damit isoliert testbar.
"""
from __future__ import annotations

import json
from datetime import date

from database import db
from models import User, RawJob, JobMatch, Application


VALID_ACTIONS = frozenset({
    'company_rejected', 'already_applied', 'job_unavailable', 'wrong_job_type',
})
VALID_JOB_TYPES = frozenset({'werkstudent', 'freelance', 'temp_agency'})

# Pro Quick-Action der system-feedback_text-Code, den der Caller setzt.
FEEDBACK_TEXT_BY_ACTION = {
    'company_rejected': 'quick_action_company_rejected',
    'already_applied': 'quick_action_already_applied',
    'job_unavailable': 'job_no_longer_available',
    'wrong_job_type': 'wrong_job_type_blocked',
}

# Stati, die NICHT von company_rejected ueberschrieben werden duerfen.
_PROTECTED_STATUSES = frozenset({'absage', 'rejected', 'ghosting', 'zusage', 'offer'})


class QuickActionError(ValueError):
    """Validierungsfehler — wird vom Caller als 400 abgebildet."""


def apply_quick_action(*, user: User, match: JobMatch, raw: RawJob,
                       action: str, job_type: str | None = None) -> None:
    """Wendet die Folgeaktion an. Caller commit()et — diese Funktion add()et nur.

    Wirft QuickActionError bei Validierungsfehlern. Idempotent.
    """
    if action not in VALID_ACTIONS:
        raise QuickActionError(f"unbekannte quick_action: {action!r}")

    if action in ('company_rejected', 'already_applied'):
        company = (raw.company or '').strip()
        title = (raw.title or '').strip()
        if not company or not title:
            raise QuickActionError(
                "Firma/Titel im RawJob fehlt — quick_action nicht moeglich"
            )
        existing = _find_application(user.id, company, title)
        if action == 'company_rejected':
            _apply_company_rejected(user, raw, match, existing)
        else:
            _apply_already_applied(user, raw, match, existing)

    elif action == 'job_unavailable':
        pass  # nur feedback_text wird gesetzt — der setzt der Caller selbst

    elif action == 'wrong_job_type':
        if not job_type or job_type not in VALID_JOB_TYPES:
            raise QuickActionError(
                f"job_type muss in {sorted(VALID_JOB_TYPES)} sein"
            )
        _apply_wrong_job_type(user, job_type)


def _find_application(user_id: str, company: str, title: str) -> Application | None:
    return (
        Application.query
        .filter(
            Application.user_id == user_id,
            Application.deleted == False,  # noqa: E712
            db.func.lower(Application.company) == company.lower(),
            db.func.lower(Application.position) == title.lower(),
        )
        .first()
    )


def _apply_company_rejected(user: User, raw: RawJob, match: JobMatch,
                            existing: Application | None) -> None:
    if existing is None:
        db.session.add(Application(
            user_id=user.id,
            company=raw.company,
            position=raw.title,
            status='absage',
            applied_date=None,
            notes=f'Quick-Action company_rejected aus JobMatch #{match.id}',
        ))
    elif existing.status not in _PROTECTED_STATUSES:
        existing.status = 'absage'


def _apply_already_applied(user: User, raw: RawJob, match: JobMatch,
                           existing: Application | None) -> None:
    if existing is not None:
        return  # bereits erfasst, keine Aenderung
    db.session.add(Application(
        user_id=user.id,
        company=raw.company,
        position=raw.title,
        status='beworben',
        applied_date=date.today(),
        notes=f'Quick-Action already_applied aus JobMatch #{match.id}',
    ))


def _apply_wrong_job_type(user: User, job_type: str) -> None:
    try:
        current = set(json.loads(user.job_type_blacklist or '[]'))
    except (ValueError, TypeError):
        current = set()
    if job_type in current:
        return
    current.add(job_type)
    # Sort for determinism (Test-Erwartungen + Diff-Stabilitaet).
    user.job_type_blacklist = json.dumps(sorted(current))
```

- [ ] **Step 4: Tests ausführen (grün)**

```bash
python3 -m pytest tests/services/test_quick_actions.py -v
```
Expected: 11 PASSED

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/quick_actions.py tests/services/test_quick_actions.py
git commit -m "$(cat <<'EOF'
Add: services/job_matching/quick_actions.py — DB-Folgeaktionen

apply_quick_action() kapselt die vier Quick-Action-Folgen:
- company_rejected → Application(status='absage', applied_date=NULL),
  idempotent: upgraded bestehende Application aus ungeschuetzten Status
  (beworben/interview/...) auf absage; PROTECTED Status (absage/rejected/
  ghosting/zusage/offer) werden NICHT veraendert.
- already_applied  → Application(status='beworben', applied_date=today),
  bei bestehender Application: no-op (kein Downgrade).
- job_unavailable  → keine DB-Aktion (nur Caller setzt feedback_text).
- wrong_job_type   → User.job_type_blacklist Set-Union.

QuickActionError bei: unbekannter action, leerer company/title,
fehlendem/invalidem job_type. Caller bildet als 400 ab.

Test: 11 Faelle (positiv + idempotent + protected-status + errors).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: PATCH-Endpoint `/api/jobs/matches/<id>` um `quick_action` erweitern

**Files:**
- Modify: `api/jobs_user.py:542` (`update_match`)
- Create: `tests/api/test_quick_actions_endpoint.py`

- [ ] **Step 1: Tests schreiben (TDD)**

`tests/api/test_quick_actions_endpoint.py`:
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""End-to-end Tests fuer PATCH /api/jobs/matches/<id> mit quick_action."""
import json
import pytest

from database import db
from models import User, RawJob, JobMatch, JobSource, Application


@pytest.fixture
def setup(app, user_factory, auth_headers):
    with app.app_context():
        user = user_factory(email='qa@test.de')
        headers = auth_headers(user)
        src = JobSource(user_id=user.id, name='t', type='manual',
                        config_json='{}', enabled=True)
        db.session.add(src)
        db.session.commit()
        raw = RawJob(
            source_id=src.id, external_id='e1',
            title='Senior Security Analyst', company='Acme GmbH',
            url='https://x.test/1', description='d',
        )
        db.session.add(raw)
        db.session.commit()
        m = JobMatch(user_id=user.id, raw_job_id=raw.id, status='new')
        db.session.add(m)
        db.session.commit()
        return user.id, m.id, headers


def test_patch_company_rejected_sets_status_and_creates_application(client, setup):
    user_id, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'company_rejected'},
                     headers=headers)
    assert r.status_code == 200
    m = JobMatch.query.get(m_id)
    assert m.status == 'dismissed'
    assert m.feedback_text == 'quick_action_company_rejected'
    apps = Application.query.filter_by(user_id=user_id, deleted=False).all()
    assert len(apps) == 1
    assert apps[0].status == 'absage'


def test_patch_already_applied_creates_beworben(client, setup):
    user_id, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'already_applied'},
                     headers=headers)
    assert r.status_code == 200
    apps = Application.query.filter_by(user_id=user_id, deleted=False).all()
    assert len(apps) == 1 and apps[0].status == 'beworben'


def test_patch_job_unavailable_only_marks_feedback(client, setup):
    user_id, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'job_unavailable'},
                     headers=headers)
    assert r.status_code == 200
    m = JobMatch.query.get(m_id)
    assert m.status == 'dismissed'
    assert m.feedback_text == 'job_no_longer_available'
    assert Application.query.filter_by(user_id=user_id).count() == 0


def test_patch_wrong_job_type_updates_user_blacklist(client, setup):
    user_id, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'wrong_job_type',
                           'job_type': 'werkstudent'},
                     headers=headers)
    assert r.status_code == 200
    u = User.query.get(user_id)
    assert json.loads(u.job_type_blacklist) == ['werkstudent']


def test_patch_400_unknown_quick_action(client, setup):
    _, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'not_a_thing'},
                     headers=headers)
    assert r.status_code == 400


def test_patch_400_wrong_job_type_missing_job_type(client, setup):
    _, m_id, headers = setup
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'wrong_job_type'},
                     headers=headers)
    assert r.status_code == 400
```

**Wichtig**: `auth_headers`-Fixture in `tests/conftest.py:152` prüfen — falls Signatur abweicht, anpassen. Hier wird vorausgesetzt dass `auth_headers(user)` ein dict mit `Authorization` zurückgibt.

- [ ] **Step 2: Tests ausführen (rot)**

```bash
python3 -m pytest tests/api/test_quick_actions_endpoint.py -v
```
Expected: 6 FAILED, weil PATCH `quick_action` noch nicht versteht.

- [ ] **Step 3: PATCH-Endpoint erweitern**

In `api/jobs_user.py`, in `update_match()` (Z. 542-585), nach der bestehenden `status`-Validierung und VOR dem `db.session.commit()`:

```python
    # Quick-Action (Phase 1, Spec 2026-06-05): triggert Folgeaktionen + setzt
    # status='dismissed' implizit. feedback_text wird zwingend gesetzt;
    # user-uebergebener feedback_text wird ignoriert.
    quick_action = data.get('quick_action')
    if quick_action is not None:
        from services.job_matching.quick_actions import (
            apply_quick_action, FEEDBACK_TEXT_BY_ACTION, QuickActionError,
        )
        raw = RawJob.query.get(m.raw_job_id)
        if raw is None:
            return jsonify({"error": "RawJob nicht gefunden"}), 500
        try:
            apply_quick_action(
                user=user, match=m, raw=raw,
                action=quick_action,
                job_type=data.get('job_type'),
            )
        except QuickActionError as exc:
            return jsonify({"error": str(exc)}), 400
        m.status = 'dismissed'
        m.feedback_text = FEEDBACK_TEXT_BY_ACTION[quick_action]
```

Achtung: dieser Block muss VOR dem bestehenden `text = data.get('feedback_text')`-Block stehen, damit der user-übergebene `feedback_text` ignoriert wird (Spec §2: "user-übergebener feedback_text wird ignoriert"). Praktisch: setze ein Flag und überspringe den `text`-Block bei `quick_action`.

Cleaner: nach dem `quick_action`-Block ein early-return Path nicht möglich (Centroid-Update muss laufen). Stattdessen:

```python
    text = data.get('feedback_text')
    if text is not None and quick_action is None:  # quick_action gewinnt
        if not isinstance(text, str):
            ...
```

- [ ] **Step 4: Tests ausführen (grün)**

```bash
python3 -m pytest tests/api/test_quick_actions_endpoint.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Regression — bestehende PATCH-Tests**

```bash
python3 -m pytest tests/api/ -v -k "matches" --no-header 2>&1 | tail -30
```
Expected: bestehende Tests weiterhin PASSED.

- [ ] **Step 6: Commit**

```bash
git add api/jobs_user.py tests/api/test_quick_actions_endpoint.py
git commit -m "$(cat <<'EOF'
Add: PATCH /api/jobs/matches/<id> versteht quick_action + job_type

Optionales Feld quick_action setzt status='dismissed' implizit + ruft
services.job_matching.quick_actions.apply_quick_action() auf. System
ueberschreibt feedback_text mit Codes 'quick_action_*' / 'job_no_longer_
available' / 'wrong_job_type_blocked'; user-uebergebener feedback_text
wird bei quick_action ignoriert.

QuickActionError -> 400. Backwards-kompatibel: PATCH ohne quick_action
verhaelt sich wie bisher.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Profile-Endpoint um `job_type_blacklist` erweitern

**Files:**
- Modify: `api/profile.py` (GET um Z. 158, PATCH um Z. 178 in `update_job_discovery_filters`)
- Create: `tests/api/test_profile_job_type_blacklist.py`

- [ ] **Step 1: Tests schreiben**

`tests/api/test_profile_job_type_blacklist.py`:
```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests fuer GET/PATCH job_type_blacklist via /api/profile/job-discovery."""
import json
import pytest

from database import db
from models import User


def test_get_returns_job_type_blacklist(client, user_factory, auth_headers):
    user = user_factory()
    user.job_type_blacklist = json.dumps(['werkstudent'])
    db.session.commit()
    headers = auth_headers(user)

    r = client.get('/api/profile/job-discovery', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['filters']['job_type_blacklist'] == ['werkstudent']


def test_patch_sets_job_type_blacklist(client, user_factory, auth_headers):
    user = user_factory()
    headers = auth_headers(user)
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': ['werkstudent', 'freelance']},
        headers=headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    assert sorted(json.loads(user.job_type_blacklist)) == ['freelance', 'werkstudent']


def test_patch_rejects_invalid_job_type(client, user_factory, auth_headers):
    user = user_factory()
    headers = auth_headers(user)
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': ['not_a_real_type']},
        headers=headers,
    )
    assert r.status_code == 400


def test_patch_rejects_non_list(client, user_factory, auth_headers):
    user = user_factory()
    headers = auth_headers(user)
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': 'werkstudent'},
        headers=headers,
    )
    assert r.status_code == 400


def test_patch_empty_list_clears_blacklist(client, user_factory, auth_headers):
    user = user_factory()
    user.job_type_blacklist = json.dumps(['werkstudent'])
    db.session.commit()
    headers = auth_headers(user)

    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': []},
        headers=headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    assert json.loads(user.job_type_blacklist) == []
```

- [ ] **Step 2: Tests ausführen (rot)**

```bash
python3 -m pytest tests/api/test_profile_job_type_blacklist.py -v
```
Expected: 5 FAILED.

- [ ] **Step 3: GET-Endpoint erweitern**

In `api/profile.py`, im `get_job_discovery`-Handler (Z. 130+), im `filters`-Dict (Z. 156):

```python
        'filters': {
            'job_region_filter': user.job_region_filter,
            'job_language_filter': user.job_language_filter,
            'job_notification_threshold': user.job_notification_threshold,
            'job_reject_filter_enabled': user.job_reject_filter_enabled,
            'job_reject_window_days': user.job_reject_window_days,
            'job_type_blacklist': _parse_blacklist(user.job_type_blacklist),
        },
```

Helper am Modul-Anfang (nach den Imports). Wichtig: `VALID_JOB_TYPES` aus Task 4 importieren statt zu duplizieren (DRY):
```python
import json as _profile_json_blacklist
from services.job_matching.quick_actions import VALID_JOB_TYPES as _VALID_JOB_TYPES


def _parse_blacklist(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = _profile_json_blacklist.loads(raw)
    except (TypeError, ValueError):
        return []
    return [x for x in v if isinstance(x, str) and x in _VALID_JOB_TYPES]
```

- [ ] **Step 4: PATCH-Endpoint erweitern**

In `update_job_discovery_filters`, vor dem `user.updated_at = ...`-Block (Z. 218):

```python
    if 'job_type_blacklist' in data:
        v = data['job_type_blacklist']
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            return {'error': 'job_type_blacklist muss list of strings sein'}, 400
        invalid = [x for x in v if x not in _VALID_JOB_TYPES]
        if invalid:
            return {'error': f'unbekannte job_types: {invalid}'}, 400
        # Set-Dedup + sortiert (deterministisch)
        user.job_type_blacklist = _profile_json_blacklist.dumps(sorted(set(v)))
```

Im Response-Dict (Z. 221-227) ebenfalls:
```python
    return {
        ...
        'job_type_blacklist': _parse_blacklist(user.job_type_blacklist),
    }, 200
```

- [ ] **Step 5: Tests ausführen (grün)**

```bash
python3 -m pytest tests/api/test_profile_job_type_blacklist.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add api/profile.py tests/api/test_profile_job_type_blacklist.py
git commit -m "$(cat <<'EOF'
Add: /api/profile/job-discovery exposed job_type_blacklist

GET liefert das Feld im 'filters'-Block. PATCH /filters akzeptiert
list[str] mit Werten in {'werkstudent','freelance','temp_agency'};
ungueltige Werte -> 400. Deterministisch: sorted+set vor Speichern.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — Quick-Action-Buttons im Dismiss-Modal

**Files:**
- Modify: `index.html` (Modal-HTML ~Z. 12000, Modal-JS ~Z. 12042)

Frontend hat keine automatischen Tests im Repo — Verifikation per Browser. Spec §7 nennt manuelle Checkliste.

- [ ] **Step 1: Modal-HTML erweitern**

In `index.html`, das `<form id="dismissFeedbackForm">` ersetzen — Aktion-Block oben, Lern-Reasons in `<details>` darunter:

```html
<form id="dismissFeedbackForm" style="padding:1.5rem;">
    <p style="margin-top:0;color:var(--text-muted);font-size:0.9rem">
        Wähle eine Aktion (mit Folgewirkung) oder gib unten optional AI-Feedback.
    </p>

    <fieldset id="quickActionBlock" style="border:1px solid var(--border);border-radius:6px;padding:0.75rem 1rem;margin:0 0 1rem;">
        <legend style="padding:0 0.5rem;font-size:0.85rem;color:var(--text-muted)">Direkt-Aktion</legend>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">
            <button type="button" class="btn btn-secondary qa-btn" data-action="company_rejected">
                🚫 Firma hat schon abgelehnt
                <div style="font-size:0.75rem;color:var(--text-muted);font-weight:normal">Future-Block für Firma</div>
            </button>
            <button type="button" class="btn btn-secondary qa-btn" data-action="already_applied">
                🔁 Schon dort beworben
                <div style="font-size:0.75rem;color:var(--text-muted);font-weight:normal">Als beworben markieren</div>
            </button>
            <button type="button" class="btn btn-secondary qa-btn" data-action="job_unavailable">
                📋 Stelle nicht mehr verfügbar
                <div style="font-size:0.75rem;color:var(--text-muted);font-weight:normal">Marker für Phrasen-Lernen</div>
            </button>
            <button type="button" class="btn btn-secondary qa-btn" data-action="wrong_job_type">
                🏷️ Falscher Job-Typ
                <div style="font-size:0.75rem;color:var(--text-muted);font-weight:normal">Aktiviert Filter im Profil</div>
            </button>
        </div>
        <div id="qaJobTypeSubchoice" style="display:none;margin-top:0.75rem;padding-top:0.75rem;border-top:1px dashed var(--border)">
            <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.4rem">Welcher Typ?</div>
            <div style="display:flex;gap:0.6rem;flex-wrap:wrap">
                <label><input type="radio" name="qa_job_type" value="werkstudent"> Werkstudent</label>
                <label><input type="radio" name="qa_job_type" value="freelance"> Freelancer / Freiberuflich</label>
                <label><input type="radio" name="qa_job_type" value="temp_agency"> Arbeitnehmerüberlassung (AÜ)</label>
            </div>
            <button type="button" class="btn btn-primary btn-sm" id="qaJobTypeSubmit" style="margin-top:0.5rem">Anwenden + Verwerfen</button>
        </div>
    </fieldset>

    <details style="margin:0 0 1rem;">
        <summary style="cursor:pointer;color:var(--text-muted);font-size:0.85rem">Optional: AI-Match-Feedback geben</summary>
        <fieldset style="border:1px solid var(--border);border-radius:6px;padding:0.75rem 1rem;margin:0.75rem 0;">
            <legend style="padding:0 0.5rem;font-size:0.85rem;color:var(--text-muted)">Gründe (mehrere möglich)</legend>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem 1rem;">
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="wrong_location"> Falscher Ort</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="salary_too_low"> Gehalt zu niedrig</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="missing_skills"> Fehlende Skills</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="wrong_industry"> Falsche Branche</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="overqualified"> Überqualifiziert</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="underqualified"> Unterqualifiziert</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="wrong_seniority"> Falsches Level</label>
                <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer"><input type="checkbox" name="reason" value="other"> Sonstiges</label>
            </div>
        </fieldset>
        <label style="display:block;margin-bottom:0">
            <span style="font-size:0.85rem;color:var(--text-muted)">Freitext (optional, max 500 Zeichen)</span>
            <textarea name="feedback_text" maxlength="500" rows="3"
                      style="width:100%;margin-top:0.25rem;padding:0.5rem;border:1px solid var(--border);border-radius:6px;font-family:inherit;font-size:0.9rem;box-sizing:border-box"
                      placeholder="z.B. Stellenanzeige zu vage, Remote-Anteil nicht klar, ..."></textarea>
        </label>
    </details>

    <div class="modal-footer" style="margin:0 -1.5rem -1.5rem;">
        <button type="button" class="btn btn-secondary" id="dismissCancelBtn" onclick="closeModal('dismissFeedbackModal')">Abbrechen</button>
        <button type="button" class="btn btn-secondary" id="dismissSkipBtn">Skip (ohne Feedback)</button>
        <button type="submit" class="btn btn-danger" id="dismissSubmitBtn">Verwerfen mit Feedback</button>
    </div>
</form>

<style>
@media (max-width: 600px) {
    #quickActionBlock > div:first-of-type { grid-template-columns: 1fr !important; }
}
.qa-btn { text-align: left; padding: 0.6rem 0.75rem; }
</style>
```

- [ ] **Step 2: Modal-JS erweitern**

In `index.html` im Script-Block direkt unter dem Modal, im `(function () { ... })();`-Wrapper (Z. 12042+):

(a) Reset im `openDismissModal` ergänzen:
```javascript
        if (form) {
            form.querySelectorAll('input[name="reason"]').forEach(cb => { cb.checked = false; });
            form.querySelectorAll('input[name="qa_job_type"]').forEach(rb => { rb.checked = false; });
            const ta = form.querySelector('textarea[name="feedback_text"]');
            if (ta) ta.value = '';
            const sub = document.getElementById('qaJobTypeSubchoice');
            if (sub) sub.style.display = 'none';
        }
```

(b) `performDismiss` um optionalen `quickAction`-Pfad erweitern:
```javascript
    async function performDismiss(reasons, text, quickAction, jobType) {
        const id = pendingMatchId;
        if (!id) return;
        const body = { status: 'dismissed' };
        if (quickAction) {
            body.quick_action = quickAction;
            if (jobType) body.job_type = jobType;
        } else {
            if (Array.isArray(reasons) && reasons.length) body.feedback_reasons = reasons;
            if (text) body.feedback_text = text;
        }
        try {
            await Auth.fetch(`/jobs/matches/${id}`, {
                method: 'PATCH',
                body: JSON.stringify(body),
            });
            if (typeof showToast === 'function') {
                const msg = quickAction
                    ? ({
                        company_rejected: '🚫 Firma blockiert + verworfen',
                        already_applied: '🔁 Als beworben markiert',
                        job_unavailable: '📋 Markiert als nicht mehr verfügbar',
                        wrong_job_type: '🏷️ Job-Typ-Filter aktiviert + verworfen',
                    })[quickAction] || 'Verworfen'
                    : (reasons && reasons.length || text
                        ? 'Verworfen — danke für das Feedback'
                        : 'Verworfen');
                showToast(msg, 'success');
            }
            const cb = onDoneCallback;
            pendingMatchId = null;
            onDoneCallback = null;
            if (typeof closeModal === 'function') closeModal('dismissFeedbackModal');
            if (cb) cb();
            else if (typeof fetchMatches === 'function') fetchMatches();
        } catch (e) {
            if (typeof showToast === 'function') {
                showToast('Verwerfen fehlgeschlagen: ' + (e && e.message ? e.message : 'unbekannt'), 'error');
            } else {
                alert('Fehler: ' + (e && e.message ? e.message : 'unbekannt'));
            }
        }
    }
```

(c) Quick-Action-Button-Handler im `DOMContentLoaded` ergänzen:
```javascript
        const qaButtons = document.querySelectorAll('.qa-btn');
        const jobTypeSubchoice = document.getElementById('qaJobTypeSubchoice');
        const jobTypeSubmit = document.getElementById('qaJobTypeSubmit');
        qaButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                if (action === 'wrong_job_type') {
                    jobTypeSubchoice.style.display = 'block';
                } else {
                    performDismiss([], '', action, null);
                }
            });
        });
        if (jobTypeSubmit) {
            jobTypeSubmit.addEventListener('click', () => {
                const checked = document.querySelector('input[name="qa_job_type"]:checked');
                if (!checked) {
                    if (typeof showToast === 'function') {
                        showToast('Bitte einen Job-Typ wählen', 'warning');
                    }
                    return;
                }
                performDismiss([], '', 'wrong_job_type', checked.value);
            });
        }
```

(d) Update der `submit`-Handler-Aufrufe in `performDismiss(...)` auf 4 Argumente (reasons, text, null, null):
```javascript
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const reasons = Array.from(form.querySelectorAll('input[name="reason"]:checked')).map(cb => cb.value);
            const text = (form.querySelector('textarea[name="feedback_text"]').value || '').trim();
            performDismiss(reasons, text, null, null);
        });
        ...
        skipBtn.addEventListener('click', () => performDismiss([], '', null, null));
```

- [ ] **Step 3: Manuelle Verifikation**

Dev-Server starten:
```bash
python3 app.py
```
Im Browser auf [http://localhost:5000](http://localhost:5000) einloggen. Mindestens 1 JobMatch im Status `new` muss vorhanden sein (notfalls einen anlegen).

Checkliste (per Match einmal durchspielen):

| Test | Erwartung |
|---|---|
| 🗑️ Verwerfen → Modal öffnet sich, Quick-Action-Block oben sichtbar | ✓ |
| Klick „🚫 Firma abgelehnt" | Toast „🚫 Firma blockiert + verworfen", Karte verschwindet. In Bewerbungen-Tab erscheint neue Application(status=absage) für die Firma+Position. |
| Bei nächstem Match derselben Firma: prefilter-cron triggern → Match dismissed mit `company_already_rejected` (DB-Check) | ✓ |
| Klick „🔁 Schon beworben" | Application(status=beworben, applied_date=heute) angelegt. |
| Klick „📋 Stelle nicht mehr verfügbar" | Keine Application, Match dismissed mit feedback_text=job_no_longer_available. |
| Klick „🏷️ Falscher Job-Typ" | Sub-Block mit 3 Radio-Buttons erscheint. Auswahl + „Anwenden" → User.job_type_blacklist enthält den Wert. |
| Aufklappen „Optional: AI-Feedback" → bestehende Reasons + Freitext nutzbar | ✓ |
| „Skip" → Standard-Dismiss ohne Aktion | ✓ |
| Browser-DevTools auf 600 px Mobile-Viewport → Buttons 1-Spalte | ✓ |

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "$(cat <<'EOF'
Add: Quick-Action-Buttons im Dismiss-Feedback-Modal

Vier 1-Klick-Aktionen mit Folgewirkung (siehe Spec
docs/superpowers/specs/2026-06-05-quick-reasons-ui-design.md):
- "Firma hat schon abgelehnt"
- "Schon dort beworben"
- "Stelle nicht mehr verfuegbar"
- "Falscher Job-Typ" (mit Sub-Auswahl Werkstudent/Freelancer/AUe)

Bestehende AI-Match-Reasons + Freitext in <details> einklappbar gemacht
(default: zugeklappt). Skip-Button + Submit-Button bleiben unveraendert.

Mobile-Layout: 2x2-Grid bricht via @media auf 1-Spalte.

Manuell verifiziert: Modal offnet, jede Aktion fuehrt zum erwarteten
Toast und DB-Effekt, Sub-Auswahl funktioniert, Skip-Pfad intakt,
Mobile-Viewport rendert.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Frontend — Job-Typ-Blacklist im Profil-Tab

**Files:**
- Modify: `index.html` (Settings-Tab Profile-Block, vermutlich in der Nähe von `job_reject_filter_enabled`-UI)

- [ ] **Step 1: UI-Block hinzufügen**

Den existierenden Settings-Block für Job-Filter in `index.html` finden:

```bash
grep -n "job_reject_filter_enabled\|job_reject_window_days\|Reject-Filter" index.html | head -10
```

Nahe dieses Blocks (typischerweise im Profil/Settings-Tab) eine neue Sektion einfügen:
```html
<fieldset style="border:1px solid var(--border);border-radius:6px;padding:0.75rem 1rem;margin:0 0 1rem;">
    <legend style="padding:0 0.5rem;font-size:0.85rem;color:var(--text-muted)">Job-Typen ausblenden</legend>
    <p style="margin:0 0 0.5rem;font-size:0.85rem;color:var(--text-muted)">
        Stellen mit diesen Typ-Schlüsselwörtern im Titel werden automatisch verworfen.
    </p>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
        <label><input type="checkbox" id="jtBlacklistWerkstudent" value="werkstudent"> Werkstudenten-Stellen</label>
        <label><input type="checkbox" id="jtBlacklistFreelance" value="freelance"> Freelancer / Freiberuflich</label>
        <label><input type="checkbox" id="jtBlacklistTempAgency" value="temp_agency"> Arbeitnehmerüberlassung (AÜ)</label>
    </div>
</fieldset>
```

- [ ] **Step 2: Load/Save-JS verdrahten**

Wo aktuell die anderen Filter-Settings geladen/gespeichert werden (Such-Pattern: `loadJobDiscoverySettings`, `saveJobDiscoverySettings` oder ähnlich — falls Funktionsname abweicht, mit `grep -n "job_reject_filter_enabled" index.html` finden):

(a) In der Load-Funktion (nach `Auth.fetch('/profile/job-discovery')`):
```javascript
        const blacklist = (body.filters && body.filters.job_type_blacklist) || [];
        document.getElementById('jtBlacklistWerkstudent').checked = blacklist.includes('werkstudent');
        document.getElementById('jtBlacklistFreelance').checked = blacklist.includes('freelance');
        document.getElementById('jtBlacklistTempAgency').checked = blacklist.includes('temp_agency');
```

(b) In der Save-Funktion (PATCH-Body um Feld erweitern):
```javascript
        const blacklist = [];
        if (document.getElementById('jtBlacklistWerkstudent').checked) blacklist.push('werkstudent');
        if (document.getElementById('jtBlacklistFreelance').checked) blacklist.push('freelance');
        if (document.getElementById('jtBlacklistTempAgency').checked) blacklist.push('temp_agency');
        body.job_type_blacklist = blacklist;
```

- [ ] **Step 3: Manuelle Verifikation**

Browser: Profil-Tab öffnen → Werkstudent-Checkbox anhaken → Speichern → Reload → Checkbox bleibt gesetzt → DB-Check: `User.job_type_blacklist == '["werkstudent"]'`.

Quick-Action im Dismiss-Modal: „🏷️ Falscher Job-Typ" → Werkstudent → die Profil-Checkbox ist nach Reload aktiv (round-trip).

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "$(cat <<'EOF'
Add: Job-Typ-Blacklist Settings-Sektion im Profil-Tab

Drei Checkboxes (Werkstudent/Freelancer/AUe) im Job-Discovery-Settings-
Block. Laedt+speichert User.job_type_blacklist via
/api/profile/job-discovery (GET) + /filters (PATCH).

Round-trip mit Quick-Action "Falscher Job-Typ" verifiziert: Modal-Klick
aktiviert die passende Profil-Checkbox; manuelles Setzen wirkt symmetrisch.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Integrations-Smoke + AGENTS.md §7 Handoff-Entry

**Files:**
- Modify: `AGENTS.md` (§7 Handoff zone)

- [ ] **Step 1: Vollständigen Test-Sweep laufen lassen**

```bash
python3 -m pytest tests/services/ tests/api/ -v 2>&1 | tail -10
```
Expected: alle Quick-Reasons-Tests grün, keine Regression.

- [ ] **Step 2: Handoff-Entry oben in §7 einfügen**

In `AGENTS.md`, direkt unter `## 7. Handoff zone (free-form, append-only)`:

```markdown
### 2026-06-05 — Quick-Reasons-UI (Phase 1) implementiert
- **Migration:** `User.job_type_blacklist TEXT NOT NULL DEFAULT '[]'` (revision a9b8c7d6e5f4 on top of f0778653c386).
- **Backend:** Neues Modul `services/job_matching/quick_actions.py` mit `apply_quick_action()` (4 Aktionen, idempotent, ProtectedStatuses gegen Downgrade). PATCH `/api/jobs/matches/<id>` erweitert um `quick_action` + `job_type`. Profile-Endpoint kennt `job_type_blacklist`. Prefilter-Handler dismissed Matches mit Blacklist-Typ via neuer `detect_job_type()`-Funktion.
- **Frontend:** Dismiss-Modal hat 4 Quick-Action-Buttons oben; bestehende AI-Reasons sind in `<details>` zugeklappt. Profil-Tab hat 3 Job-Typ-Checkboxes.
- **Tests:** ~40 neue Tests (unit + integration). NICHT deployed to IONOS.
- **Metric watch (14 Tage post-deploy):** Anteil dismisses mit feedback_text != '' soll von 55 % auf ≥ 80 % steigen, `company_already_rejected`-Treffer ≥ 3x.
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "$(cat <<'EOF'
Add: AGENTS.md §7 Handoff-Entry — Quick-Reasons-UI Phase 1 fertig

Dokumentiert Migration, neue Module, betroffene Endpoints, Test-Coverage.
Metric-Watch in 14 Tagen prufen.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: PR-Branch pushen**

```bash
git push
```

Bestehender PR #20 (auf demselben Branch) bekommt die Commits zu sehen. Falls separater PR gewünscht: neuen Branch von `master` cherry-picken + PR öffnen.

---

## Erfolgs-Kriterien

- [ ] Alle Tasks 1-9 abgeschlossen.
- [ ] Tests: `python3 -m pytest tests/services/ tests/api/` → keine Regression, ~40 neue Tests grün.
- [ ] Manuelle Verifikation (Task 7+8): jede der 4 Quick-Actions löst korrekten DB-Effekt aus.
- [ ] AGENTS.md §7 aktuell.
- [ ] Deploy auf IONOS: separater Schritt (Migration läuft automatisch via `bewerbungen-deploy.sh`).
- [ ] Metric-Check 14 Tage post-deploy: Anteil dismisses mit feedback_text ≥ 80 %.
