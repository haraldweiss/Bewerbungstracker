# Job-Discovery Phase A — Backend-Pipeline & DB-Schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementiert die komplette Backend-Pipeline für automatische Job-Suche mit Pre-Filter und Claude-Matching. Liefert eine via REST-API steuerbare Crawl-Match-Notify-Pipeline (5 Cron-Stages) ohne Frontend.

**Architecture:** 4 neue DB-Tabellen + 5 Cron-Endpoints (Stages crawl/prefilter/claude-match/notify/cleanup), Source-Adapter-Pattern für RSS/Adzuna/Bundesagentur/Arbeitnow, lokaler Pre-Filter via Keyword-Scoring, Claude-Match nutzt vorerst den bestehenden Server-Key (BYOK kommt in Phase B).

**Tech Stack:** Python 3, Flask, SQLAlchemy, pytest, `feedparser` (RSS), `requests` (HTTP), `anthropic` SDK (bestehend), `responses` (HTTP-Mocking in Tests).

**Spec:** [docs/superpowers/specs/2026-04-28-job-discovery-design.md](../specs/2026-04-28-job-discovery-design.md)

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `models.py` | + 3 neue Modelle (`JobSource`, `RawJob`, `JobMatch`), Erweiterung `ApiCall.key_owner`, neue Felder auf `User` für Job-Settings |
| `services/job_sources/__init__.py` | Adapter-Registry: type → Adapter-Class |
| `services/job_sources/base.py` | `JobSourceAdapter` Base-Class mit `fetch()`-Interface |
| `services/job_sources/rss.py` | RSS/Atom-Adapter |
| `services/job_sources/adzuna.py` | Adzuna-API-Adapter |
| `services/job_sources/bundesagentur.py` | Bundesagentur-Jobsuche-API-Adapter |
| `services/job_sources/arbeitnow.py` | Arbeitnow-API-Adapter |
| `services/job_matching/__init__.py` | Package-Init |
| `services/job_matching/cv_tokenizer.py` | Extrahiert Skills/Titel/Tech aus CV-JSON |
| `services/job_matching/prefilter.py` | Lokales Keyword-Scoring |
| `services/job_matching/claude_matcher.py` | Claude-Aufruf für Match-Score+Reasoning |
| `services/job_matching/notifier.py` | Push-Notification an User |
| `services/ssrf_guard.py` | URL-Validator gegen Private-IP-Ranges |
| `api/jobs_cron.py` | Blueprint mit 5 Cron-Endpoints (Token-geschützt) |
| `api/jobs_user.py` | Blueprint mit User-Endpoints (Quellen, Matches) |
| `services/cron_auth.py` | `@require_cron_token` Decorator |
| `scripts/seed_job_sources.py` | Initialer Insert von 3-5 globalen Quellen |
| `scripts/migrate_job_discovery.py` | DB-Init/Upgrade-Skript |
| `tests/services/test_ssrf_guard.py` | Unit-Tests |
| `tests/services/test_cv_tokenizer.py` | Unit-Tests |
| `tests/services/test_prefilter.py` | Unit-Tests |
| `tests/services/test_job_sources_rss.py` | Adapter-Tests mit RSS-Fixture |
| `tests/services/test_job_sources_adzuna.py` | Adapter-Tests mit API-Fixture |
| `tests/services/test_job_sources_bundesagentur.py` | Adapter-Tests |
| `tests/services/test_job_sources_arbeitnow.py` | Adapter-Tests |
| `tests/services/test_claude_matcher.py` | Mock-basierter Test |
| `tests/api/test_jobs_cron.py` | Integration-Tests Pipeline |
| `tests/api/test_jobs_user.py` | Integration-Tests User-API |
| `tests/fixtures/rss_stepstone_sample.xml` | RSS-Fixture |
| `tests/fixtures/adzuna_response.json` | API-Fixture |
| `tests/fixtures/bundesagentur_response.json` | API-Fixture |
| `tests/fixtures/arbeitnow_response.json` | API-Fixture |

---

## Task 1: Test-Fixtures vorbereiten

**Files:**
- Create: `tests/fixtures/rss_stepstone_sample.xml`
- Create: `tests/fixtures/adzuna_response.json`
- Create: `tests/fixtures/bundesagentur_response.json`
- Create: `tests/fixtures/arbeitnow_response.json`

- [ ] **Step 1: RSS-Fixture anlegen**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>StepStone Jobs Frontend</title>
  <link>https://www.stepstone.de</link>
  <item>
    <title>Senior Frontend Developer (m/w/d) - React/TypeScript</title>
    <link>https://www.stepstone.de/jobs/senior-frontend-12345</link>
    <guid isPermaLink="false">stepstone-12345</guid>
    <pubDate>Mon, 28 Apr 2026 10:00:00 +0200</pubDate>
    <description><![CDATA[Wir suchen einen erfahrenen Frontend-Entwickler mit React, TypeScript und 5+ Jahren Erfahrung. Standort: Berlin. Remote möglich.]]></description>
    <category>Berlin</category>
  </item>
  <item>
    <title>Junior Backend Developer Python</title>
    <link>https://www.stepstone.de/jobs/junior-backend-67890</link>
    <guid isPermaLink="false">stepstone-67890</guid>
    <pubDate>Sun, 27 Apr 2026 14:00:00 +0200</pubDate>
    <description><![CDATA[Einstiegsposition Backend mit Python und Flask. München. Vollzeit.]]></description>
    <category>München</category>
  </item>
</channel>
</rss>
```

- [ ] **Step 2: Adzuna-Fixture anlegen**

```json
{
  "results": [
    {
      "id": "1234567890",
      "title": "Senior React Developer",
      "company": {"display_name": "ACME GmbH"},
      "location": {"display_name": "Berlin", "area": ["Deutschland", "Berlin"]},
      "redirect_url": "https://www.adzuna.de/land/ad/1234567890",
      "description": "We need a senior React developer with 5+ years of experience.",
      "created": "2026-04-28T08:00:00Z",
      "salary_min": 65000,
      "salary_max": 85000
    }
  ],
  "count": 1
}
```

- [ ] **Step 3: Bundesagentur-Fixture anlegen**

```json
{
  "stellenangebote": [
    {
      "refnr": "10000-1234567890-S",
      "beruf": "Frontend Entwickler/in",
      "titel": "Frontend Entwickler React",
      "arbeitgeber": "Tech Solutions GmbH",
      "arbeitsort": {"plz": "10115", "ort": "Berlin", "region": "Berlin"},
      "aktuelleVeroeffentlichungsdatum": "2026-04-28",
      "externeUrl": null
    }
  ],
  "maxErgebnisse": 1
}
```

- [ ] **Step 4: Arbeitnow-Fixture anlegen**

```json
{
  "data": [
    {
      "slug": "senior-react-engineer-acme",
      "title": "Senior React Engineer",
      "company_name": "ACME",
      "location": "Berlin (Remote)",
      "url": "https://www.arbeitnow.com/view/senior-react-engineer-acme",
      "description": "Looking for a senior React engineer...",
      "tags": ["javascript", "react", "remote"],
      "created_at": 1714291200,
      "remote": true,
      "visa_sponsorship": false
    }
  ]
}
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/
git commit -m "test: Job-Discovery API-Fixtures (RSS/Adzuna/Bundesagentur/Arbeitnow)"
```

---

## Task 2: Datenmodell-Erweiterung — `JobSource`

**Files:**
- Modify: `models.py` (am Ende anhängen)
- Test: `tests/test_models_job_discovery.py` (neu)

- [ ] **Step 1: Failing-Test schreiben**

`tests/test_models_job_discovery.py`:
```python
import pytest
from datetime import datetime
from app import create_app
from database import db
from models import JobSource


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_job_source_creates_global(app):
    src = JobSource(
        name="Bundesagentur Frontend",
        type="bundesagentur",
        config={"was": "Frontend", "wo": "10115"},
        enabled=True,
        crawl_interval_min=60,
    )
    db.session.add(src)
    db.session.commit()

    assert src.id is not None
    assert src.user_id is None  # global
    assert src.consecutive_failures == 0
    assert src.config == {"was": "Frontend", "wo": "10115"}


def test_job_source_user_owned(app, user_factory):
    user = user_factory()
    src = JobSource(
        user_id=user.id,
        name="Mein RSS-Feed",
        type="rss",
        config={"url": "https://example.com/feed.xml"},
    )
    db.session.add(src)
    db.session.commit()

    assert src.user_id == user.id
```

- [ ] **Step 2: Run test → erwarte Failure**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
pytest tests/test_models_job_discovery.py -v
```
Erwartet: `ImportError: cannot import name 'JobSource'`

- [ ] **Step 3: `JobSource`-Modell in `models.py` ergänzen**

Am Ende von `models.py` anhängen:
```python
import json as _json


class JobSource(db.Model):
    """Quelle für Job-Crawl (universelle Feed-Verwaltung).

    user_id NULL = system-globale Quelle, sonst user-eigen.
    config ist type-spezifisches JSON (RSS-URL, Adzuna-Query, etc.).
    """
    __tablename__ = 'job_sources'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    _config_json = db.Column('config', db.Text, nullable=False, default='{}')
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    crawl_interval_min = db.Column(db.Integer, default=60, nullable=False)
    last_crawled_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    consecutive_failures = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def config(self) -> dict:
        return _json.loads(self._config_json or '{}')

    @config.setter
    def config(self, value: dict):
        self._config_json = _json.dumps(value or {})

    def __repr__(self):
        return f'<JobSource {self.id} {self.type}:{self.name}>'
```

- [ ] **Step 4: `user_factory`-Fixture sicherstellen**

`tests/conftest.py` öffnen — falls keine `user_factory` existiert, hinzufügen:
```python
import uuid
from models import User


@pytest.fixture
def user_factory(app):
    def _create(email=None, **kwargs):
        u = User(
            id=str(uuid.uuid4()),
            email=email or f"user-{uuid.uuid4().hex[:8]}@test.de",
            password_hash="$2b$12$dummy",
            is_active=True,
            **kwargs,
        )
        db.session.add(u)
        db.session.commit()
        return u
    return _create
```

- [ ] **Step 5: Run test → erwarte Passing**

```bash
pytest tests/test_models_job_discovery.py -v
```
Erwartet: PASS

- [ ] **Step 6: Commit**

```bash
git add models.py tests/test_models_job_discovery.py tests/conftest.py
git commit -m "feat: JobSource-Modell für universelle Feed-Verwaltung"
```

---

## Task 3: Datenmodell — `RawJob`

**Files:**
- Modify: `models.py`
- Test: `tests/test_models_job_discovery.py`

- [ ] **Step 1: Failing-Test ergänzen**

