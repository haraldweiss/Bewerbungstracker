# User-defined Email-Plattformen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin kann im UI neue Email-Plattformen anlegen (Stepstone, get-in-IT, …), ohne Code-Push. AI-Pattern-Learning übernimmt danach die Layout-Extraktion.

**Architecture:** Hybrid — bestehende 3 Plattformen (Indeed/LinkedIn/XING) bleiben in hardcoded `PROFILES`-Dict. Neue Tabelle `platform_profiles` für DB-Plattformen. Resolution via neuer Funktion `get_profile(slug)` (Hardcoded → DB → KeyError). UI-Wizard im Admin-Tab mit Domain-Eingabe → Auto-Generation von Regex-Defaults.

**Tech Stack:** Flask + SQLAlchemy + Alembic (Backend), Vanilla-JS mit DOM-API (Frontend), pytest (Tests).

**Spec:** `docs/superpowers/specs/2026-05-21-user-defined-platforms-design.md`

---

### Task 1: DB-Modell `PlatformProfileRow` + Alembic-Migration

**Files:**
- Modify: `models.py` (neue Klasse `PlatformProfileRow`)
- Create: `alembic/versions/20260521_1600_add_platform_profiles_table.py`
- Test: `tests/test_platform_profiles_db.py`

- [ ] **Step 1: Failing Test**

Create `tests/test_platform_profiles_db.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from models import PlatformProfileRow, User


def test_create_platform_profile(app, user_factory):
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone",
        display_name="Stepstone",
        domain="stepstone.de",
        subject_must_contain='["stelle", "job"]',
        ai_schema_hint="Generic European job board.",
        digest_threshold=3,
        created_by_user_id=user.id,
    )
    from database import db
    db.session.add(row)
    db.session.commit()
    fetched = PlatformProfileRow.query.filter_by(slug="stepstone").first()
    assert fetched.display_name == "Stepstone"
    assert fetched.domain == "stepstone.de"


def test_slug_unique(app, user_factory):
    from database import db
    user = user_factory()
    r1 = PlatformProfileRow(
        slug="stepstone", display_name="A", domain="a.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(r1); db.session.commit()
    r2 = PlatformProfileRow(
        slug="stepstone", display_name="B", domain="b.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(r2)
    with pytest.raises(Exception):  # IntegrityError
        db.session.commit()
```

- [ ] **Step 2: Run and confirm FAIL**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_db.py -v
```
Expected: `ImportError: cannot import name 'PlatformProfileRow' from 'models'`

- [ ] **Step 3: Add `PlatformProfileRow` class to `models.py`**

Append to `models.py` (after the last existing class, before any final module-level code):

```python
class PlatformProfileRow(db.Model):
    """User-defined Email-Plattform.

    Resolution-Priorität: hardcoded `PROFILES`-Dict zuerst (Indeed/LinkedIn/
    XING), dann diese Tabelle. Siehe `services/job_sources/email_jobs.py::
    get_profile`.
    """
    __tablename__ = 'platform_profiles'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), nullable=False, unique=True)
    display_name = db.Column(db.String(120), nullable=False)
    domain = db.Column(db.String(120), nullable=False)
    # JSON-Array von Subject-Substrings (case-insensitive)
    subject_must_contain = db.Column(db.Text, nullable=False, default='[]')
    ai_schema_hint = db.Column(db.Text, nullable=True)
    digest_threshold = db.Column(db.Integer, nullable=False, default=3)
    # Optionale Regex-Overrides — wenn NULL, wird aus `domain` auto-generiert.
    url_pattern_override = db.Column(db.Text, nullable=True)
    from_whitelist_override = db.Column(db.Text, nullable=True)
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False,
    )
    created_by_user_id = db.Column(
        db.String(36), db.ForeignKey('users.id'), nullable=False,
    )

    def to_dict(self) -> dict:
        import json as _json
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "domain": self.domain,
            "subject_must_contain": _json.loads(self.subject_must_contain or "[]"),
            "ai_schema_hint": self.ai_schema_hint or "",
            "digest_threshold": self.digest_threshold,
            "url_pattern_override": self.url_pattern_override,
            "from_whitelist_override": self.from_whitelist_override,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<PlatformProfileRow {self.slug}>'