In `tests/test_models_job_discovery.py` anhängen:
```python
from models import RawJob


def test_raw_job_dedup_per_source(app):
    src = JobSource(name="Test", type="rss", config={"url": "x"})
    db.session.add(src)
    db.session.flush()

    job1 = RawJob(
        source_id=src.id,
        external_id="abc-123",
        title="Frontend",
        company="ACME",
        url="https://example.com/job/1",
        crawl_status="raw",
    )
    db.session.add(job1)
    db.session.commit()

    # Selbe (source_id, external_id) sollte UNIQUE-Constraint verletzen
    job_dup = RawJob(
        source_id=src.id,
        external_id="abc-123",
        title="Andere Daten",
        url="https://example.com/job/2",
        crawl_status="raw",
    )
    db.session.add(job_dup)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()
```

- [ ] **Step 2: Test läuft, schlägt fehl** (RawJob existiert nicht)

```bash
pytest tests/test_models_job_discovery.py::test_raw_job_dedup_per_source -v
```

- [ ] **Step 3: `RawJob` in `models.py` ergänzen**

```python
class RawJob(db.Model):
    """Gecrawlte Stellenausschreibung (geteilt zwischen Usern bei globalen Quellen).

    Pro User entsteht ein eigener JobMatch-Eintrag.
    """
    __tablename__ = 'raw_jobs'
    __table_args__ = (
        db.UniqueConstraint('source_id', 'external_id', name='uq_raw_job_source_external'),
        db.Index('ix_raw_jobs_status', 'crawl_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('job_sources.id'), nullable=False, index=True)
    external_id = db.Column(db.String(512), nullable=False)
    title = db.Column(db.String(512), nullable=False)
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    url = db.Column(db.String(1024), nullable=False)
    description = db.Column(db.Text)
    posted_at = db.Column(db.DateTime, nullable=True)
    _raw_payload = db.Column('raw_payload', db.Text, nullable=True)
    crawl_status = db.Column(db.String(16), default='raw', nullable=False)  # raw|prefiltered|matched|archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def raw_payload(self) -> dict:
        return _json.loads(self._raw_payload) if self._raw_payload else {}

    @raw_payload.setter
    def raw_payload(self, value: dict):
        self._raw_payload = _json.dumps(value) if value else None

    def __repr__(self):
        return f'<RawJob {self.id} {self.title[:30]}>'
```

- [ ] **Step 4: Test passt**

```bash
pytest tests/test_models_job_discovery.py -v
```
Erwartet: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models_job_discovery.py
git commit -m "feat: RawJob-Modell mit Dedup-Constraint (source_id, external_id)"
```

---

## Task 4: Datenmodell — `JobMatch`

**Files:**
- Modify: `models.py`
- Test: `tests/test_models_job_discovery.py`

- [ ] **Step 1: Failing-Test ergänzen**

```python
from models import JobMatch


def test_job_match_per_user_unique(app, user_factory):
    user = user_factory()
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="x1", title="t",
                 url="http://x", crawl_status="raw")
    db.session.add(raw); db.session.flush()

    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    db.session.add(m); db.session.commit()
    assert m.id is not None
    assert m.match_score is None  # noch nicht bewertet
    assert m.status == 'new'

    # Dupe in derselben (raw_job_id, user_id) Kombo soll fehlschlagen
    dup = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    db.session.add(dup)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `JobMatch` in `models.py`**

```python
class JobMatch(db.Model):
    """Per-User-Bewertung eines RawJob.

    status: 'new' = noch nicht angesehen, 'seen' = User hat ihn gesehen,
    'imported' = übernommen, 'dismissed' = verworfen oder Auto-Verworfen.
    """
    __tablename__ = 'job_matches'
    __table_args__ = (
        db.UniqueConstraint('raw_job_id', 'user_id', name='uq_match_job_user'),
        db.Index('ix_match_user_status_score', 'user_id', 'status', 'match_score'),
        db.Index('ix_match_prefilter_pending', 'prefilter_score'),
    )

    id = db.Column(db.Integer, primary_key=True)
    raw_job_id = db.Column(db.Integer, db.ForeignKey('raw_jobs.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    prefilter_score = db.Column(db.Float, nullable=True)
    match_score = db.Column(db.Float, nullable=True)
    match_reasoning = db.Column(db.Text, nullable=True)
    _missing_skills = db.Column('missing_skills', db.Text, nullable=True)
    status = db.Column(db.String(16), default='new', nullable=False)
    notified_at = db.Column(db.DateTime, nullable=True)
    imported_application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    raw_job = db.relationship('RawJob', backref='matches')

    @property
    def missing_skills(self) -> list:
        return _json.loads(self._missing_skills) if self._missing_skills else []

    @missing_skills.setter
    def missing_skills(self, value: list):
        self._missing_skills = _json.dumps(value) if value else None
```

- [ ] **Step 4: Test passt**

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models_job_discovery.py
git commit -m "feat: JobMatch-Modell mit per-User Match-Bewertung"
```

---

## Task 5: User-Settings für Job-Discovery + ApiCall.key_owner

**Files:**
- Modify: `models.py`
- Test: `tests/test_models_job_discovery.py`

- [ ] **Step 1: Failing-Test schreiben**

```python
from models import ApiCall


def test_user_has_job_settings_defaults(app, user_factory):
    u = user_factory()
    db.session.refresh(u)
    assert u.job_discovery_enabled is False
    assert u.job_notification_threshold == 80
    assert u.job_claude_budget_per_tick == 5
    assert u.job_daily_budget_cents == 50
    assert u.job_language_filter == ["de", "en"]
    assert u.job_region_filter is None


def test_api_call_has_key_owner_default(app, user_factory):
    u = user_factory()
    call = ApiCall(
        user_id=u.id,
        endpoint='/test',
        model='claude-haiku',
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
    )
    db.session.add(call); db.session.commit()
    assert call.key_owner == 'server'
```

- [ ] **Step 2: Tests laufen, schlagen fehl**

- [ ] **Step 3: `User`-Modell um Felder erweitern**

In `models.py` in der `User`-Klasse (nach `cv_data_json`) ergänzen:
```python
    # Job-Discovery Settings
    job_discovery_enabled = db.Column(db.Boolean, default=False, nullable=False)
    job_notification_threshold = db.Column(db.Integer, default=80, nullable=False)
    job_claude_budget_per_tick = db.Column(db.Integer, default=5, nullable=False)
    job_daily_budget_cents = db.Column(db.Integer, default=50, nullable=False)
    _job_language_filter = db.Column('job_language_filter', db.Text, default='["de","en"]')
    _job_region_filter = db.Column('job_region_filter', db.Text, nullable=True)

    @property
    def job_language_filter(self) -> list:
        return _json.loads(self._job_language_filter or '["de","en"]')

    @job_language_filter.setter
    def job_language_filter(self, value: list):
        self._job_language_filter = _json.dumps(value)

    @property
    def job_region_filter(self) -> dict | None:
        return _json.loads(self._job_region_filter) if self._job_region_filter else None

    @job_region_filter.setter
    def job_region_filter(self, value: dict | None):
        self._job_region_filter = _json.dumps(value) if value else None
```

- [ ] **Step 4: `ApiCall`-Modell um `key_owner` erweitern**

In der `ApiCall`-Klasse hinzufügen:
```python
    key_owner = db.Column(db.String(20), default='server', nullable=False)  # server|user|custom_endpoint
```

- [ ] **Step 5: Tests passen**

```bash
pytest tests/test_models_job_discovery.py -v
```

- [ ] **Step 6: Commit**

```bash
git add models.py tests/test_models_job_discovery.py
git commit -m "feat: Job-Discovery User-Settings + ApiCall.key_owner"
```

---

## Task 6: DB-Migrations-Skript

**Files:**
- Create: `scripts/migrate_job_discovery.py`

- [ ] **Step 1: Migrations-Skript schreiben**

```python
"""DB-Migration für Job-Discovery (Phase A).

Da das Projekt keine Alembic-Migrations nutzt, läuft dies als idempotentes
Init-Skript. db.create_all() legt neue Tabellen an, ALTER TABLE für
Erweiterungen bestehender Tabellen.

Usage:
    FLASK_ENV=production python scripts/migrate_job_discovery.py
"""
import os
import sys
from sqlalchemy import inspect, text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db


NEW_USER_COLUMNS = [
    ("job_discovery_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("job_notification_threshold", "INTEGER NOT NULL DEFAULT 80"),
    ("job_claude_budget_per_tick", "INTEGER NOT NULL DEFAULT 5"),
    ("job_daily_budget_cents", "INTEGER NOT NULL DEFAULT 50"),
    ("job_language_filter", 'TEXT DEFAULT \'["de","en"]\''),
    ("job_region_filter", "TEXT"),
]


def add_column_if_missing(table: str, column: str, type_def: str):
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns(table)]
    if column not in cols:
        with db.engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {type_def}'))
        print(f"  + {table}.{column}")
    else:
        print(f"  = {table}.{column} (existiert bereits)")


def main():
    app = create_app()
    with app.app_context():
        print("→ Erstelle neue Tabellen (job_sources, raw_jobs, job_matches)...")
        db.create_all()

        print("→ Erweitere users-Tabelle...")
        for col, type_def in NEW_USER_COLUMNS:
            add_column_if_missing('users', col, type_def)

        print("→ Erweitere api_calls-Tabelle...")
        add_column_if_missing('api_calls', 'key_owner', "VARCHAR(20) NOT NULL DEFAULT 'server'")

        print("✓ Migration abgeschlossen.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Skript testen**

```bash
mkdir -p scripts
# Skript in scripts/migrate_job_discovery.py speichern
python scripts/migrate_job_discovery.py
```
Erwartet: Ausgabe `+ users.job_discovery_enabled`, etc., dann `✓ Migration abgeschlossen.`

- [ ] **Step 3: Idempotenz testen — zweimal laufen lassen**

```bash
python scripts/migrate_job_discovery.py
```
Erwartet: alle `=` (existiert bereits), kein Fehler.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_job_discovery.py
git commit -m "feat: idempotentes DB-Migrations-Skript für Job-Discovery"
```

---

## Task 7: SSRF-Guard

**Files:**
- Create: `services/ssrf_guard.py`
- Test: `tests/services/test_ssrf_guard.py`

- [ ] **Step 1: Failing-Test schreiben**

```python
import pytest
from services.ssrf_guard import is_url_safe_for_rss, SSRFError, validate_rss_url


def test_blocks_localhost():
    assert is_url_safe_for_rss("http://localhost/feed") is False
    assert is_url_safe_for_rss("http://127.0.0.1/feed") is False

def test_blocks_private_ranges():
    assert is_url_safe_for_rss("http://192.168.1.1/feed") is False
    assert is_url_safe_for_rss("http://10.0.0.5/feed") is False
    assert is_url_safe_for_rss("http://169.254.169.254/feed") is False

def test_allows_public_url():
    assert is_url_safe_for_rss("https://example.com/feed.xml") is True
    assert is_url_safe_for_rss("https://www.stepstone.de/rss") is True

def test_blocks_invalid_url():
    assert is_url_safe_for_rss("not-a-url") is False
    assert is_url_safe_for_rss("file:///etc/passwd") is False
    assert is_url_safe_for_rss("ftp://example.com/feed") is False

def test_validate_raises_for_unsafe():
    with pytest.raises(SSRFError):
        validate_rss_url("http://localhost/x")
```

- [ ] **Step 2: Test schlägt fehl** (Modul existiert nicht)

- [ ] **Step 3: `services/ssrf_guard.py` schreiben**

```python
"""SSRF-Guard für externe URLs.

RSS-Quellen dürfen NUR public-routable HTTP/HTTPS sein. Private IP-Ranges
(RFC1918), localhost, link-local und Multicast werden geblockt.

Custom-AI-Endpoints (Phase B) nutzen einen separaten, weniger restriktiven
Guard, der Self-Hosted (localhost) erlaubt.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(Exception):
    pass


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # localhost
    ipaddress.ip_network("10.0.0.0/8"),         # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),     # link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),        # multicast
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_url_safe_for_rss(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return False
    return True


def validate_rss_url(url: str) -> None:
    if not is_url_safe_for_rss(url):
        raise SSRFError(f"URL nicht erlaubt (private/lokale IP, ungültiges Schema o.ä.): {url}")
```

- [ ] **Step 4: Tests passen**

```bash
mkdir -p tests/services
touch tests/services/__init__.py
pytest tests/services/test_ssrf_guard.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/ssrf_guard.py tests/services/
git commit -m "feat: SSRF-Guard für RSS-Quellen (blockiert private IPs)"
```

---

## Task 8: CV-Tokenizer

**Files:**
- Create: `services/job_matching/__init__.py` (leer)
- Create: `services/job_matching/cv_tokenizer.py`
- Test: `tests/services/test_cv_tokenizer.py`

- [ ] **Step 1: Failing-Test schreiben**

```python
from services.job_matching.cv_tokenizer import tokenize_cv, CVTokens


def test_extracts_skills_titles_and_freetext():
    cv_data = {
        "cv": {
            "skills": ["React", "TypeScript", "Python", "Docker"],
            "experiences": [
                {"title": "Senior Frontend Developer", "company": "ACME"},
                {"title": "Full Stack Engineer", "company": "Beta"},
            ],
            "summary": "8 Jahre Erfahrung mit JavaScript, Node.js, Cloud-Architektur."
        }
    }
    tokens = tokenize_cv(cv_data)
    assert isinstance(tokens, CVTokens)
    assert "react" in tokens.skills
    assert "typescript" in tokens.skills
    assert "senior frontend developer" in tokens.titles
    assert "javascript" in tokens.freetext  # case-insensitive

def test_handles_empty_cv():
    tokens = tokenize_cv({"cv": {}})
    assert tokens.skills == set()
    assert tokens.titles == set()

def test_handles_none():
    tokens = tokenize_cv(None)
    assert tokens.skills == set()
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/job_matching/cv_tokenizer.py` schreiben**

```python
"""CV-Tokenizer für Pre-Filter-Scoring.

Extrahiert aus dem cv_data_json eines Users drei Token-Mengen:
- skills (Skill-Liste, z.B. "react", "python")
- titles (Job-Titel-Historie)
- freetext (Tokens aus Summary/Cover-Letter, lowercased)

Das Format orientiert sich am bestehenden cv_data_json-Schema.
"""
from dataclasses import dataclass, field
import re


_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9\.\+#]{2,}")


@dataclass
class CVTokens:
    skills: set = field(default_factory=set)
    titles: set = field(default_factory=set)
    freetext: set = field(default_factory=set)


def _tokenize_text(text: str) -> set:
    if not text:
        return set()
    return {m.group().lower() for m in _TOKEN_RE.finditer(text)}


def tokenize_cv(cv_data: dict | None) -> CVTokens:
    """Extrahiert Tokens aus cv_data_json.

    Args:
        cv_data: dict mit Schlüssel 'cv' → {skills, experiences, summary, ...}
    """
    tokens = CVTokens()
    if not cv_data or not isinstance(cv_data, dict):
        return tokens

    cv = cv_data.get('cv') or {}

    # Skills: Liste von Strings
    for skill in cv.get('skills') or []:
        if isinstance(skill, str):
            tokens.skills.add(skill.strip().lower())

    # Titel: aus experiences[].title
    for exp in cv.get('experiences') or []:
        if isinstance(exp, dict) and exp.get('title'):
            tokens.titles.add(exp['title'].strip().lower())

    # Freetext: Summary, Bio, Cover-Letter-Templates
    for field_name in ('summary', 'bio', 'cover_letter'):
        if cv.get(field_name):
            tokens.freetext |= _tokenize_text(cv[field_name])

    return tokens
```

- [ ] **Step 4: Tests passen**

```bash
mkdir -p services/job_matching
touch services/job_matching/__init__.py
pytest tests/services/test_cv_tokenizer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/__init__.py services/job_matching/cv_tokenizer.py tests/services/test_cv_tokenizer.py
git commit -m "feat: CV-Tokenizer für Pre-Filter-Scoring"
```

---

## Task 9: Pre-Filter Scorer

**Files:**
- Create: `services/job_matching/prefilter.py`
- Test: `tests/services/test_prefilter.py`

- [ ] **Step 1: Failing-Test schreiben**

```python
from services.job_matching.cv_tokenizer import CVTokens
from services.job_matching.prefilter import score_job, PrefilterContext


def _ctx(language_filter=None, region_filter=None):
    return PrefilterContext(
        language_filter=language_filter or ["de", "en"],
        region_filter=region_filter,
    )


def test_score_high_for_full_overlap():
    cv = CVTokens(
        skills={"react", "typescript", "python"},
        titles={"senior frontend developer"},
        freetext={"javascript", "node.js"},
    )
    job = {
        "title": "Senior Frontend Developer (React/TypeScript)",
        "description": "Wir suchen mit React, TypeScript und Python. JavaScript-Profi.",
        "location": "Berlin",
    }
    score = score_job(cv, job, _ctx())
    assert score >= 70

def test_score_low_for_no_overlap():
    cv = CVTokens(skills={"java", "spring"})
    job = {"title": "Designer", "description": "Figma, Adobe XD", "location": "Hamburg"}
    score = score_job(cv, job, _ctx())
    assert score < 20

def test_region_filter_drops_score_to_zero():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev", "description": "React", "location": "München, 80331"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10", "11"], "remote_ok": False})
    assert score_job(cv, job, ctx) == 0

def test_remote_ok_overrides_region_filter():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev (Remote)", "description": "React, fully remote", "location": "Munich"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10"], "remote_ok": True})
    assert score_job(cv, job, ctx) > 0
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/job_matching/prefilter.py`**

```python
"""Lokales Keyword-Scoring (Pre-Filter vor Claude-Match).

Score-Logik:
- Skill-Overlap: × 3 Gewichtung
- Titel-Overlap: × 2
- Freetext-Overlap: × 1
- Normalisiert auf 0-100 (Anteil des CV-Token-Pools, der im Job vorkommt)

Negative Filter (Score = 0):
- Region-Filter (PLZ-Präfix) und nicht "Remote"
- Sprache-Filter (Heuristik: deutsche/englische Wörter im Titel)
"""
import re
from dataclasses import dataclass

from services.job_matching.cv_tokenizer import CVTokens


_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9\.\+#]{2,}")
_REMOTE_RE = re.compile(r"\bremote\b|\bhomeoffice\b|fully\s+remote", re.IGNORECASE)
_PLZ_RE = re.compile(r"\b\d{5}\b")


@dataclass
class PrefilterContext:
    language_filter: list  # z.B. ["de", "en"]
    region_filter: dict | None  # z.B. {"plz_prefixes": ["10","11"], "remote_ok": True}


def _tokenize(text: str) -> set:
    return {m.group().lower() for m in _TOKEN_RE.finditer(text or "")}


def _matches_region(job: dict, region: dict) -> bool:
    text = f"{job.get('location') or ''} {job.get('description') or ''}"

    if region.get("remote_ok") and _REMOTE_RE.search(text):
        return True

    prefixes = region.get("plz_prefixes") or []
    if not prefixes:
        return True
    plzs = _PLZ_RE.findall(text)
    return any(plz.startswith(p) for plz in plzs for p in prefixes)


def _detect_language(job: dict) -> str:
    text = (job.get("title") or "").lower()
    de_markers = ["entwickler", "stelle", "berater", "leiter", "kaufmann", "kauffrau", "ingenieur"]
    if any(m in text for m in de_markers):
        return "de"
    return "en"  # default


def score_job(cv: CVTokens, job: dict, ctx: PrefilterContext) -> float:
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
    cv_size = max(len(cv.skills) * 3 + len(cv.titles) * 2 + len(cv.freetext), 1)
    pct = min(raw_score / cv_size, 1.0) * 100
    return round(pct, 2)
```

- [ ] **Step 4: Tests passen**

```bash
pytest tests/services/test_prefilter.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/prefilter.py tests/services/test_prefilter.py
git commit -m "feat: Pre-Filter Scorer (Keyword-basiert mit Sprach/Region-Filter)"
```

---

## Task 10: Source-Adapter Base + RSS

**Files:**
- Create: `services/job_sources/__init__.py`
- Create: `services/job_sources/base.py`
- Create: `services/job_sources/rss.py`
- Test: `tests/services/test_job_sources_rss.py`

- [ ] **Step 1: Dependency hinzufügen**

`requirements.txt` öffnen, ergänzen falls nicht vorhanden:
```
feedparser>=6.0
responses>=0.24
```
Dann:
```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Failing-Test**

```python
from pathlib import Path
import responses
from services.job_sources.rss import RssAdapter
from services.job_sources.base import FetchedJob


FIXTURE = Path(__file__).parent.parent / "fixtures" / "rss_stepstone_sample.xml"


@responses.activate
def test_rss_adapter_parses_two_jobs():
    rss_xml = FIXTURE.read_text()
    responses.add(responses.GET, "https://example.com/feed.xml", body=rss_xml,
                  content_type="application/rss+xml", status=200)

    adapter = RssAdapter(config={"url": "https://example.com/feed.xml"})
    jobs = adapter.fetch()

    assert len(jobs) == 2
    assert isinstance(jobs[0], FetchedJob)
    assert jobs[0].external_id == "stepstone-12345"
    assert "Senior Frontend" in jobs[0].title
    assert jobs[0].url == "https://www.stepstone.de/jobs/senior-frontend-12345"
```

- [ ] **Step 3: Tests laufen, schlagen fehl**

- [ ] **Step 4: Base-Class schreiben**

`services/job_sources/base.py`:
```python
"""Base-Class für Job-Source-Adapter."""
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class FetchedJob:
    """Strukturiertes Roh-Result aus einer Source."""
    external_id: str
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)


class JobSourceAdapter(ABC):
    """Abstract Adapter; jede Source implementiert fetch()."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch(self) -> list[FetchedJob]:
        """Lädt aktuelle Jobs von der Quelle. Wirft bei HTTP-Fehler."""
        raise NotImplementedError
```

- [ ] **Step 5: RSS-Adapter schreiben**

`services/job_sources/rss.py`:
```python
"""RSS/Atom-Feed Adapter."""
import feedparser
from datetime import datetime
from time import mktime

from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.ssrf_guard import validate_rss_url


class RssAdapter(JobSourceAdapter):
    """Liest beliebige RSS/Atom-Feeds.

    Config-Schema:
        {"url": "https://example.com/feed.xml"}
    """

    def fetch(self) -> list[FetchedJob]:
        url = self.config.get("url")
        if not url:
            raise ValueError("RSS config requires 'url'")

        validate_rss_url(url)

        parsed = feedparser.parse(url)
        if parsed.bozo and parsed.entries == []:
            raise RuntimeError(f"RSS-Parse-Fehler: {parsed.bozo_exception}")

        jobs = []
        for e in parsed.entries:
            posted_at = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                posted_at = datetime.fromtimestamp(mktime(e.published_parsed))

            external_id = getattr(e, 'id', None) or getattr(e, 'guid', None) or e.link
            jobs.append(FetchedJob(
                external_id=str(external_id),
                title=e.title,
                url=e.link,
                description=getattr(e, 'description', None) or getattr(e, 'summary', None),
                location=getattr(e, 'category', None),
                posted_at=posted_at,
                raw=dict(e),
            ))
        return jobs
```

- [ ] **Step 6: Registry**

`services/job_sources/__init__.py`:
```python
from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
# Adzuna, Bundesagentur, Arbeitnow folgen in Tasks 11-13


def get_adapter(source_type: str, config: dict) -> JobSourceAdapter:
    registry = {
        "rss": RssAdapter,
        # 'adzuna': AdzunaAdapter,
        # 'bundesagentur': BundesagenturAdapter,
        # 'arbeitnow': ArbeitnowAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    return cls(config)
```

- [ ] **Step 7: Test passt**

```bash
pytest tests/services/test_job_sources_rss.py -v
```

- [ ] **Step 8: Commit**

```bash
git add services/job_sources/ tests/services/test_job_sources_rss.py requirements.txt
git commit -m "feat: Job-Source Adapter-Base + RSS-Implementierung"
```

---

## Task 11: Adzuna-Adapter

**Files:**
- Create: `services/job_sources/adzuna.py`
- Modify: `services/job_sources/__init__.py`
- Test: `tests/services/test_job_sources_adzuna.py`

- [ ] **Step 1: Failing-Test**

```python
import json
from pathlib import Path
import responses
from services.job_sources.adzuna import AdzunaAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "adzuna_response.json"


@responses.activate
def test_adzuna_adapter_parses():
    responses.add(
        responses.GET,
        "https://api.adzuna.com/v1/api/jobs/de/search/1",
        json=json.loads(FIX.read_text()),
        status=200,
    )

    adapter = AdzunaAdapter(config={
        "app_id": "id123", "app_key": "key456",
        "country": "de", "what": "react", "where": "Berlin",
        "results_per_page": 50,
    })
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "1234567890"
    assert jobs[0].company == "ACME GmbH"
    assert jobs[0].location == "Berlin"
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/job_sources/adzuna.py`**

```python
"""Adzuna-API-Adapter (https://developer.adzuna.com)."""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class AdzunaAdapter(JobSourceAdapter):
    """Config:
        {"app_id":"...","app_key":"...","country":"de",
         "what":"frontend","where":"Berlin","results_per_page":50}
    """
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def fetch(self) -> list[FetchedJob]:
        c = self.config
        if not (c.get("app_id") and c.get("app_key") and c.get("country")):
            raise ValueError("Adzuna config requires app_id, app_key, country")

        url = f"{self.BASE_URL}/{c['country']}/search/1"
        params = {
            "app_id": c["app_id"],
            "app_key": c["app_key"],
            "results_per_page": c.get("results_per_page", 50),
            "what": c.get("what", ""),
            "where": c.get("where", ""),
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs = []
        for item in data.get("results", []):
            posted = None
            if item.get("created"):
                try:
                    posted = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
                except Exception:
                    pass

            jobs.append(FetchedJob(
                external_id=str(item["id"]),
                title=item.get("title", ""),
                url=item.get("redirect_url", ""),
                company=(item.get("company") or {}).get("display_name"),
                location=(item.get("location") or {}).get("display_name"),
                description=item.get("description"),
                posted_at=posted,
                raw=item,
            ))
        return jobs
```

- [ ] **Step 4: Im Registry registrieren**

In `services/job_sources/__init__.py`:
```python
from services.job_sources.adzuna import AdzunaAdapter
# Registry um 'adzuna' ergänzen:
# 'adzuna': AdzunaAdapter,
```

- [ ] **Step 5: Test passt + Commit**

```bash
pytest tests/services/test_job_sources_adzuna.py -v
git add services/job_sources/adzuna.py services/job_sources/__init__.py tests/services/test_job_sources_adzuna.py
git commit -m "feat: Adzuna-API Adapter"
```

---

## Task 12: Bundesagentur-Adapter

**Files:**
- Create: `services/job_sources/bundesagentur.py`
- Modify: `services/job_sources/__init__.py`
- Test: `tests/services/test_job_sources_bundesagentur.py`

> **API-Doku:** https://jobsuche.api.bund.dev/  
> Endpoint: `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs`  
> Header: `X-API-Key: jobboerse-jobsuche` (offizieller Public-Key)

- [ ] **Step 1: Failing-Test**

```python
import json
from pathlib import Path
import responses
from services.job_sources.bundesagentur import BundesagenturAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "bundesagentur_response.json"


@responses.activate
def test_bundesagentur_parses():
    responses.add(
        responses.GET,
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = BundesagenturAdapter(config={"was": "Frontend", "wo": "10115", "umkreis": 25})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "10000-1234567890-S"
    assert jobs[0].company == "Tech Solutions GmbH"
    assert "Berlin" in jobs[0].location
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `bundesagentur.py`**

```python
"""Bundesagentur Jobsuche-API (offiziell, kostenlos).

Doku: https://jobsuche.api.bund.dev/
"""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class BundesagenturAdapter(JobSourceAdapter):
    URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
    HEADERS = {"X-API-Key": "jobboerse-jobsuche"}

    def fetch(self) -> list[FetchedJob]:
        params = {
            "was": self.config.get("was", ""),
            "wo": self.config.get("wo", ""),
            "umkreis": self.config.get("umkreis", 25),
            "size": 50,
        }
        if self.config.get("arbeitszeit"):
            params["arbeitszeit"] = self.config["arbeitszeit"]

        r = requests.get(self.URL, params=params, headers=self.HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs = []
        for item in data.get("stellenangebote", []):
            posted = None
            if item.get("aktuelleVeroeffentlichungsdatum"):
                try:
                    posted = datetime.fromisoformat(item["aktuelleVeroeffentlichungsdatum"])
                except Exception:
                    pass

            ort = item.get("arbeitsort") or {}
            location = ", ".join(filter(None, [
                ort.get("plz"), ort.get("ort"), ort.get("region")
            ]))

            external_url = item.get("externeUrl") or \
                f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{item['refnr']}"

            jobs.append(FetchedJob(
                external_id=item["refnr"],
                title=item.get("titel") or item.get("beruf", ""),
                url=external_url,
                company=item.get("arbeitgeber"),
                location=location,
                description=None,
                posted_at=posted,
                raw=item,
            ))
        return jobs
```

- [ ] **Step 4: Registrieren + Test + Commit**

In `services/job_sources/__init__.py` Registry erweitern.
```bash
pytest tests/services/test_job_sources_bundesagentur.py -v
git add services/job_sources/bundesagentur.py services/job_sources/__init__.py tests/services/test_job_sources_bundesagentur.py
git commit -m "feat: Bundesagentur Jobsuche-API Adapter"
```

---

## Task 13: Arbeitnow-Adapter

**Files:**
- Create: `services/job_sources/arbeitnow.py`
- Modify: `services/job_sources/__init__.py`
- Test: `tests/services/test_job_sources_arbeitnow.py`

> **API-Doku:** https://documenter.getpostman.com/view/18545278/UVJbJdKh  
> Endpoint: `https://www.arbeitnow.com/api/job-board-api`

- [ ] **Step 1: Failing-Test**

```python
import json
from pathlib import Path
import responses
from services.job_sources.arbeitnow import ArbeitnowAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "arbeitnow_response.json"


@responses.activate
def test_arbeitnow_parses_and_filters_tags():
    responses.add(responses.GET, "https://www.arbeitnow.com/api/job-board-api",
                  json=json.loads(FIX.read_text()), status=200)
    adapter = ArbeitnowAdapter(config={"tags": ["javascript"]})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "senior-react-engineer-acme"
    assert "Berlin" in jobs[0].location

@responses.activate
def test_arbeitnow_tag_filter_excludes():
    responses.add(responses.GET, "https://www.arbeitnow.com/api/job-board-api",
                  json=json.loads(FIX.read_text()), status=200)
    adapter = ArbeitnowAdapter(config={"tags": ["python"]})
    assert len(adapter.fetch()) == 0
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: `arbeitnow.py`**

```python
"""Arbeitnow-API (kostenlos, keine Auth)."""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class ArbeitnowAdapter(JobSourceAdapter):
    URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self) -> list[FetchedJob]:
        r = requests.get(self.URL, timeout=15)
        r.raise_for_status()
        data = r.json()

        wanted_tags = set(t.lower() for t in self.config.get("tags") or [])
        require_visa = self.config.get("visa_sponsorship") is True

        jobs = []
        for item in data.get("data", []):
            tags = set(t.lower() for t in item.get("tags") or [])
            if wanted_tags and not (wanted_tags & tags):
                continue
            if require_visa and not item.get("visa_sponsorship"):
                continue

            posted = None
            if item.get("created_at"):
                try:
                    posted = datetime.fromtimestamp(int(item["created_at"]))
                except Exception:
                    pass

            jobs.append(FetchedJob(
                external_id=item.get("slug"),
                title=item.get("title", ""),
                url=item.get("url", ""),
                company=item.get("company_name"),
                location=item.get("location"),
                description=item.get("description"),
                posted_at=posted,
                raw=item,
            ))
        return jobs
```

- [ ] **Step 4: Registrieren + Test + Commit**

```bash
pytest tests/services/test_job_sources_arbeitnow.py -v
git add services/job_sources/arbeitnow.py services/job_sources/__init__.py tests/services/test_job_sources_arbeitnow.py
git commit -m "feat: Arbeitnow-API Adapter"
```

---

## Task 14: Cron-Token Auth-Decorator

**Files:**
- Create: `services/cron_auth.py`
- Test: `tests/services/test_cron_auth.py`

- [ ] **Step 1: Failing-Test**

```python
import os
from flask import Flask
from services.cron_auth import require_cron_token


def make_app(monkeypatch, token=None):
    if token is not None:
        monkeypatch.setenv("JOB_CRON_TOKEN", token)
    app = Flask(__name__)
    @app.post("/cron/test")
    @require_cron_token
    def cron_endpoint():
        return {"ok": True}
    return app


def test_blocks_without_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    client = app.test_client()
    r = client.post("/cron/test")
    assert r.status_code == 403

def test_blocks_with_wrong_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "wrong"})
    assert r.status_code == 403

def test_passes_with_correct_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "secret123"})
    assert r.status_code == 200