```

- [ ] **Step 4: Create Alembic migration**

Find the previous migration head:
```bash
ls -1 alembic/versions/ | tail -5
```

Latest head should be `7c4d9f1a2b3e` (widen_rawjob_url_column); verify with `grep revision alembic/versions/*widen*.py`.

Create `alembic/versions/20260521_1600_add_platform_profiles_table.py`:

```python
"""add platform_profiles table

Revision ID: a1b2c3d4e5f6
Revises: 7c4d9f1a2b3e
Create Date: 2026-05-21 16:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '7c4d9f1a2b3e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platform_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(120), nullable=False),
        sa.Column('domain', sa.String(120), nullable=False),
        sa.Column('subject_must_contain', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('ai_schema_hint', sa.Text(), nullable=True),
        sa.Column('digest_threshold', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('url_pattern_override', sa.Text(), nullable=True),
        sa.Column('from_whitelist_override', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.UniqueConstraint('slug', name='uq_platform_profiles_slug'),
    )


def downgrade():
    op.drop_table('platform_profiles')
```

- [ ] **Step 5: Run migration locally**

```bash
PYTHONPATH=. venv/bin/alembic upgrade head
```
Expected: `Running upgrade 7c4d9f1a2b3e -> a1b2c3d4e5f6, add platform_profiles table`

- [ ] **Step 6: Tests grün**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_db.py -v
```
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add models.py alembic/versions/20260521_1600_add_platform_profiles_table.py tests/test_platform_profiles_db.py
git commit -m "feat(platforms): PlatformProfileRow model + migration"
```

---

### Task 2: `get_profile(slug)` + `_build_profile_from_row()`

**Files:**
- Modify: `services/job_sources/email_jobs.py`
- Test: `tests/test_platform_profiles_resolver.py`

- [ ] **Step 1: Failing Tests**

Create `tests/test_platform_profiles_resolver.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
import re
from services.job_sources.email_jobs import (
    get_profile, PROFILES, PlatformProfile, _build_profile_from_row,
)


def test_get_profile_hardcoded_indeed():
    p = get_profile("indeed")
    assert p is PROFILES["indeed"]


def test_get_profile_hardcoded_linkedin():
    p = get_profile("linkedin")
    assert p.name == "linkedin"


def test_get_profile_unknown_raises(app):
    with pytest.raises(KeyError):
        get_profile("does_not_exist_anywhere")


def test_get_profile_from_db(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone",
        display_name="Stepstone",
        domain="stepstone.de",
        subject_must_contain='["stelle", "job"]',
        ai_schema_hint="Test hint",
        digest_threshold=3,
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()

    p = get_profile("stepstone")
    assert isinstance(p, PlatformProfile)
    assert p.name == "stepstone"
    assert p.source_label == "Stepstone"
    assert p.subject_must_contain == ("stelle", "job")
    assert p.ai_schema_hint == "Test hint"


def test_build_profile_auto_generates_url_pattern(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert p.url_pattern.search("https://www.stepstone.de/job/12345")
    assert p.url_pattern.search("https://www.stepstone.de/anything/here")
    assert not p.url_pattern.search("https://example.com/foo")


def test_build_profile_auto_generates_from_whitelist(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert len(p.from_whitelist) == 1
    pattern = re.compile(p.from_whitelist[0])
    assert pattern.search("noreply@stepstone.de")
    assert pattern.search("alerts@jobs.stepstone.de")
    assert not pattern.search("noreply@example.com")


def test_build_profile_url_pattern_override(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    custom = r"https?://(?:www\.)?stepstone\.de/stellenangebote/\d+"
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", url_pattern_override=custom,
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert p.url_pattern.pattern == custom
    assert p.url_pattern.search("https://stepstone.de/stellenangebote/123")
    assert not p.url_pattern.search("https://stepstone.de/news/foo")
```

- [ ] **Step 2: Run and confirm FAIL**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_resolver.py -v
```
Expected: `ImportError: cannot import name 'get_profile'` / `_build_profile_from_row`

- [ ] **Step 3: Add `get_profile` + `_build_profile_from_row` to `services/job_sources/email_jobs.py`**

Append at module level (after the `PROFILES` dict, before the `EmailJobsAdapter` class):

```python
# Generic defaults für auto-generated Plattformen (DB-resolved).
_GENERIC_SUBJECT_PATTERN = re.compile(
    r"^(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)\s*$",
    re.IGNORECASE,
)


def _build_profile_from_row(row) -> PlatformProfile:
    """Konstruiert PlatformProfile aus DB-Row. Auto-Generation aus domain
    wenn url_pattern_override / from_whitelist_override nicht gesetzt sind.
    """
    import json as _json
    domain = row.domain
    domain_esc = re.escape(domain)

    if row.url_pattern_override:
        url_pattern_str = row.url_pattern_override
    else:
        url_pattern_str = (
            rf"https?://(?:[a-z0-9.-]+\.)?{domain_esc}/[^\s)<>\"'\\]+"
        )
    url_pattern = re.compile(url_pattern_str, re.IGNORECASE)

    if row.from_whitelist_override:
        from_whitelist = (row.from_whitelist_override,)
    else:
        from_whitelist = (rf"@(?:[a-z0-9.-]+\.)?{domain_esc}$",)

    subject_must_contain = tuple(
        _json.loads(row.subject_must_contain or "[]")
    )

    return PlatformProfile(
        name=row.slug,
        source_label=row.display_name,
        from_filter=f"from:{domain}",
        from_whitelist=from_whitelist,
        url_pattern=url_pattern,
        subject_patterns=(_GENERIC_SUBJECT_PATTERN,),
        body_title_re=_BODY_TITLE_RE,
        body_company_re=_BODY_COMPANY_RE,
        body_location_re=_BODY_LOCATION_RE,
        digest_threshold=row.digest_threshold,
        ai_hint="",
        body_card_re=None,
        hard_title_blacklist_re=None,
        subject_must_contain=subject_must_contain,
        ai_schema_hint=row.ai_schema_hint or "",
    )


def get_profile(slug: str) -> PlatformProfile:
    """Resolve Plattform-Slug zu PlatformProfile.

    1. Hardcoded PROFILES-Dict (legacy, getestet — Vorrang).
    2. DB-Tabelle platform_profiles (user-defined).
    3. KeyError wenn nichts gefunden.
    """
    if slug in PROFILES:
        return PROFILES[slug]
    from models import PlatformProfileRow
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if row is None:
        raise KeyError(f"Unknown platform: {slug}")
    return _build_profile_from_row(row)
```

- [ ] **Step 4: Tests grün**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_resolver.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/email_jobs.py tests/test_platform_profiles_resolver.py
git commit -m "feat(platforms): get_profile resolver + auto-generation aus domain"
```

---

### Task 3: Refactor — alle `PROFILES[slug]` auf `get_profile(slug)`

**Files:**
- Modify: `services/job_sources/__init__.py` (lines 42-49)
- Modify: `services/job_sources/pattern_learner.py` (line 400 + import)
- Modify: `api/jobs_user.py` (lines 183, 1219, 1225)
- Modify: `api/jobs_cron.py` (line 44 + line 258)

- [ ] **Step 1: Failing Test — Adapter mit DB-Plattform funktioniert**

Add to `tests/test_platform_profiles_resolver.py`:

```python
def test_get_adapter_with_db_platform(app, user_factory):
    """get_adapter() für 'stepstone_email' findet die Plattform in der DB."""
    from database import db
    from models import PlatformProfileRow
    from services.job_sources import get_adapter
    from services.job_sources.email_jobs import EmailJobsAdapter
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()

    adapter = get_adapter("stepstone_email", config={}, user=user)
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile.name == "stepstone"
```

- [ ] **Step 2: RED**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_resolver.py::test_get_adapter_with_db_platform -v
```
Expected: `ValueError: Unbekannte Email-Plattform: stepstone`

- [ ] **Step 3: Refactor `services/job_sources/__init__.py:42-49`**

Find:
```python
    if source_type.endswith("_email"):
        from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
        platform = source_type[: -len("_email")]
        if platform not in PROFILES:
            raise ValueError(f"Unbekannte Email-Plattform: {platform}")
        return EmailJobsAdapter(
            config=config,
            user=kwargs.get("user"),
            platform_profile=PROFILES[platform],
        )
```

Replace with:
```python
    if source_type.endswith("_email"):
        from services.job_sources.email_jobs import EmailJobsAdapter, get_profile
        platform = source_type[: -len("_email")]
        try:
            profile = get_profile(platform)
        except KeyError:
            raise ValueError(f"Unbekannte Email-Plattform: {platform}")
        return EmailJobsAdapter(
            config=config,
            user=kwargs.get("user"),
            platform_profile=profile,
        )
```

- [ ] **Step 4: Refactor `services/job_sources/pattern_learner.py:400`**

Find:
```python
        platform_profile=PROFILES[platform],
```

Replace with:
```python
        platform_profile=get_profile(platform),
```

Also: at the top of `pattern_learner.py`, search for the import line referencing `PROFILES`:
```bash
grep -n "from services.job_sources.email_jobs import" services/job_sources/pattern_learner.py
```

If not yet imported, add `get_profile` to the existing import. E.g. change:
```python
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
```
to:
```python
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES, get_profile
```

- [ ] **Step 5: Refactor `api/jobs_user.py:183`**

Find:
```python
            name=f"{PROFILES[platform].source_label} Email",
```

Replace with:
```python
            name=f"{get_profile(platform).source_label} Email",
```

Add `get_profile` to the import at the top of the file:
```bash
grep -n "from services.job_sources.email_jobs import" api/jobs_user.py
```

Extend the existing import to include `get_profile`.

- [ ] **Step 6: Refactor `api/jobs_user.py:1219, 1225`**

Find:
```python
        url_pattern_str = PROFILES[platform].url_pattern.pattern
```
Replace with:
```python
        url_pattern_str = get_profile(platform).url_pattern.pattern
```

Find:
```python
        compiled, test, url_check_re=PROFILES[platform].url_pattern,
```
Replace with:
```python
        compiled, test, url_check_re=get_profile(platform).url_pattern,
```

- [ ] **Step 7: Refactor `api/jobs_cron.py:44` — dynamisches `EMAIL_SOURCE_TYPES`**

Find:
```python
EMAIL_SOURCE_TYPES = ("indeed_email", "linkedin_email", "xing_email")
```

Add a helper function right after that line (KEEP the existing constant — it's a backward-compat fallback):

```python
def _email_source_types() -> tuple[str, ...]:
    """Dynamische Liste aller Email-Plattform-Types (hardcoded + DB).

    Wird in `_select_due_source` genutzt um Email-Sources vom auto-crawl
    auszuschließen (sie laufen nur per manuellem Import-Button).
    """
    from services.job_sources.email_jobs import PROFILES
    from models import PlatformProfileRow
    hardcoded = tuple(f"{slug}_email" for slug in PROFILES.keys())
    try:
        db_slugs = tuple(
            f"{r.slug}_email"
            for r in PlatformProfileRow.query.with_entities(
                PlatformProfileRow.slug
            ).all()
        )
    except Exception:
        # Tabelle existiert noch nicht (z.B. erste Migration)
        db_slugs = ()
    return hardcoded + db_slugs
```

Find the callsite around line 258:
```python
        JobSource.type.notin_(EMAIL_SOURCE_TYPES),
```

Replace with:
```python
        JobSource.type.notin_(_email_source_types()),
```

- [ ] **Step 8: Run new + regression tests**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_resolver.py tests/test_platform_profiles_db.py -v
echo "--- Regression ---"
PYTHONPATH=. venv/bin/pytest tests/ -k 'pattern_learner or email_jobs or jobs_user or jobs_cron' -v 2>&1 | tail -10
```
Expected: new tests pass; regression all green.

- [ ] **Step 9: Commit**

```bash
git add services/job_sources/__init__.py services/job_sources/pattern_learner.py api/jobs_user.py api/jobs_cron.py tests/test_platform_profiles_resolver.py
git commit -m "refactor(platforms): alle PROFILES[slug] auf get_profile(slug) umstellen"
```

---

### Task 4: API-Endpoints (Admin CRUD)

**Files:**
- Modify: `api/admin.py` (4 neue Endpoints + Validation-Helper)
- Test: `tests/test_platform_profiles_api.py`

- [ ] **Step 1: Failing Tests**

Create `tests/test_platform_profiles_api.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import pytest


def _admin_headers(client, user_factory):
    """Promote user to admin and return auth headers."""
    from database import db
    user = user_factory()
    user.is_admin = True
    db.session.commit()
    from auth_service import AuthService
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def _user_headers(client, user_factory):
    user = user_factory()
    from auth_service import AuthService
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_list_platforms_admin_only(client, user_factory):
    headers, _ = _user_headers(client, user_factory)
    r = client.get("/api/admin/platforms", headers=headers)
    assert r.status_code == 403


def test_list_platforms_empty(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.get("/api/admin/platforms", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"platforms": []}


def test_create_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone",
            "display_name": "Stepstone",
            "domain": "stepstone.de",
            "subject_must_contain": ["stelle", "job"],
            "ai_schema_hint": "",
        },
        headers=headers,
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["slug"] == "stepstone"
    assert data["domain"] == "stepstone.de"


def test_create_rejects_reserved_slug(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "indeed",  # reserved (hardcoded)
            "display_name": "Indeed Custom",
            "domain": "example.com",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "reserviert" in r.get_json().get("error", "").lower()


def test_create_rejects_duplicate_slug(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    payload = {
        "slug": "stepstone", "display_name": "A", "domain": "a.de",
        "subject_must_contain": ["x"],
    }
    client.post("/api/admin/platforms", json=payload, headers=headers)
    r = client.post("/api/admin/platforms", json=payload, headers=headers)
    assert r.status_code == 400
    assert "existiert" in r.get_json().get("error", "").lower()


def test_create_rejects_invalid_slug_format(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "STEP STONE!",  # invalid chars + uppercase
            "display_name": "X", "domain": "x.de",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_rejects_invalid_domain(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone", "display_name": "Stepstone",
            "domain": "not a domain",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_rejects_invalid_regex_override(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone", "display_name": "Stepstone",
            "domain": "stepstone.de",
            "subject_must_contain": ["x"],
            "url_pattern_override": r"[invalid(regex",
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_update_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "Old", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    r = client.patch(
        "/api/admin/platforms/stepstone",
        json={"display_name": "New Name"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["display_name"] == "New Name"


def test_delete_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "x", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    r = client.delete("/api/admin/platforms/stepstone", headers=headers)
    assert r.status_code == 200


def test_delete_blocked_when_jobsource_references_it(client, user_factory):
    from database import db
    from models import JobSource
    headers, admin = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "x", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    js = JobSource(
        name="Stepstone Test", type="stepstone_email",
        scope="global", enabled=True, config={},
    )
    db.session.add(js); db.session.commit()
    r = client.delete("/api/admin/platforms/stepstone", headers=headers)
    assert r.status_code == 409
    assert "JobSource" in r.get_json().get("error", "")
```

- [ ] **Step 2: RED**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_api.py -v
```
Expected: tests fail with 404 (endpoints don't exist).

- [ ] **Step 3: Add 4 endpoints + validation to `api/admin.py`**

Append to `api/admin.py`:

```python
# ── Platform Profiles ──────────────────────────────────────────────────────

import re as _re_pp
import json as _json_pp
from models import PlatformProfileRow

_SLUG_RE = _re_pp.compile(r"^[a-z0-9_-]{2,64}$")
_DOMAIN_RE = _re_pp.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", _re_pp.IGNORECASE)


def _validate_payload(payload: dict, partial: bool = False) -> tuple[dict, str | None]:
    """Validate platform-profile payload. Returns (cleaned, error_msg)."""
    from services.job_sources.email_jobs import PROFILES

    cleaned: dict = {}

    if "slug" in payload or not partial:
        slug = (payload.get("slug") or "").strip().lower()
        if not _SLUG_RE.match(slug):
            return {}, "slug muss [a-z0-9_-]{2,64} sein"
        if slug in PROFILES:
            return {}, f"Slug '{slug}' ist reserviert (hardcoded Plattform)"
        cleaned["slug"] = slug

    if "display_name" in payload or not partial:
        name = (payload.get("display_name") or "").strip()
        if not name or len(name) > 120:
            return {}, "display_name muss 1-120 Zeichen sein"
        cleaned["display_name"] = name

    if "domain" in payload or not partial:
        domain = (payload.get("domain") or "").strip().lower()
        if not _DOMAIN_RE.match(domain):
            return {}, "domain muss ein gültiger Hostname sein"
        cleaned["domain"] = domain

    if "subject_must_contain" in payload or not partial:
        smc = payload.get("subject_must_contain") or []
        if not isinstance(smc, list) or not (1 <= len(smc) <= 20):
            return {}, "subject_must_contain muss 1-20 Strings enthalten"
        if any(not isinstance(s, str) or len(s) > 80 for s in smc):
            return {}, "subject_must_contain: Strings ≤80 Zeichen"
        cleaned["subject_must_contain"] = _json_pp.dumps(smc)

    if "ai_schema_hint" in payload:
        hint = (payload.get("ai_schema_hint") or "").strip()
        if len(hint) > 2000:
            return {}, "ai_schema_hint ≤2000 Zeichen"
        cleaned["ai_schema_hint"] = hint or None

    if "digest_threshold" in payload:
        try:
            dt = int(payload["digest_threshold"])
            if not (1 <= dt <= 20):
                raise ValueError()
        except (TypeError, ValueError):
            return {}, "digest_threshold muss 1-20 sein"
        cleaned["digest_threshold"] = dt

    if "url_pattern_override" in payload:
        v = (payload.get("url_pattern_override") or "").strip()
        if v:
            if len(v) > 500:
                return {}, "url_pattern_override ≤500 Zeichen"
            try:
                _re_pp.compile(v)
            except _re_pp.error as exc:
                return {}, f"url_pattern_override ungültig: {exc}"
            cleaned["url_pattern_override"] = v
        else:
            cleaned["url_pattern_override"] = None

    if "from_whitelist_override" in payload:
        v = (payload.get("from_whitelist_override") or "").strip()
        if v:
            if len(v) > 500:
                return {}, "from_whitelist_override ≤500 Zeichen"
            try:
                _re_pp.compile(v)
            except _re_pp.error as exc:
                return {}, f"from_whitelist_override ungültig: {exc}"
            cleaned["from_whitelist_override"] = v
        else:
            cleaned["from_whitelist_override"] = None

    return cleaned, None


@admin_bp.get('/platforms')
@admin_required
def list_platforms(user):
    rows = PlatformProfileRow.query.order_by(PlatformProfileRow.slug).all()
    return jsonify({"platforms": [r.to_dict() for r in rows]}), 200


@admin_bp.post('/platforms')
@admin_required
def create_platform(user):
    payload = request.get_json() or {}
    cleaned, err = _validate_payload(payload, partial=False)
    if err:
        return jsonify({"error": err}), 400
    if PlatformProfileRow.query.filter_by(slug=cleaned["slug"]).first():
        return jsonify({"error": f"Slug '{cleaned['slug']}' existiert bereits"}), 400
    row = PlatformProfileRow(
        **cleaned,
        digest_threshold=cleaned.get("digest_threshold", 3),
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    return jsonify(row.to_dict()), 201


@admin_bp.patch('/platforms/<string:slug>')
@admin_required
def update_platform(user, slug):
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if not row:
        return jsonify({"error": "Plattform nicht gefunden"}), 404
    payload = request.get_json() or {}
    # Slug-Änderung verbieten (FK-stabil halten)
    if "slug" in payload and payload["slug"] != slug:
        return jsonify({"error": "Slug nicht änderbar"}), 400
    payload.pop("slug", None)
    cleaned, err = _validate_payload(payload, partial=True)
    if err:
        return jsonify({"error": err}), 400
    for k, v in cleaned.items():
        setattr(row, k, v)
    db.session.commit()
    return jsonify(row.to_dict()), 200


@admin_bp.delete('/platforms/<string:slug>')
@admin_required
def delete_platform(user, slug):
    from models import JobSource
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if not row:
        return jsonify({"error": "Plattform nicht gefunden"}), 404
    ref_count = JobSource.query.filter_by(type=f"{slug}_email").count()
    if ref_count > 0:
        return jsonify({
            "error": f"Plattform wird von {ref_count} JobSource(s) genutzt"
        }), 409
    db.session.delete(row); db.session.commit()
    return jsonify({"deleted": slug}), 200
```

Note: `request`, `jsonify`, `db`, `admin_bp`, `admin_required` are already imported at the top of `api/admin.py`.

- [ ] **Step 4: Tests grün**

```bash
PYTHONPATH=. venv/bin/pytest tests/test_platform_profiles_api.py -v
```
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add api/admin.py tests/test_platform_profiles_api.py
git commit -m "feat(platforms): admin-CRUD-API für user-defined Plattformen"
```

---

### Task 5: Frontend — Admin-Tab + Wizard (DOM-safe)

**Files:**
- Modify: `index.html` (neuer Admin-Sektion + JS-Modul `PlatformsUI`)
- Modify: `service-worker.js` (`CACHE_NAME` bump)

**Security note:** Dynamic table rows + modal inputs werden via DOM-API (`document.createElement` + `textContent`) gebaut, NICHT via Template-Literals mit Variable-Interpolation. Static markup (Card-Container, Modal-Skeleton) bleibt als statisches HTML.

- [ ] **Step 1: Add static HTML card + modal skeleton to `index.html`**

Find the existing learned-patterns card around line ~1299 (`grep -n "jdLearnedPatternsTableBody" index.html`). After its closing `</div></div>`, insert static markup:

```html
<div class="card" style="max-width:900px;margin-top:1rem;">
  <div class="card-title" style="margin-bottom:0.75rem">🌐 Plattformen (Email-Quellen)</div>
  <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.75rem;">
    Neue Email-Plattformen anlegen ohne Code-Push. Indeed/LinkedIn/XING sind
    hardcoded und nicht editierbar. AI-Pattern-Learning übernimmt das Layout
    beim ersten 🧠 Lernen.
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
    <thead>
      <tr style="text-align:left;color:var(--text-muted)">
        <th style="padding:0.4rem">Slug</th>
        <th>Anzeige-Name</th>
        <th>Domain</th>
        <th>Subject-Keywords</th>
        <th>Aktion</th>
      </tr>
    </thead>
    <tbody id="platformTableBody">
      <tr><td colspan="5" style="color:var(--text-muted)">Lädt...</td></tr>
    </tbody>
  </table>
  <div style="margin-top:0.75rem">
    <button class="btn btn-primary btn-sm" onclick="PlatformsUI.openCreate()">+ Neue Plattform</button>
    <button class="btn btn-secondary btn-sm" onclick="PlatformsUI.load()">🔄 Aktualisieren</button>
  </div>
</div>

<div id="platformModal" class="modal" style="display:none">
  <div class="modal-content" style="max-width:560px">
    <div class="modal-header">
      <h3 id="platformModalTitle">Neue Plattform anlegen</h3>
      <button class="modal-close" onclick="PlatformsUI.closeModal()">×</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label>Anzeige-Name *</label>
        <input type="text" id="pfName" placeholder="z.B. Stepstone" style="width:100%">
      </div>
      <div class="form-group">
        <label>Domain *</label>
        <input type="text" id="pfDomain" placeholder="stepstone.de" style="width:100%">
        <div style="font-size:0.75rem;color:var(--text-muted)">Nur Hostname, ohne https://</div>
      </div>
      <div class="form-group">
        <label>Slug *</label>
        <input type="text" id="pfSlug" placeholder="stepstone" style="width:100%">
        <div style="font-size:0.75rem;color:var(--text-muted)">Identifier — JobSource-Type wird "&lt;slug&gt;_email"</div>
      </div>
      <div class="form-group">
        <label>Subject-Keywords (kommagetrennt) *</label>
        <input type="text" id="pfKeywords" placeholder="stelle, job, stellenangebot" style="width:100%">
      </div>
      <div class="form-group">
        <label>AI-Hint (optional)</label>
        <textarea id="pfHint" rows="3" placeholder="Layout-Hinweis für AI-Pattern-Learner..." style="width:100%;resize:vertical"></textarea>
      </div>
      <details style="margin-top:0.75rem">
        <summary style="cursor:pointer;color:var(--text-muted)">⚙️ Advanced (Regex-Overrides)</summary>
        <div class="form-group" style="margin-top:0.5rem">
          <label>URL-Pattern-Override</label>
          <input type="text" id="pfUrlOverride" placeholder="(auto aus Domain)" style="width:100%">
        </div>
        <div class="form-group">
          <label>From-Whitelist-Override</label>
          <input type="text" id="pfFromOverride" placeholder="(auto aus Domain)" style="width:100%">
        </div>
      </details>
      <div id="pfError" style="color:#dc3545;margin-top:0.5rem;font-size:0.85rem"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="PlatformsUI.closeModal()">Abbrechen</button>
      <button class="btn btn-primary" onclick="PlatformsUI.save()">Speichern</button>
    </div>
  </div>
</div>
```

All `id`-references and onclick-handlers point to the JS-Module added in next step. No dynamic interpolation in this block.

- [ ] **Step 2: Add `PlatformsUI` JS module (DOM-API-based)**

Find a place in `index.html` JS section near `JdSourcesUI` (search `const JdSourcesUI = `). Add adjacent module that uses ONLY DOM-API (createElement + textContent), no template-string + interpolation:

```javascript
const PlatformsUI = (() => {
    let _editingSlug = null;
    const _hardcoded = ['indeed', 'linkedin', 'xing'];

    function slugFromName(name) {
        return (name || '').toLowerCase()
            .replace(/[^a-z0-9_-]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 64);
    }

    function _addCell(row, text) {
        const td = document.createElement('td');
        td.style.padding = '0.4rem';
        td.textContent = text == null ? '' : String(text);
        return row.appendChild(td);
    }

    function _addActionButtons(row, slug) {
        const td = document.createElement('td');
        td.style.padding = '0.4rem';
        const btnEdit = document.createElement('button');
        btnEdit.className = 'btn btn-sm';
        btnEdit.textContent = '✏️';
        btnEdit.addEventListener('click', () => edit(slug));
        const btnDel = document.createElement('button');
        btnDel.className = 'btn btn-sm';
        btnDel.textContent = '🗑️';
        btnDel.addEventListener('click', () => remove(slug));
        td.appendChild(btnEdit);
        td.appendChild(document.createTextNode(' '));
        td.appendChild(btnDel);
        row.appendChild(td);
    }

    function _renderTable(rows) {
        const tbody = document.getElementById('platformTableBody');
        if (!tbody) return;
        while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

        // Hardcoded platforms (read-only display)
        _hardcoded.forEach(slug => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border)';
            tr.style.color = 'var(--text-muted)';
            _addCell(tr, slug);
            _addCell(tr, slug.charAt(0).toUpperCase() + slug.slice(1));
            _addCell(tr, '—');
            _addCell(tr, '—');
            _addCell(tr, '(Hardcoded)');
            tbody.appendChild(tr);
        });

        // DB platforms
        rows.forEach(p => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border)';
            _addCell(tr, p.slug);
            _addCell(tr, p.display_name);
            _addCell(tr, p.domain);
            _addCell(tr, (p.subject_must_contain || []).join(', '));
            _addActionButtons(tr, p.slug);
            tbody.appendChild(tr);
        });
    }

    function _renderError(msg) {
        const tbody = document.getElementById('platformTableBody');
        if (!tbody) return;
        while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5;
        td.style.color = '#dc3545';
        td.textContent = 'Fehler: ' + msg;
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    async function load() {
        try {
            const r = await Auth.fetch('/admin/platforms', { method: 'GET' });
            const list = (r && r.platforms) || [];
            _renderTable(list);
        } catch (e) {
            _renderError(e && e.message ? e.message : String(e));
        }
    }

    function openCreate() {
        _editingSlug = null;
        document.getElementById('platformModalTitle').textContent = 'Neue Plattform anlegen';
        ['pfName','pfDomain','pfSlug','pfKeywords','pfHint','pfUrlOverride','pfFromOverride'].forEach(id => {
            document.getElementById(id).value = '';
        });
        document.getElementById('pfSlug').disabled = false;
        document.getElementById('pfError').textContent = '';
        document.getElementById('platformModal').style.display = 'flex';
        // Auto-slug from name (only during create)
        document.getElementById('pfName').oninput = (e) => {
            if (!_editingSlug) {
                document.getElementById('pfSlug').value = slugFromName(e.target.value);
            }
        };
    }

    async function edit(slug) {
        _editingSlug = slug;
        try {
            const r = await Auth.fetch('/admin/platforms', { method: 'GET' });
            const p = ((r && r.platforms) || []).find(x => x.slug === slug);
            if (!p) { alert('Plattform nicht gefunden'); return; }
            document.getElementById('platformModalTitle').textContent = 'Plattform bearbeiten: ' + slug;
            document.getElementById('pfName').value = p.display_name || '';
            document.getElementById('pfDomain').value = p.domain || '';
            document.getElementById('pfSlug').value = p.slug || '';
            document.getElementById('pfSlug').disabled = true;
            document.getElementById('pfKeywords').value = (p.subject_must_contain || []).join(', ');
            document.getElementById('pfHint').value = p.ai_schema_hint || '';
            document.getElementById('pfUrlOverride').value = p.url_pattern_override || '';
            document.getElementById('pfFromOverride').value = p.from_whitelist_override || '';
            document.getElementById('pfError').textContent = '';
            document.getElementById('platformModal').style.display = 'flex';
        } catch (e) {
            alert('Fehler: ' + (e && e.message ? e.message : e));
        }
    }

    function closeModal() {
        document.getElementById('platformModal').style.display = 'none';
        document.getElementById('pfSlug').disabled = false;
        _editingSlug = null;
    }

    async function save() {
        const payload = {
            slug: document.getElementById('pfSlug').value.trim(),
            display_name: document.getElementById('pfName').value.trim(),
            domain: document.getElementById('pfDomain').value.trim(),
            subject_must_contain: document.getElementById('pfKeywords').value
                .split(',').map(s => s.trim()).filter(Boolean),
            ai_schema_hint: document.getElementById('pfHint').value.trim(),
            url_pattern_override: document.getElementById('pfUrlOverride').value.trim() || null,
            from_whitelist_override: document.getElementById('pfFromOverride').value.trim() || null,
        };
        try {
            const url = _editingSlug
                ? '/admin/platforms/' + encodeURIComponent(_editingSlug)
                : '/admin/platforms';
            const method = _editingSlug ? 'PATCH' : 'POST';
            const r = await Auth.fetch(url, { method, body: JSON.stringify(payload) });
            if (r && (r.slug || r.display_name)) {
                closeModal();
                await load();
            } else if (r && r.error) {
                document.getElementById('pfError').textContent = r.error;
            }
        } catch (e) {
            document.getElementById('pfError').textContent = e && e.message ? e.message : String(e);
        }
    }

    async function remove(slug) {
        if (!confirm('Plattform "' + slug + '" wirklich löschen?')) return;
        try {
            const r = await Auth.fetch('/admin/platforms/' + encodeURIComponent(slug), { method: 'DELETE' });
            if (r && r.deleted) {
                await load();
            } else if (r && r.error) {
                alert('❌ ' + r.error);
            }
        } catch (e) {
            alert('❌ ' + (e && e.message ? e.message : e));
        }
    }

    return { load, openCreate, edit, closeModal, save, remove };
})();
```

- [ ] **Step 3: Hook `PlatformsUI.load()` into admin-tab activation**

Find where `JdSourcesUI.loadLearnedPatterns()` is called (around line ~3217). Add adjacent:

```javascript
if (typeof PlatformsUI !== 'undefined' && PlatformsUI.load) {
    PlatformsUI.load();
}
```

- [ ] **Step 4: SW Cache bump**

```bash
grep -n "CACHE_NAME" service-worker.js | head -1
```

Find current value (e.g. `'bewerbungs-tracker-v52'`) and increment by 1.

- [ ] **Step 5: Smoke-Test lokal (manuell)**

```bash
./start.sh
```

Browser: Login als admin → Settings → Admin → "🌐 Plattformen" sichtbar → "+ Neue Plattform" → Name/Domain ausfüllen → Slug auto-generiert → Subject-Keywords → Speichern → Tabelle zeigt neue Zeile → Edit-Button → Felder pre-filled → Save → Update funktioniert → Delete → Plattform weg.

- [ ] **Step 6: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(frontend): admin-tab + wizard für user-defined plattformen (DOM-safe)"
```

---

### Task 6: JobSource-Type-Selector dynamisch erweitern

**Files:**
- Modify: `index.html` (JdSourcesUI module + renderConfigForm + buildConfig)

- [ ] **Step 1: Add `_loadDynamicPlatforms` to `JdSourcesUI`**

Find the `JdSourcesUI` IIFE (search `const JdSourcesUI = `). Inside the IIFE, before the `return { ... }` export, add:

```javascript
async function _loadDynamicPlatforms() {
    try {
        const r = await Auth.fetch('/admin/platforms', { method: 'GET' });
        const list = (r && r.platforms) || [];
        const sel = document.getElementById('jdNewType');
        if (!sel) return;
        // Remove old dynamic options first
        Array.from(sel.querySelectorAll('option[data-dynamic="true"]')).forEach(o => o.remove());
        list.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.slug + '_email';
            opt.textContent = p.display_name + ' Email (DB)';
            opt.setAttribute('data-dynamic', 'true');
            sel.appendChild(opt);
        });
    } catch (e) {
        console.warn('[JdSources] Konnte DB-Plattformen nicht laden:', e);
    }
}
```

- [ ] **Step 2: Call `_loadDynamicPlatforms()` after sources load**

In `JdSourcesUI.load()` (around line ~3478), find the line `_sourcesCache = list;` and add right after it:

```javascript
            await _loadDynamicPlatforms();
```

- [ ] **Step 3: Generalize `renderConfigForm` for all `*_email` types**

Find `renderConfigForm` (around line ~3600). Find the block:
```javascript
        } else if (t === 'indeed_email') {
            c.innerHTML = `
                <div class="form-group"><label>IMAP-Folder:</label>
                    <input type="text" id="jdCfgFolder" value="Indeed" placeholder="Indeed" style="width:100%"></div>
                <div class="form-group"><label>Lookback (Tage):</label>
                    <input type="number" id="jdCfgLookback" value="30" min="1" max="365" style="width:120px"></div>
                <div class="form-group" style="font-size:0.8rem;color:var(--text-muted)">Nur manueller Import via 📧 Button. User-IMAP-Credentials müssen gesetzt sein.</div>`;
        }
```

This existing block uses template-string assignment to render the form. The values inside come from a static string literal (`'Indeed'`), so it's safe — BUT we generalize by deriving the folder default from the platform slug. The slug comes from `<option value>` which is controlled (admin-set, slug-format validated server-side), so it's safe to interpolate.

Replace with:
```javascript
        } else if (t.endsWith('_email')) {
            // Generic Email-Source form: works for all hardcoded + DB platforms.
            // Folder default = capitalized platform slug.
            const platform = t.slice(0, -'_email'.length);
            const folderDefault = platform.charAt(0).toUpperCase() + platform.slice(1);
            // Build form via DOM API to avoid HTML injection from platform slug.
            while (c.firstChild) c.removeChild(c.firstChild);
            const grp1 = document.createElement('div');
            grp1.className = 'form-group';
            const lbl1 = document.createElement('label');
            lbl1.textContent = 'IMAP-Folder:';
            grp1.appendChild(lbl1);
            const inp1 = document.createElement('input');
            inp1.type = 'text';
            inp1.id = 'jdCfgFolder';
            inp1.value = folderDefault;
            inp1.placeholder = folderDefault;
            inp1.style.width = '100%';
            grp1.appendChild(inp1);
            c.appendChild(grp1);

            const grp2 = document.createElement('div');
            grp2.className = 'form-group';
            const lbl2 = document.createElement('label');
            lbl2.textContent = 'Lookback (Tage):';
            grp2.appendChild(lbl2);
            const inp2 = document.createElement('input');
            inp2.type = 'number';
            inp2.id = 'jdCfgLookback';
            inp2.value = '30';
            inp2.min = '1';
            inp2.max = '365';
            inp2.style.width = '120px';
            grp2.appendChild(inp2);
            c.appendChild(grp2);

            const note = document.createElement('div');
            note.className = 'form-group';
            note.style.fontSize = '0.8rem';
            note.style.color = 'var(--text-muted)';
            note.textContent = 'Nur manueller Import via 📧 Button. User-IMAP-Credentials müssen gesetzt sein.';
            c.appendChild(note);
        }
```

- [ ] **Step 4: Generalize `buildConfig` for all `*_email` types**

Find `buildConfig` (around line ~3635). Find:
```javascript
        if (t === 'indeed_email') return {
            folder: ($('jdCfgFolder').value || 'Indeed').trim(),
            lookback_days: parseInt($('jdCfgLookback').value, 10) || 30,
        };
```

Replace with:
```javascript
        if (t.endsWith('_email')) return {
            folder: ($('jdCfgFolder').value || '').trim() || 'INBOX',
            lookback_days: parseInt($('jdCfgLookback').value, 10) || 30,
        };
```

- [ ] **Step 5: SW Cache bump (zum 2. mal)**

```bash
grep -n "CACHE_NAME" service-worker.js | head -1
```

Increment by 1.

- [ ] **Step 6: Smoke-Test (manuell)**

```bash
./start.sh
```

Browser: Login als admin → 🌐 Plattformen → „testjobs" anlegen (Domain `testjobs.de`) → Job-Quellen-Tab → „+ Neue Quelle" → Type-Selector zeigt `testjobs Email (DB)` als Option → Type wählen → Form zeigt IMAP-Folder default `Testjobs` → Speichern.

- [ ] **Step 7: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(frontend): jobsource-type-selector mit db-plattformen dynamisch (DOM-safe)"
```

---

### Task 7: Deploy + Smoke-Test Prod

- [ ] **Step 1: Push**

```bash
git push origin master
```

- [ ] **Step 2: Deploy**

```bash
ssh ionos-vps "/usr/local/bin/bewerbungen-deploy.sh"
```

Expected: `Running upgrade ... add platform_profiles table` + `✓ Service active` + `Frontend HTTP: 200`.

- [ ] **Step 3: Smoke-Test API gegen Prod**

Token aus Browser-DevTools holen (`localStorage.access_token`).

```bash
TOKEN="..."
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  https://bewerbungen.wolfinisoftware.de/api/admin/platforms
```
Expected: `HTTP 200` + `{"platforms": []}`.

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug":"test_platform","display_name":"Test","domain":"example.com","subject_must_contain":["test"]}' \
  https://bewerbungen.wolfinisoftware.de/api/admin/platforms
```
Expected: `HTTP 201` + Plattform-JSON.

Cleanup:
```bash
curl -s -w "HTTP %{http_code}\n" -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  https://bewerbungen.wolfinisoftware.de/api/admin/platforms/test_platform
```

- [ ] **Step 4: Browser-Smoke**

Cache leeren (SW-Bump zieht), Admin-Tab öffnen, Test-Plattform anlegen, in JobSource-Selector verifizieren, danach Plattform löschen.

---

## Self-Review

**Spec-Coverage:**
- ✅ DB-Tabelle `platform_profiles` → Task 1
- ✅ Slug-Constraint + Reserved-Check → Task 4 (`_validate_payload`)
- ✅ `get_profile(slug)` Resolution → Task 2
- ✅ Auto-Generation aus Domain → Task 2
- ✅ Overrides für URL-Pattern + From-Whitelist → Task 2
- ✅ 4 API-Endpoints → Task 4
- ✅ Validation (slug, domain, regex compile, length) → Task 4
- ✅ FK-Check beim DELETE → Task 4
- ✅ Admin-only → `@admin_required` in Task 4
- ✅ Frontend Admin-Tab + Wizard → Task 5 (DOM-API für dynamische Inhalte)
- ✅ JobSource-Type-Selector dynamisch → Task 6
- ✅ Refactor PROFILES → get_profile → Task 3
- ✅ Alembic-Migration → Task 1
- ✅ Tests (Model, Resolver, API) → Task 1, 2, 4
- ✅ Deploy + Smoke → Task 7

**Security-Konsiderationen:**
- DOM-API + `textContent` für alle user-derived Werte im Frontend
- Static HTML-Skeleton ist sicher (kein user content)
- API-Validation rejects ungültige Regex via `re.compile` mit length-limit
- `@admin_required` decorator schützt alle Endpoints

**Placeholder-Scan:** Keine TBDs/TODOs/„similar to". Alle Code-Blocks komplett.

**Type-Konsistenz:**
- `PlatformProfileRow` → konsistent in allen Tasks
- `get_profile(slug: str) -> PlatformProfile` → konsistent
- `_build_profile_from_row(row)` → konsistent
- API-Routes `/api/admin/platforms[...]` → konsistent
- Frontend `PlatformsUI.{load,openCreate,edit,save,remove,closeModal}` → konsistent