def test_blocks_when_env_unset(monkeypatch):
    monkeypatch.delenv("JOB_CRON_TOKEN", raising=False)
    app = make_app(monkeypatch, None)
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "anything"})
    assert r.status_code == 503  # Service Unavailable: Server nicht konfiguriert
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/cron_auth.py`**

```python
"""Cron-Token Decorator: schützt Cron-Endpoints via X-Cron-Token Header."""
import os
import hmac
from functools import wraps
from flask import request, jsonify


def require_cron_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("JOB_CRON_TOKEN")
        if not expected:
            return jsonify({"error": "Cron-Token nicht konfiguriert"}), 503

        provided = request.headers.get("X-Cron-Token", "")
        if not hmac.compare_digest(expected, provided):
            return jsonify({"error": "Forbidden"}), 403

        return fn(*args, **kwargs)
    return wrapper
```

- [ ] **Step 4: Test passt + Commit**

```bash
pytest tests/services/test_cron_auth.py -v
git add services/cron_auth.py tests/services/test_cron_auth.py
git commit -m "feat: Cron-Token Auth-Decorator (HMAC-vergleich)"
```

---

## Task 15: Stage 1 — Crawl-Source Endpoint

**Files:**
- Create: `api/jobs_cron.py`
- Modify: `app.py` (Blueprint registrieren)
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test**

```python
import os
import json
from pathlib import Path
import pytest
import responses
from datetime import datetime, timedelta

from app import create_app
from database import db
from models import User, JobSource, RawJob, JobMatch


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@responses.activate
def test_crawl_source_picks_due_source_creates_raw_jobs_and_matches(app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, cv_data_json='{"cv":{"skills":["react"]}}')

    rss_xml = (Path(__file__).parent.parent / "fixtures" / "rss_stepstone_sample.xml").read_text()
    responses.add(responses.GET, "https://example.com/feed.xml",
                  body=rss_xml, content_type="application/rss+xml", status=200)

    src = JobSource(name="Test", type="rss", config={"url": "https://example.com/feed.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src)
    db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["source_id"] == src.id
    assert body["new_jobs"] == 2
    assert body["matches_created"] == 2  # 2 jobs × 1 user

    raw_jobs = RawJob.query.all()
    assert len(raw_jobs) == 2
    matches = JobMatch.query.all()
    assert len(matches) == 2
    assert all(m.user_id == user.id for m in matches)
    assert all(m.status == "new" for m in matches)


def test_crawl_source_skips_sources_not_due(app, client):
    src = JobSource(name="Recent", type="rss", config={"url": "x"},
                    enabled=True, crawl_interval_min=60,
                    last_crawled_at=datetime.utcnow() - timedelta(minutes=5))
    db.session.add(src); db.session.commit()
    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    assert r.get_json()["source_id"] is None
    assert r.get_json()["reason"] == "no_source_due"


@responses.activate
def test_crawl_source_records_error_and_increments_failures(app, client):
    responses.add(responses.GET, "https://example.com/broken.xml", status=500)
    src = JobSource(name="Broken", type="rss", config={"url": "https://example.com/broken.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src); db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    db.session.refresh(src)
    assert src.consecutive_failures == 1
    assert src.last_error is not None
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: Blueprint schreiben**

`api/jobs_cron.py`:
```python
"""Cron-Endpoints für Job-Discovery Pipeline (Token-geschützt)."""
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify

from database import db
from models import User, JobSource, RawJob, JobMatch
from services.cron_auth import require_cron_token
from services.job_sources import get_adapter


jobs_cron_bp = Blueprint('jobs_cron', __name__, url_prefix='/api/jobs')

# Tick-Limits
MAX_NEW_JOBS_PER_TICK = 50
HARD_TIME_LIMIT_SEC = 25
AUTO_DISABLE_FAILURE_COUNT = 5


def _select_due_source() -> JobSource | None:
    cutoff_subquery = db.session.query(JobSource).filter(JobSource.enabled == True)
    candidates = cutoff_subquery.all()
    now = datetime.utcnow()
    due = [
        s for s in candidates
        if s.last_crawled_at is None
        or (s.last_crawled_at + timedelta(minutes=s.crawl_interval_min)) <= now
    ]
    if not due:
        return None
    due.sort(key=lambda s: s.last_crawled_at or datetime.min)
    return due[0]


def _eligible_users_for_source(source: JobSource) -> list[User]:
    """Match-fähige User: aktiv + Job-Discovery ON + CV vorhanden.

    Bei user-eigener Quelle: nur der Owner.
    Bei globaler Quelle: alle eligible User.
    """
    q = User.query.filter(
        User.is_active == True,
        User.job_discovery_enabled == True,
        User.cv_data_json.isnot(None),
    )
    if source.user_id is not None:
        q = q.filter(User.id == source.user_id)
    return q.all()


@jobs_cron_bp.post('/crawl-source')
@require_cron_token
def crawl_source():
    started = time.time()
    src = _select_due_source()
    if src is None:
        return jsonify({"source_id": None, "reason": "no_source_due"}), 200

    src.last_crawled_at = datetime.utcnow()

    try:
        adapter = get_adapter(src.type, src.config)
        fetched = adapter.fetch()
    except Exception as e:
        src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
        src.consecutive_failures += 1
        if src.consecutive_failures >= AUTO_DISABLE_FAILURE_COUNT:
            src.enabled = False
        db.session.commit()
        return jsonify({"source_id": src.id, "error": src.last_error,
                        "consecutive_failures": src.consecutive_failures,
                        "auto_disabled": not src.enabled}), 200

    src.last_error = None
    src.consecutive_failures = 0

    eligible_users = _eligible_users_for_source(src)
    new_jobs = 0
    matches_created = 0

    for fj in fetched[:MAX_NEW_JOBS_PER_TICK]:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        existing = RawJob.query.filter_by(source_id=src.id, external_id=fj.external_id).first()
        if existing:
            continue

        raw = RawJob(
            source_id=src.id,
            external_id=fj.external_id,
            title=fj.title,
            company=fj.company,
            location=fj.location,
            url=fj.url,
            description=fj.description,
            posted_at=fj.posted_at,
            crawl_status='raw',
        )
        raw.raw_payload = fj.raw
        db.session.add(raw)
        db.session.flush()
        new_jobs += 1

        for user in eligible_users:
            db.session.add(JobMatch(
                raw_job_id=raw.id, user_id=user.id, status='new'
            ))
            matches_created += 1

    db.session.commit()

    return jsonify({
        "source_id": src.id,
        "new_jobs": new_jobs,
        "matches_created": matches_created,
        "duration_sec": round(time.time() - started, 2),
    }), 200
```

- [ ] **Step 4: Blueprint in `app.py` registrieren**

Im `app.py` bei den Blueprint-Imports ergänzen:
```python
from api.jobs_cron import jobs_cron_bp
app.register_blueprint(jobs_cron_bp)
```

- [ ] **Step 5: Tests passen**

```bash
mkdir -p tests/api
touch tests/api/__init__.py
pytest tests/api/test_jobs_cron.py::test_crawl_source_picks_due_source_creates_raw_jobs_and_matches -v
pytest tests/api/test_jobs_cron.py -v
```

- [ ] **Step 6: Commit**

```bash
git add api/jobs_cron.py app.py tests/api/test_jobs_cron.py
git commit -m "feat: Stage 1 Crawl-Source Endpoint mit Auto-Disable bei 5x Fehler"
```

---

## Task 16: Stage 2 — Pre-Filter Endpoint

**Files:**
- Modify: `api/jobs_cron.py`
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test ergänzen**

```python
def test_prefilter_scores_pending_matches(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react", "typescript"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Senior React Developer", description="React, TypeScript, Berlin",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    r = client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["scored"] == 1

    m = JobMatch.query.first()
    assert m.prefilter_score is not None
    assert m.prefilter_score > 0


def test_prefilter_dismisses_low_scores(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["python"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Designer", description="Figma",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    m = JobMatch.query.first()
    assert m.status == 'dismissed'
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: Stage-2-Endpoint in `api/jobs_cron.py` ergänzen**

```python
import json
from services.job_matching.cv_tokenizer import tokenize_cv
from services.job_matching.prefilter import score_job, PrefilterContext

MAX_PREFILTER_PER_TICK = 100
PREFILTER_DISMISS_THRESHOLD = 30


@jobs_cron_bp.post('/prefilter')
@require_cron_token
def prefilter():
    started = time.time()
    pending = (JobMatch.query
               .filter(JobMatch.prefilter_score.is_(None), JobMatch.status == 'new')
               .limit(MAX_PREFILTER_PER_TICK).all())

    cv_cache: dict[str, any] = {}
    ctx_cache: dict[str, PrefilterContext] = {}
    scored = 0
    dismissed = 0

    for match in pending:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if match.user_id not in cv_cache:
            user = User.query.get(match.user_id)
            cv_data = json.loads(user.cv_data_json) if user.cv_data_json else {}
            cv_cache[match.user_id] = tokenize_cv(cv_data)
            ctx_cache[match.user_id] = PrefilterContext(
                language_filter=user.job_language_filter,
                region_filter=user.job_region_filter,
            )

        raw = RawJob.query.get(match.raw_job_id)
        score = score_job(
            cv_cache[match.user_id],
            {"title": raw.title, "description": raw.description, "location": raw.location},
            ctx_cache[match.user_id],
        )
        match.prefilter_score = score
        if score < PREFILTER_DISMISS_THRESHOLD:
            match.status = 'dismissed'
            dismissed += 1
        scored += 1

    # Status der RawJobs auf 'prefiltered' setzen wenn alle Matches gescored
    db.session.commit()
    return jsonify({"scored": scored, "dismissed": dismissed,
                    "duration_sec": round(time.time() - started, 2)}), 200
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/api/test_jobs_cron.py -v
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat: Stage 2 Pre-Filter Endpoint mit Auto-Dismiss <30"
```

---

## Task 17: Stage 3 — Claude-Match Endpoint (Server-Key)

**Files:**
- Create: `services/job_matching/claude_matcher.py`
- Modify: `api/jobs_cron.py`
- Test: `tests/services/test_claude_matcher.py`
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test für Matcher (Mock)**

`tests/services/test_claude_matcher.py`:
```python
from unittest.mock import MagicMock, patch
from services.job_matching.claude_matcher import match_job_with_claude, MatchResult


def test_match_job_returns_structured_result():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 85, "reasoning": "Great fit", "missing_skills": ["k8s"]}')],
        usage=MagicMock(input_tokens=400, output_tokens=80),
    )

    cv_summary = "Senior Frontend Developer, 8 years React/TypeScript"
    job = {"title": "Sr React Dev", "description": "React, TypeScript", "location": "Berlin"}

    result = match_job_with_claude(client=mock_client, model="claude-haiku-4-5",
                                   cv_summary=cv_summary, job=job)
    assert isinstance(result, MatchResult)
    assert result.score == 85
    assert result.reasoning == "Great fit"
    assert "k8s" in result.missing_skills
    assert result.tokens_in == 400
    assert result.tokens_out == 80


def test_match_job_handles_invalid_json():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='not json at all')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    )
    result = match_job_with_claude(client=mock_client, model="claude-haiku-4-5",
                                   cv_summary="x", job={"title": "y", "description": "z"})
    assert result.score == 0
    assert "fehlgeschlagen" in result.reasoning.lower()
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: `services/job_matching/claude_matcher.py`**

```python
"""Claude-basierte Job-Bewertung (Phase A: nutzt Server-Key).

Phase B refactored das auf User-spezifische Provider — die Funktion
`match_job_with_claude` bleibt aber gleich, der `client` und `model`
kommen dann aus der Provider-Factory.
"""
import json as _json
from dataclasses import dataclass


PROMPT_TEMPLATE = """Du bewertest, wie gut die folgende Stellenausschreibung zu meinem CV passt.

MEIN CV (Zusammenfassung):
{cv_summary}

STELLENAUSSCHREIBUNG:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Objekt im Format:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["<skill1>", "<skill2>"]}}

Keine Erläuterungen drum herum. Nur das JSON-Objekt.
"""


@dataclass
class MatchResult:
    score: float
    reasoning: str
    missing_skills: list
    tokens_in: int
    tokens_out: int


def _build_prompt(cv_summary: str, job: dict) -> str:
    return PROMPT_TEMPLATE.format(
        cv_summary=cv_summary[:3000],
        title=job.get("title", ""),
        location=job.get("location", ""),
        description=(job.get("description") or "")[:5000],
    )


def match_job_with_claude(client, model: str, cv_summary: str, job: dict) -> MatchResult:
    """Ruft Claude auf, parst Antwort, gibt MatchResult zurück.

    Bei ungültiger JSON-Antwort: Fallback auf score=0, reasoning="fehlgeschlagen".
    Tokens werden immer geloggt (auch bei Fehler).
    """
    prompt = _build_prompt(cv_summary, job)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    tokens_in = getattr(response.usage, "input_tokens", 0)
    tokens_out = getattr(response.usage, "output_tokens", 0)

    # Best-effort JSON-Extraktion
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json\n").strip()

    try:
        data = _json.loads(text)
        return MatchResult(
            score=float(data.get("score", 0)),
            reasoning=str(data.get("reasoning", "")),
            missing_skills=list(data.get("missing_skills") or []),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:
        return MatchResult(
            score=0,
            reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Claude).",
            missing_skills=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
```

- [ ] **Step 4: Test passt**

```bash
pytest tests/services/test_claude_matcher.py -v
```

- [ ] **Step 5: Stage-3-Endpoint in `api/jobs_cron.py` ergänzen**

```python
import os
from anthropic import Anthropic
from services.job_matching.claude_matcher import match_job_with_claude
from models import ApiCall

DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "claude-haiku-4-5-20251001")
# Sehr grobe Cost-Schätzung; in Phase B durch echtes Modell-Pricing ersetzt
COST_USD_PER_1M_TOKENS_IN = 0.80
COST_USD_PER_1M_TOKENS_OUT = 4.00


def _get_anthropic_client():
    """Phase A: einziger Server-Key. Phase B ersetzt dies durch Factory."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def _estimate_cost_cents(tokens_in: int, tokens_out: int) -> int:
    usd = (tokens_in / 1_000_000 * COST_USD_PER_1M_TOKENS_IN
           + tokens_out / 1_000_000 * COST_USD_PER_1M_TOKENS_OUT)
    return max(1, round(usd * 100))


def _user_today_cost_cents(user_id: str) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (db.session.query(db.func.sum(ApiCall.cost))
            .filter(ApiCall.user_id == user_id, ApiCall.timestamp >= today_start)
            .scalar()) or 0
    return int(round(rows * 100))


def _build_cv_summary(cv_data_json: str) -> str:
    if not cv_data_json:
        return ""
    cv = json.loads(cv_data_json).get("cv") or {}
    parts = []
    if cv.get("summary"):
        parts.append(f"Zusammenfassung: {cv['summary']}")
    if cv.get("skills"):
        parts.append(f"Skills: {', '.join(cv['skills'])}")
    if cv.get("experiences"):
        titles = [e.get("title", "") for e in cv["experiences"][:5]]
        parts.append(f"Letzte Positionen: {' | '.join(titles)}")
    return "\n".join(parts)


@jobs_cron_bp.post('/claude-match')
@require_cron_token
def claude_match():
    started = time.time()
    client = _get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY nicht gesetzt"}), 503

    matched = 0
    skipped_budget = 0

    users_with_pending = (db.session.query(User)
                          .join(JobMatch, JobMatch.user_id == User.id)
                          .filter(JobMatch.match_score.is_(None),
                                  JobMatch.prefilter_score >= PREFILTER_DISMISS_THRESHOLD,
                                  JobMatch.status == 'new')
                          .distinct().all())

    for user in users_with_pending:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget += 1
            continue

        candidates = (JobMatch.query
                      .filter(JobMatch.user_id == user.id,
                              JobMatch.match_score.is_(None),
                              JobMatch.prefilter_score >= PREFILTER_DISMISS_THRESHOLD,
                              JobMatch.status == 'new')
                      .order_by(JobMatch.prefilter_score.desc())
                      .limit(user.job_claude_budget_per_tick).all())

        cv_summary = _build_cv_summary(user.cv_data_json)
        for match in candidates:
            if time.time() - started > HARD_TIME_LIMIT_SEC:
                break
            raw = RawJob.query.get(match.raw_job_id)
            try:
                result = match_job_with_claude(
                    client=client, model=DEFAULT_MODEL, cv_summary=cv_summary,
                    job={"title": raw.title, "description": raw.description, "location": raw.location},
                )
            except Exception as e:
                # Lass match.match_score=NULL für Retry im nächsten Tick
                continue

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
            matched += 1

        db.session.commit()

    return jsonify({"matched": matched, "skipped_budget": skipped_budget,
                    "duration_sec": round(time.time() - started, 2)}), 200
```

- [ ] **Step 6: Integration-Test in `tests/api/test_jobs_cron.py`**

```python
from unittest.mock import patch, MagicMock


@patch("api.jobs_cron._get_anthropic_client")
def test_claude_match_scores_top_n_per_user(mock_factory, app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react"], "summary": "React expert"}}),
        job_claude_budget_per_tick=2,
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    for i in range(5):
        raw = RawJob(source_id=src.id, external_id=f"id-{i}",
                     title=f"React Job {i}", description="React",
                     url=f"https://example.com/{i}", crawl_status='raw')
        db.session.add(raw); db.session.flush()
        db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                                prefilter_score=70 + i))
    db.session.commit()

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 88, "reasoning": "ok", "missing_skills": []}')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    )
    mock_factory.return_value = mock_client

    r = client.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})
    body = r.get_json()
    assert body["matched"] == 2  # nur Top-2 wegen budget_per_tick
    matched = JobMatch.query.filter(JobMatch.match_score.isnot(None)).all()
    assert len(matched) == 2
```

- [ ] **Step 7: Tests passen + Commit**

```bash
pytest tests/api/test_jobs_cron.py tests/services/test_claude_matcher.py -v
git add api/jobs_cron.py services/job_matching/claude_matcher.py tests/services/test_claude_matcher.py tests/api/test_jobs_cron.py
git commit -m "feat: Stage 3 Claude-Match (Server-Key, mit Tagesbudget+Tick-Limit)"
```

---

## Task 18: Stage 4 — Notify Endpoint

**Files:**
- Create: `services/job_matching/notifier.py`
- Modify: `api/jobs_cron.py`
- Test: `tests/services/test_notifier.py`
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test**

`tests/services/test_notifier.py`:
```python
from unittest.mock import patch
from services.job_matching.notifier import send_match_notification


@patch("services.job_matching.notifier._send_push")
def test_send_match_notification_calls_push(mock_push, app, user_factory):
    user = user_factory()
    send_match_notification(user_id=user.id,
                            title="React Senior Job",
                            company="ACME",
                            score=92,
                            url="https://example.com/job/1")
    assert mock_push.called
    args = mock_push.call_args
    assert "React" in args[1]["body"]
    assert "92" in args[1]["body"]
```

In `tests/api/test_jobs_cron.py`:
```python
@patch("services.job_matching.notifier._send_push")
def test_notify_sends_for_high_score_only(mock_push, app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, job_notification_threshold=80)
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                            prefilter_score=80, match_score=85))
    raw2 = RawJob(source_id=src.id, external_id="2", title="t", url="x", crawl_status='matched')
    db.session.add(raw2); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw2.id, user_id=user.id, status='new',
                            prefilter_score=70, match_score=70))
    db.session.commit()

    r = client.post("/api/jobs/notify", headers={"X-Cron-Token": "test-token"})
    assert r.get_json()["notified"] == 1
    assert mock_push.call_count == 1
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: `services/job_matching/notifier.py`**

```python
"""Push-Notifications für Match-Treffer.

Phase A: Stub mit print + DB-Eintrag in einer optionalen 'notifications' Tabelle.
Falls bestehender Notification-Service existiert (Web-Push, FCM), hier integrieren.
"""
import logging

logger = logging.getLogger(__name__)


def _send_push(user_id: str, title: str, body: str, url: str | None = None):
    """Hooks for tests + production push.

    Wird durch echten Push-Service ersetzt. Aktuell loggt nur.
    """
    logger.info("PUSH user=%s title=%r body=%r url=%s", user_id, title, body, url)


def send_match_notification(user_id: str, title: str, company: str | None,
                             score: float, url: str):
    body = f"Match {score:.0f}: {title}" + (f" @ {company}" if company else "")
    _send_push(user_id=user_id, title="Neuer Job-Vorschlag", body=body, url=url)
```

- [ ] **Step 4: Stage-4-Endpoint in `api/jobs_cron.py`**

```python
from services.job_matching.notifier import send_match_notification

MAX_NOTIFICATIONS_PER_TICK = 20


@jobs_cron_bp.post('/notify')
@require_cron_token
def notify():
    started = time.time()

    candidates = (db.session.query(JobMatch, RawJob, User)
                  .join(RawJob, RawJob.id == JobMatch.raw_job_id)
                  .join(User, User.id == JobMatch.user_id)
                  .filter(JobMatch.notified_at.is_(None),
                          JobMatch.status == 'new',
                          JobMatch.match_score.isnot(None))
                  .all())

    notified = 0
    for match, raw, user in candidates:
        if notified >= MAX_NOTIFICATIONS_PER_TICK:
            break
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break
        if match.match_score < user.job_notification_threshold:
            continue

        send_match_notification(
            user_id=user.id, title=raw.title, company=raw.company,
            score=match.match_score, url=raw.url,
        )
        match.notified_at = datetime.utcnow()
        notified += 1

    db.session.commit()
    return jsonify({"notified": notified, "duration_sec": round(time.time() - started, 2)}), 200
```

- [ ] **Step 5: Tests passen + Commit**

```bash
pytest tests/services/test_notifier.py tests/api/test_jobs_cron.py -v
git add services/job_matching/notifier.py api/jobs_cron.py tests/services/test_notifier.py tests/api/test_jobs_cron.py
git commit -m "feat: Stage 4 Notify Endpoint mit Threshold-Filter"
```

---

## Task 19: Stage 5 — Cleanup Endpoint

**Files:**
- Modify: `api/jobs_cron.py`
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test**

```python
def test_cleanup_archives_old_unused_raw_jobs(app, client):
    from datetime import timedelta
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    old_raw = RawJob(source_id=src.id, external_id="old", title="t", url="x",
                     crawl_status='matched',
                     created_at=datetime.utcnow() - timedelta(days=70))
    new_raw = RawJob(source_id=src.id, external_id="new", title="t", url="x",
                     crawl_status='matched')
    db.session.add_all([old_raw, new_raw]); db.session.commit()

    r = client.post("/api/jobs/cleanup", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["archived_raw_jobs"] == 1

    db.session.refresh(old_raw)
    assert old_raw.crawl_status == 'archived'
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: Stage-5-Endpoint**

```python
ARCHIVE_AFTER_DAYS = 60


@jobs_cron_bp.post('/cleanup')
@require_cron_token
def cleanup():
    cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)

    # Archiviere alte RawJobs ohne aktive new/imported-Matches
    candidates = RawJob.query.filter(
        RawJob.created_at < cutoff,
        RawJob.crawl_status != 'archived',
    ).all()

    archived = 0
    for raw in candidates:
        active = JobMatch.query.filter(
            JobMatch.raw_job_id == raw.id,
            JobMatch.status.in_(['new', 'imported']),
        ).count()
        if active == 0:
            raw.crawl_status = 'archived'
            archived += 1

    # Reset consecutive_failures für Quellen die seit 7 Tagen kein Error hatten
    src_cutoff = datetime.utcnow() - timedelta(days=7)
    healthy_sources = JobSource.query.filter(
        JobSource.last_error.is_(None),
        JobSource.consecutive_failures > 0,
        JobSource.updated_at < src_cutoff,
    ).all()
    for s in healthy_sources:
        s.consecutive_failures = 0

    db.session.commit()
    return jsonify({"archived_raw_jobs": archived,
                    "reset_failure_counters": len(healthy_sources)}), 200
```

- [ ] **Step 4: Test passt + Commit**

```bash
pytest tests/api/test_jobs_cron.py -v
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat: Stage 5 Cleanup Endpoint (60d-Archive + Failure-Reset)"
```

---

## Task 20: User-API — Quellen-Verwaltung

**Files:**
- Create: `api/jobs_user.py`
- Modify: `app.py`
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Failing-Test**

`tests/api/test_jobs_user.py`:
```python
import pytest
import json
from app import create_app
from database import db
from models import JobSource


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app, user_factory):
    """JWT-Header: nutzt das bestehende Auth-System."""
    from services.auth_service import create_session_token  # bestehender Service
    user = user_factory()
    token = create_session_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_list_sources_returns_global_and_own(client, app, user_factory, auth_header):
    headers, user = auth_header
    db.session.add(JobSource(name="Global1", type="rss", config={"url": "x"}))
    db.session.add(JobSource(name="Mine", type="rss", config={"url": "y"}, user_id=user.id))
    db.session.add(JobSource(name="Other-User", type="rss", config={"url": "z"}, user_id="other-uuid"))
    db.session.commit()

    r = client.get("/api/jobs/sources", headers=headers)
    body = r.get_json()
    names = [s["name"] for s in body["sources"]]
    assert "Global1" in names
    assert "Mine" in names
    assert "Other-User" not in names


def test_create_own_source(client, auth_header):
    headers, user = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "My RSS", "type": "rss", "config": {"url": "https://example.com/feed.xml"},
        "crawl_interval_min": 30,
    }, headers=headers)
    assert r.status_code == 201
    src = JobSource.query.filter_by(user_id=user.id).first()
    assert src.name == "My RSS"


def test_create_source_validates_ssrf(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Hack", "type": "rss", "config": {"url": "http://localhost/feed"},
    }, headers=headers)
    assert r.status_code == 400
    assert "URL" in r.get_json()["error"]


def test_user_cannot_modify_global_source(client, auth_header):
    headers, _ = auth_header
    g = JobSource(name="Global", type="rss", config={"url": "x"})
    db.session.add(g); db.session.commit()
    r = client.patch(f"/api/jobs/sources/{g.id}", json={"enabled": False}, headers=headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: Bestehende Auth-Pattern checken**

Schau in `api/applications.py` oder `api/profile.py` nach, wie `@require_auth` oder `g.user_id` benutzt wird, und nutze exakt dasselbe Pattern.

```bash
grep -n "require_auth\|@auth_required\|g.user_id" api/*.py | head -20
```

- [ ] **Step 4: `api/jobs_user.py` schreiben**

```python
"""User-facing Job-Discovery Endpoints (JWT-geschützt)."""
from flask import Blueprint, request, jsonify, g

from database import db
from models import JobSource, RawJob, JobMatch, Application
from services.ssrf_guard import is_url_safe_for_rss
from services.auth_service import require_auth  # bestehend, ggf. Pfad anpassen


jobs_user_bp = Blueprint('jobs_user', __name__, url_prefix='/api/jobs')


_VALID_TYPES = {"rss", "adzuna", "bundesagentur", "arbeitnow"}


def _validate_config(source_type: str, config: dict) -> str | None:
    """Returns Fehlermeldung oder None bei OK."""
    if source_type == "rss":
        url = (config or {}).get("url")
        if not url or not isinstance(url, str):
            return "RSS-Config benötigt 'url' (string)"
        if not is_url_safe_for_rss(url):
            return f"URL nicht erlaubt (private/lokale IP): {url}"
    elif source_type == "adzuna":
        for k in ("app_id", "app_key", "country"):
            if not (config or {}).get(k):
                return f"Adzuna-Config benötigt '{k}'"
    elif source_type == "bundesagentur":
        if not (config or {}).get("was") and not (config or {}).get("wo"):
            return "Bundesagentur-Config benötigt mindestens 'was' oder 'wo'"
    elif source_type == "arbeitnow":
        pass  # alle Felder optional
    return None


def _serialize_source(s: JobSource) -> dict:
    return {
        "id": s.id, "name": s.name, "type": s.type, "config": s.config,
        "enabled": s.enabled, "crawl_interval_min": s.crawl_interval_min,
        "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
        "last_error": s.last_error, "consecutive_failures": s.consecutive_failures,
        "is_global": s.user_id is None,
        "is_own": s.user_id == g.user_id,
    }


@jobs_user_bp.get('/sources')
@require_auth
def list_sources():
    sources = JobSource.query.filter(
        (JobSource.user_id.is_(None)) | (JobSource.user_id == g.user_id)
    ).order_by(JobSource.name).all()
    return jsonify({"sources": [_serialize_source(s) for s in sources]}), 200


@jobs_user_bp.post('/sources')
@require_auth
def create_source():
    data = request.get_json() or {}
    if data.get("type") not in _VALID_TYPES:
        return jsonify({"error": f"type muss eines von {_VALID_TYPES} sein"}), 400
    if not data.get("name"):
        return jsonify({"error": "name fehlt"}), 400

    err = _validate_config(data["type"], data.get("config") or {})
    if err:
        return jsonify({"error": err}), 400

    src = JobSource(
        user_id=g.user_id,
        name=data["name"],
        type=data["type"],
        enabled=data.get("enabled", True),
        crawl_interval_min=data.get("crawl_interval_min", 60),
    )
    src.config = data.get("config") or {}
    db.session.add(src)
    db.session.commit()
    return jsonify({"source": _serialize_source(src)}), 201


@jobs_user_bp.patch('/sources/<int:source_id>')
@require_auth
def update_source(source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    if "name" in data:
        src.name = data["name"]
    if "enabled" in data:
        src.enabled = bool(data["enabled"])
    if "crawl_interval_min" in data:
        src.crawl_interval_min = int(data["crawl_interval_min"])
    if "config" in data:
        err = _validate_config(src.type, data["config"])
        if err:
            return jsonify({"error": err}), 400
        src.config = data["config"]
    db.session.commit()
    return jsonify({"source": _serialize_source(src)}), 200


@jobs_user_bp.delete('/sources/<int:source_id>')
@require_auth
def delete_source(source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(src)
    db.session.commit()
    return ('', 204)


@jobs_user_bp.post('/sources/<int:source_id>/test-crawl')
@require_auth
def test_crawl_source(source_id: int):
    """Manueller Test-Crawl für eine Quelle (synchron, ohne Persistierung)."""
    from services.job_sources import get_adapter
    src = JobSource.query.get_or_404(source_id)
    if src.user_id is not None and src.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        adapter = get_adapter(src.type, src.config)
        jobs = adapter.fetch()
        return jsonify({"ok": True, "found_jobs": len(jobs),
                        "sample_titles": [j.title for j in jobs[:5]]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200
```

- [ ] **Step 5: Blueprint in `app.py` registrieren**

Ergänze in `app.py`:
```python
from api.jobs_user import jobs_user_bp
app.register_blueprint(jobs_user_bp)
```

- [ ] **Step 6: Tests passen + Commit**

```bash
pytest tests/api/test_jobs_user.py -v
git add api/jobs_user.py app.py tests/api/test_jobs_user.py
git commit -m "feat: User-API für Job-Source Verwaltung (CRUD + Test-Crawl)"
```

---

## Task 21: User-API — Match-Listing & Status-Updates

**Files:**
- Modify: `api/jobs_user.py`
- Test: `tests/api/test_jobs_user.py`

- [ ] **Step 1: Failing-Tests**

```python
def test_list_matches_filters_by_score_and_status(client, app, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()

    for i, score in enumerate([90, 75, 50, 30]):
        raw = RawJob(source_id=src.id, external_id=f"id-{i}", title=f"Job {i}",
                     url="x", crawl_status='matched')
        db.session.add(raw); db.session.flush()
        db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id,
                                status='new', match_score=score, prefilter_score=80))
    db.session.commit()

    r = client.get("/api/jobs/matches?min_score=70&status=new", headers=headers)
    body = r.get_json()
    assert len(body["matches"]) == 2  # 90 und 75
    assert body["matches"][0]["match_score"] == 90  # sorted DESC


def test_patch_match_status(client, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    db.session.add(m); db.session.commit()

    r = client.patch(f"/api/jobs/matches/{m.id}", json={"status": "dismissed"}, headers=headers)
    assert r.status_code == 200
    db.session.refresh(m)
    assert m.status == "dismissed"


def test_import_match_creates_application(client, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="React Dev", company="ACME",
                 location="Berlin", url="https://example.com/job", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=85, match_reasoning="Toller Match")
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    assert "application_id" in body
    db.session.refresh(m)
    assert m.status == "imported"
    assert m.imported_application_id == body["application_id"]
    app_obj = Application.query.get(body["application_id"])
    assert app_obj.user_id == user.id
    assert "ACME" in app_obj.firma
    assert "85" in (app_obj.notizen or "")
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: Endpoints in `api/jobs_user.py` ergänzen**

```python
def _serialize_match(m: JobMatch, raw: RawJob, src: JobSource) -> dict:
    return {
        "id": m.id,
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
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


@jobs_user_bp.get('/matches')
@require_auth
def list_matches():
    min_score = request.args.get('min_score', type=float, default=0)
    status_filter = request.args.getlist('status') or ['new']
    source_id = request.args.get('source_id', type=int)
    q_text = (request.args.get('q') or '').strip().lower()
    limit = min(request.args.get('limit', type=int, default=50), 200)
    offset = request.args.get('offset', type=int, default=0)

    query = (db.session.query(JobMatch, RawJob, JobSource)
             .join(RawJob, RawJob.id == JobMatch.raw_job_id)
             .join(JobSource, JobSource.id == RawJob.source_id)
             .filter(JobMatch.user_id == g.user_id,
                     JobMatch.status.in_(status_filter)))

    if min_score > 0:
        query = query.filter(JobMatch.match_score >= min_score)
    if source_id:
        query = query.filter(JobSource.id == source_id)
    if q_text:
        query = query.filter(db.or_(
            db.func.lower(RawJob.title).contains(q_text),
            db.func.lower(RawJob.company).contains(q_text),
        ))

    total = query.count()
    rows = (query.order_by(JobMatch.match_score.desc().nullslast(),
                           JobMatch.created_at.desc())
                 .offset(offset).limit(limit).all())

    return jsonify({
        "matches": [_serialize_match(m, r, s) for (m, r, s) in rows],
        "total": total, "limit": limit, "offset": offset,
    }), 200


@jobs_user_bp.patch('/matches/<int:match_id>')
@require_auth
def update_match(match_id: int):
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    new_status = data.get("status")
    if new_status not in ('seen', 'dismissed', 'new'):
        return jsonify({"error": "status muss 'seen'|'dismissed'|'new' sein"}), 400
    m.status = new_status
    db.session.commit()
    return jsonify({"id": m.id, "status": m.status}), 200


@jobs_user_bp.post('/matches/<int:match_id>/import')
@require_auth
def import_match(match_id: int):
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403
    raw = RawJob.query.get(m.raw_job_id)

    notiz = (
        f"📥 Aus Job-Vorschlag importiert (Match-Score {m.match_score:.0f}).\n\n"
        f"Begründung: {m.match_reasoning or '–'}\n\n"
        f"Fehlende Skills: {', '.join(m.missing_skills) if m.missing_skills else '–'}\n\n"
        f"Original-Link: {raw.url}"
    )

    app = Application(
        user_id=g.user_id,
        firma=raw.company or "Unbekannt",
        position=raw.title,
        status='geplant',
        url=raw.url,
        notizen=notiz,
    )
    db.session.add(app)
    db.session.flush()

    m.status = 'imported'
    m.imported_application_id = app.id
    db.session.commit()

    return jsonify({"application_id": app.id}), 201
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/api/test_jobs_user.py -v
git add api/jobs_user.py tests/api/test_jobs_user.py
git commit -m "feat: User-API für Match-Listing, Status-Update, Übernahme-als-Bewerbung"
```

---

## Task 22: System-Quellen-Seed

**Files:**
- Create: `scripts/seed_job_sources.py`

- [ ] **Step 1: Skript schreiben**

```python
"""Seed-Skript: legt 3 globale Default-Quellen an, falls nicht vorhanden.

Idempotent — re-runs überschreiben nichts.

Usage:
    python scripts/seed_job_sources.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import JobSource


DEFAULTS = [
    {
        "name": "Bundesagentur — Frontend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Frontend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Bundesagentur — Backend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Backend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Arbeitnow — Remote Tech",
        "type": "arbeitnow",
        "config": {"tags": ["javascript", "python", "remote"]},
    },
]


def main():
    app = create_app()
    with app.app_context():
        for d in DEFAULTS:
            existing = JobSource.query.filter_by(name=d["name"], user_id=None).first()
            if existing:
                print(f"= {d['name']} (existiert bereits)")
                continue
            src = JobSource(
                user_id=None, name=d["name"], type=d["type"],
                enabled=True, crawl_interval_min=60,
            )
            src.config = d["config"]
            db.session.add(src)
            print(f"+ {d['name']}")
        db.session.commit()
        print("✓ Seed abgeschlossen.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Skript einmal laufen lassen + Idempotenz prüfen**

```bash
python scripts/seed_job_sources.py
python scripts/seed_job_sources.py  # zweites Mal: alle "= existiert bereits"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_job_sources.py
git commit -m "feat: Seed-Skript für 3 globale Default-Job-Quellen"
```

---

## Task 23: Doku + Manuelle QA

**Files:**
- Create: `docs/FEATURES/JOB_DISCOVERY.md`
- Modify: `README.md`

- [ ] **Step 1: Feature-Doku schreiben**

`docs/FEATURES/JOB_DISCOVERY.md`:
```markdown
# Job-Discovery & Auto-Matching (Phase A: Backend)

## Konzept

Automatische Stellensuche aus konfigurierbaren Quellen mit lokalem Pre-Filter
und Claude-basiertem Matching gegen den hinterlegten Lebenslauf.

## Setup

### 1. DB-Migration

```bash
python scripts/migrate_job_discovery.py
python scripts/seed_job_sources.py
```

### 2. ENV-Variablen

```bash
JOB_CRON_TOKEN=<random-secret-32+chars>
ANTHROPIC_API_KEY=<dein-key>     # Phase A: Server-Key. Phase B: BYOK.
CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001
```

### 3. User aktivieren

User muss `job_discovery_enabled=true` setzen und einen CV (cv_data_json) hinterlegen.

### 4. Cron-Setup (cron-job.org o.ä.)

```
*/15 * * * *      POST https://<deine-domain>/api/jobs/crawl-source
*/15 * * * *      POST https://<deine-domain>/api/jobs/prefilter
*/30 * * * *      POST https://<deine-domain>/api/jobs/claude-match
*/30 * * * *      POST https://<deine-domain>/api/jobs/notify
0 3 * * *         POST https://<deine-domain>/api/jobs/cleanup
```

Header bei jedem Aufruf: `X-Cron-Token: <JOB_CRON_TOKEN>`

## Manuelle Tests

| Schritt | Erwartung |
|---|---|
| `POST /api/jobs/crawl-source` mit Token | 200, neue Jobs in `raw_jobs` |
| `POST /api/jobs/prefilter` | 200, `match.prefilter_score` gesetzt |
| `POST /api/jobs/claude-match` | 200, Top-N Matches mit `match_score` + `match_reasoning` |
| `POST /api/jobs/notify` | 200, Push-Notification für Score ≥ 80 |
| `GET /api/jobs/matches?min_score=70` | Liste mit JWT |
| `POST /api/jobs/matches/<id>/import` | erstellt Bewerbung mit Match-Notiz |

## Limits / Cost-Capping

- Pro User max `job_claude_budget_per_tick` Claude-Calls (Default 5)
- Pro User max `job_daily_budget_cents` Kosten/Tag (Default 50 Cent)
- Quelle 5× Fehler in Folge → Auto-Disable
- RawJobs > 60 Tage ohne aktive Matches → archiviert
```

- [ ] **Step 2: README ergänzen**

In `README.md` unter "Kernfeatures" ergänzen:
```markdown
- 🔍 **Job-Discovery** - Automatische Stellensuche aus RSS-Feeds + Bundesagentur/Adzuna/Arbeitnow APIs mit Claude-basiertem Match-Score gegen deinen CV
```

- [ ] **Step 3: Manuelle Smoke-Test-Checkliste durchgehen**

```bash
# 1. Migration
python scripts/migrate_job_discovery.py
python scripts/seed_job_sources.py

# 2. Testserver
flask run

# 3. User aktivieren (über Profile-API oder direkt SQL)

# 4. Pipeline manuell triggern
curl -X POST http://localhost:5000/api/jobs/crawl-source -H "X-Cron-Token: $JOB_CRON_TOKEN"
curl -X POST http://localhost:5000/api/jobs/prefilter -H "X-Cron-Token: $JOB_CRON_TOKEN"
curl -X POST http://localhost:5000/api/jobs/claude-match -H "X-Cron-Token: $JOB_CRON_TOKEN"
curl -X POST http://localhost:5000/api/jobs/notify -H "X-Cron-Token: $JOB_CRON_TOKEN"

# 5. Matches abfragen (mit JWT)
curl http://localhost:5000/api/jobs/matches -H "Authorization: Bearer $JWT"
```

- [ ] **Step 4: Commit**

```bash
git add docs/FEATURES/JOB_DISCOVERY.md README.md
git commit -m "docs: Job-Discovery Phase A Doku + README-Update"
```

---

## Task 24: Full-Test-Run + Coverage

- [ ] **Step 1: Alle Tests laufen lassen**

```bash
pytest tests/ -v
```
Erwartet: alle PASS, keine Regressionen in bestehenden Tests.

- [ ] **Step 2: Coverage-Check für neue Module**

```bash
pytest tests/services/ tests/api/test_jobs_cron.py tests/api/test_jobs_user.py \
       --cov=services/job_sources --cov=services/job_matching \
       --cov=services/ssrf_guard --cov=services/cron_auth \
       --cov=api/jobs_cron --cov=api/jobs_user \
       --cov-report=term-missing
```
Erwartet: ≥ 80% Line-Coverage je Modul.

- [ ] **Step 3: Falls Lücken → fehlende Tests ergänzen**

- [ ] **Step 4: Final-Commit**

```bash
git commit --allow-empty -m "test: Phase A komplett — alle Tests grün, Coverage ≥80%"
```

---

## Phase A — Definition of Done

- ✅ DB-Migration funktioniert idempotent
- ✅ 4 Source-Adapter (RSS, Adzuna, Bundesagentur, Arbeitnow) mit Tests
- ✅ 5 Cron-Stages (crawl, prefilter, claude-match, notify, cleanup)
- ✅ User-API für Quellen-Verwaltung + Match-Listing + Übernahme
- ✅ SSRF-Guard, Cron-Token, Auto-Disable bei Fehlern
- ✅ Cost-Capping (Tick-Limit + Tagesbudget)
- ✅ Coverage ≥80% für neue Module
- ✅ Doku in `docs/FEATURES/JOB_DISCOVERY.md`
- ✅ Globale Default-Quellen geseedet

Phase A ist via curl/Postman komplett funktional. Phase B fügt BYOK hinzu, Phase C das Frontend.
