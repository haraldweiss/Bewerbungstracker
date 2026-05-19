# Email-Pattern-Lerner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI-gesteuerte adaptive Anpassung von Email-Job-Layout-Pattern (Subject/Body-Card/Filter) — bei LinkedIn/Xing/Indeed-Layout-Drift kann der User per Knopfdruck ein neues Pattern lernen lassen.

**Architecture:** Neue Tabelle `learned_email_patterns` mit Versionierung (globale Active-Row pro Plattform). Service `services/job_sources/pattern_learner.py` führt `fetch_sample_mails -> ai_learn_pattern (via ai-provider-service) -> compile_pattern -> validate_pattern` Pipeline aus. `EmailJobsAdapter._parse_email` lädt aktives Pattern aus DB und überstimmt damit hardcoded Profile-Defaults. UI: 🧠-Button pro Source + Warn-Badge bei niedriger Hit-Rate + Settings-Karte mit Rollback.

**Tech Stack:** Python 3.12 + Flask + SQLAlchemy + Alembic, jsonschema-library, ai-provider-service (Ollama/Claude), Vanilla JS Frontend, pytest.

**Spec:** [2026-05-19-email-pattern-learner-design.md](../specs/2026-05-19-email-pattern-learner-design.md)

---

## File Structure

**Create:**
- `services/job_sources/pattern_learner.py` — alle Service-Funktionen
- `alembic/versions/<hash>_add_learned_email_patterns.py` — Migration
- `tests/services/test_pattern_learner.py` — Unit-Tests
- `tests/api/test_pattern_learner_api.py` — Integration-Tests

**Modify:**
- `models.py` — `LearnedEmailPattern`-Model
- `services/job_sources/email_jobs.py` — `EmailJobsAdapter._parse_email` nutzt aktives Pattern
- `api/jobs_user.py` — 3 neue Endpoints
- `index.html` — 🧠-Button + Warn-Badge + Settings-Karte (nutzt bestehendes `JdSourcesUI`-Rendering-Pattern mit `escapeHtml`-Sanitizer wie der bestehende `refresh()` und `renderTypeFields()`)
- `service-worker.js` — CACHE_NAME v39 → v42

**UI-Note:** Bestehender `JdSourcesUI`-Code nutzt Vanilla DOM mit `escapeHtml(...)`-Sanitization vor jedem User-Input-Insert (siehe z.B. Zeilen rund um `tbody` in index.html). Neue UI-Snippets folgen dem **identischen Pattern**, escapen alle User-/Server-Daten konsequent.

---

### Task 1: SQLAlchemy-Modell + Alembic-Migration

**Files:**
- Modify: `models.py` (neue Klasse `LearnedEmailPattern`)
- Create: `alembic/versions/<hash>_add_learned_email_patterns.py`

- [ ] **Step 1: SQLAlchemy-Modell hinzufügen**

In `models.py` ans Ende einfügen:

```python
class LearnedEmailPattern(db.Model):
    """Pro Plattform gelerntes Layout-Pattern (Email-Job-Source-Adapter).

    Versionierung: jedes Train erzeugt eine neue Row, alte wird is_active=False.
    Rollback: aktuelle deaktivieren + vorige wieder aktivieren.
    Partial-Unique-Constraint: max 1 is_active=True pro Plattform.
    """
    __tablename__ = 'learned_email_patterns'

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(32), nullable=False, index=True)
    pattern_json = db.Column(db.Text, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    hit_rate = db.Column(db.Float, nullable=False)
    trained_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trained_by_user_id = db.Column(
        db.String(36), db.ForeignKey('users.id'), nullable=False
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    rolled_back_at = db.Column(db.DateTime, nullable=True)
    rolled_back_by_user_id = db.Column(
        db.String(36), db.ForeignKey('users.id'), nullable=True
    )

    __table_args__ = (
        db.Index(
            'ux_lep_one_active_per_platform',
            'platform',
            unique=True,
            sqlite_where=db.text('is_active = 1'),
            postgresql_where=db.text('is_active = TRUE'),
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'pattern_json': self.pattern_json,
            'sample_count': self.sample_count,
            'hit_rate': self.hit_rate,
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'trained_by_user_id': self.trained_by_user_id,
            'is_active': self.is_active,
            'rolled_back_at': self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            'rolled_back_by_user_id': self.rolled_back_by_user_id,
        }
```

- [ ] **Step 2: Alembic-Migration generieren**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker/.claude/worktrees/confident-mendeleev-17fcde
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/alembic revision -m "add_learned_email_patterns"
```

Expected: Datei `alembic/versions/<hash>_add_learned_email_patterns.py` wird erzeugt.

- [ ] **Step 3: Migration-Body schreiben**

Generierten Skelett-File mit folgendem Inhalt füllen (Revision-IDs vom Auto-Generator UNVERÄNDERT übernehmen):

```python
"""add_learned_email_patterns"""
from alembic import op
import sqlalchemy as sa

revision = '<as-generated>'
down_revision = '<as-generated>'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'learned_email_patterns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('platform', sa.String(32), nullable=False),
        sa.Column('pattern_json', sa.Text(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('hit_rate', sa.Float(), nullable=False),
        sa.Column('trained_at', sa.DateTime(), nullable=False),
        sa.Column('trained_by_user_id', sa.String(36),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
        sa.Column('rolled_back_by_user_id', sa.String(36),
                  sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index(
        'ix_learned_email_patterns_platform',
        'learned_email_patterns', ['platform']
    )
    op.create_index(
        'ux_lep_one_active_per_platform',
        'learned_email_patterns', ['platform'],
        unique=True,
        sqlite_where=sa.text('is_active = 1'),
        postgresql_where=sa.text('is_active = TRUE'),
    )


def downgrade():
    op.drop_index('ux_lep_one_active_per_platform', 'learned_email_patterns')
    op.drop_index('ix_learned_email_patterns_platform', 'learned_email_patterns')
    op.drop_table('learned_email_patterns')
```

- [ ] **Step 4: Migration anwenden**

```bash
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/alembic upgrade head 2>&1 | tail -5
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade <prev> -> <new>, add_learned_email_patterns`.

- [ ] **Step 5: Smoke-Test des Modells**

```bash
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/python -c "
from app import create_app
from models import LearnedEmailPattern, db
app = create_app()
with app.app_context():
    print('Table exists:', db.engine.dialect.has_table(db.engine.connect(), 'learned_email_patterns'))
"
```

Expected: `Table exists: True`.

- [ ] **Step 6: Commit**

```bash
git add models.py alembic/versions/
git commit -m "feat(models): LearnedEmailPattern + Alembic-Migration"
```

---

### Task 2: JSON-Schema + Schema-Validation

**Files:**
- Create: `services/job_sources/pattern_learner.py`
- Create: `tests/services/test_pattern_learner.py`

- [ ] **Step 1: Schema-Tests schreiben (failing)**

```python
# tests/services/test_pattern_learner.py
"""Unit-Tests für Pattern-Lerner."""
import pytest
from services.job_sources.pattern_learner import (
    PATTERN_JSON_SCHEMA, validate_pattern_schema,
)


def test_valid_pattern_passes():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung"],
            "company_blacklist_separators": ["----"],
        },
    }
    assert validate_pattern_schema(p) == []


def test_invalid_pattern_missing_subject_pattern():
    p = {
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    errors = validate_pattern_schema(p)
    assert len(errors) >= 1
    assert any("subject_pattern" in e for e in errors)


def test_invalid_pattern_wrong_type():
    p = {
        "subject_pattern": {
            "prefix_optional": "not a bool",  # invalid
            "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1


def test_invalid_pattern_extra_field_rejected():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
            "evil_field": "drop table users",
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1
```

- [ ] **Step 2: Tests fail**

```bash
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/python -m pytest tests/services/test_pattern_learner.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'services.job_sources.pattern_learner'`.

- [ ] **Step 3: Modul implementieren**

```python
# services/job_sources/pattern_learner.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""AI-gesteuerter Pattern-Lerner für Email-Job-Adapter."""
from __future__ import annotations
import json
import re
from typing import Any

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None


PATTERN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject_pattern", "body_card", "filters"],
    "properties": {
        "subject_pattern": {
            "type": "object",
            "additionalProperties": False,
            "required": ["prefix_optional", "prefix_keywords", "separator"],
            "properties": {
                "prefix_optional": {"type": "boolean"},
                "prefix_keywords": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 80},
                    "maxItems": 20,
                },
                "separator": {"type": "string", "maxLength": 50},
            },
        },
        "body_card": {
            "type": "object",
            "additionalProperties": False,
            "required": ["url_labels", "fields_before_url", "separator_lines_allowed"],
            "properties": {
                "url_labels": {
                    "type": "array", "minItems": 1, "maxItems": 10,
                    "items": {"type": "string", "maxLength": 80},
                },
                "fields_before_url": {
                    "type": "array", "minItems": 1, "maxItems": 5,
                    "items": {"enum": ["title", "company", "location", "extra"]},
                },
                "separator_lines_allowed": {
                    "type": "integer", "minimum": 0, "maximum": 20,
                },
            },
        },
        "filters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title_blacklist", "company_blacklist_separators"],
            "properties": {
                "title_blacklist": {
                    "type": "array", "maxItems": 50,
                    "items": {"type": "string", "maxLength": 200},
                },
                "company_blacklist_separators": {
                    "type": "array", "maxItems": 10,
                    "items": {"type": "string", "maxLength": 50},
                },
            },
        },
    },
}


def validate_pattern_schema(pattern: dict) -> list[str]:
    """Returns list of validation errors (empty if valid)."""
    if Draft7Validator is None:
        raise RuntimeError("jsonschema library not installed")
    validator = Draft7Validator(PATTERN_JSON_SCHEMA)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(pattern)
    ]
```

- [ ] **Step 4: jsonschema installiert sicherstellen**

```bash
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/pip show jsonschema 2>/dev/null | head -1 || /Library/WebServer/Documents/Bewerbungstracker/venv/bin/pip install jsonschema
```

Falls in `requirements.txt` nicht enthalten: `jsonschema>=4.0` ergänzen.

- [ ] **Step 5: Tests grün** — 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/pattern_learner.py tests/services/test_pattern_learner.py requirements.txt
git commit -m "feat(pattern-learner): JSON-Schema + Validator (strict additionalProperties=False)"
```

---

### Task 3: compile_pattern - JSON zu Regex

**Files:**
- Modify: `services/job_sources/pattern_learner.py`
- Modify: `tests/services/test_pattern_learner.py`

- [ ] **Step 1: Tests ergänzen**

```python
from services.job_sources.pattern_learner import compile_pattern, CompiledPattern


def _valid_pattern_dict():
    return {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle", "Job alert"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen", "View job"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung", "Top-Jobs"],
            "company_blacklist_separators": ["----", "===="],
        },
    }


def test_compile_returns_compiled_pattern():
    cp = compile_pattern(_valid_pattern_dict())
    assert isinstance(cp, CompiledPattern)
    assert cp.body_card_re is not None
    assert cp.subject_re is not None
    assert cp.title_blacklist_re is not None


def test_compile_body_card_matches_linkedin_layout():
    cp = compile_pattern(_valid_pattern_dict())
    body = (
        "Senior Cybersecurity Consultant (m,w,d)\r\n"
        "QESTIT DACH\r\n"
        "Deutschland\r\n"
        "Mit Lebenslauf und Profil bewerben\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/4410189303/"
    )
    matches = list(cp.body_card_re.finditer(body))
    assert len(matches) >= 1
    m = matches[0]
    assert "Senior Cybersecurity Consultant" in m.group('title')
    assert "QESTIT DACH" in m.group('company')
    assert "Deutschland" in m.group('location')
    assert "linkedin.com/comm/jobs/view/4410189303" in m.group('url')


def test_compile_subject_optional_prefix():
    cp = compile_pattern(_valid_pattern_dict())
    m = cp.subject_re.match("Senior Engineer bei Acme GmbH")
    assert m and m.group('title') == "Senior Engineer" and m.group('company') == "Acme GmbH"
    m = cp.subject_re.match("Neue Stelle: Junior Dev bei Bcorp")
    assert m


def test_compile_title_blacklist():
    cp = compile_pattern(_valid_pattern_dict())
    assert cp.title_blacklist_re.search("Ihre Jobbenachrichtigung")
    assert cp.title_blacklist_re.search("Top-Jobs für Sie")
    assert not cp.title_blacklist_re.search("Senior Engineer")
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: compile_pattern implementieren**

In `services/job_sources/pattern_learner.py` ergänzen:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledPattern:
    body_card_re: "re.Pattern"
    subject_re: "re.Pattern"
    title_blacklist_re: "re.Pattern | None"
    company_blacklist_separator_re: "re.Pattern | None"
    url_labels: tuple[str, ...]


_FIELD_BUILDERS = {
    "title":    r"[ \t]*(?P<title>\S[^\r\n]{2,200}\S)\s*\r?\n",
    "company":  r"[ \t]*(?P<company>\S[^\r\n]{1,150}\S)\s*\r?\n",
    "location": r"[ \t]*(?P<location>\S[^\r\n]{1,80}\S)\s*\r?\n",
    "extra":    r"[^\r\n]*\r?\n",
}


def compile_pattern(pattern: dict) -> CompiledPattern:
    """Baut Regex-Objekte aus JSON-Pattern. Raises ValueError bei unbekannten Feldern."""
    body_card = pattern["body_card"]
    parts = []
    for field in body_card["fields_before_url"]:
        if field not in _FIELD_BUILDERS:
            raise ValueError(f"Unknown field: {field}")
        parts.append(_FIELD_BUILDERS[field])
    n_sep = body_card["separator_lines_allowed"]
    parts.append(rf"(?:[^\r\n]*\r?\n){{0,{n_sep}}}?")
    labels_alt = "|".join(re.escape(lbl) for lbl in body_card["url_labels"])
    parts.append(rf"\s*(?:{labels_alt})\s*:?\s*")
    parts.append(r"(?P<url>https?://[^\s\r\n)<>\"']+)")
    body_card_re = re.compile("^" + "".join(parts), re.IGNORECASE | re.MULTILINE)

    sp = pattern["subject_pattern"]
    prefix_alt = "|".join(re.escape(kw) for kw in sp["prefix_keywords"]) or "."
    sep = sp["separator"]
    prefix_part = (
        rf"(?:(?:{prefix_alt})\s*:?\s*)?"
        if sp["prefix_optional"]
        else rf"(?:{prefix_alt})\s*:?\s*"
    )
    subject_re = re.compile(
        rf"^{prefix_part}(?P<title>.+?)\s+(?:{sep})\s+(?P<company>.+?)\s*$",
        re.IGNORECASE,
    )

    tb = pattern["filters"]["title_blacklist"]
    title_blacklist_re = None
    if tb:
        title_blacklist_re = re.compile(
            "|".join(f"(?:{phrase})" for phrase in tb),
            re.IGNORECASE,
        )

    cbs = pattern["filters"]["company_blacklist_separators"]
    company_blacklist_separator_re = None
    if cbs:
        company_blacklist_separator_re = re.compile(
            "^(?:" + "|".join(re.escape(s) for s in cbs) + r")+$"
        )

    return CompiledPattern(
        body_card_re=body_card_re,
        subject_re=subject_re,
        title_blacklist_re=title_blacklist_re,
        company_blacklist_separator_re=company_blacklist_separator_re,
        url_labels=tuple(body_card["url_labels"]),
    )
```

- [ ] **Step 4: Tests grün** — 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/pattern_learner.py tests/services/test_pattern_learner.py
git commit -m "feat(pattern-learner): compile_pattern baut Regex aus JSON"
```

---

### Task 4: validate_pattern - Hit-Rate auf Samples

**Files:**
- Modify: `services/job_sources/pattern_learner.py`
- Modify: `tests/services/test_pattern_learner.py`

- [ ] **Step 1: Tests**

```python
from services.job_sources.pattern_learner import validate_pattern


def _sample_mails():
    body_match = (
        "Senior Engineer\r\nAcme GmbH\r\nBerlin\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/123"
    )
    body_nojob = "Random newsletter content with no job structure."
    return [
        {"subject": "Senior Engineer bei Acme GmbH", "body": body_match},
        {"subject": "DevOps bei Bcorp", "body": body_match.replace("Acme", "Bcorp")},
        {"subject": "Frontend bei Ccorp", "body": body_match.replace("Acme", "Ccorp")},
        {"subject": "Random Newsletter", "body": body_nojob},
    ]


def test_validate_counts_hits():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, _sample_mails())
    assert hit_rate == 0.75
    assert sum(1 for d in diags if d["matched"]) == 3


def test_validate_empty():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, [])
    assert hit_rate == 0.0 and diags == []


def test_validate_missing_body():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, _ = validate_pattern(cp, [
        {"subject": "Test", "body": None},
        {"subject": "Test", "body": ""},
    ])
    assert hit_rate == 0.0
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Implementieren**

```python
def validate_pattern(compiled: CompiledPattern, samples: list[dict]) -> tuple[float, list[dict]]:
    """Hit-Rate auf Sample-Mails. Returns (hit_rate, diagnostics)."""
    if not samples:
        return 0.0, []
    diagnostics: list[dict] = []
    matched_count = 0
    for em in samples:
        body = em.get("body") or ""
        cards = list(compiled.body_card_re.finditer(body))
        valid_cards = []
        for m in cards:
            t = (m.group("title") or "").strip()
            c = (m.group("company") or "").strip() if "company" in m.groupdict() else ""
            if compiled.title_blacklist_re and compiled.title_blacklist_re.search(t):
                continue
            if (
                compiled.company_blacklist_separator_re
                and c
                and compiled.company_blacklist_separator_re.match(c)
            ):
                continue
            valid_cards.append(m)
        is_match = len(valid_cards) > 0
        if is_match:
            matched_count += 1
        diagnostics.append({
            "subject": (em.get("subject") or "")[:80],
            "matched": is_match, "card_count": len(valid_cards),
        })
    return matched_count / len(samples), diagnostics
```

- [ ] **Step 4: Tests grün** — 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/pattern_learner.py tests/services/test_pattern_learner.py
git commit -m "feat(pattern-learner): validate_pattern berechnet Hit-Rate"
```

---

### Task 5: fetch_sample_mails

**Files:**
- Modify: `services/job_sources/pattern_learner.py`
- Modify: `tests/services/test_pattern_learner.py`

- [ ] **Step 1: Tests**

```python
from unittest.mock import MagicMock, patch
from services.job_sources.pattern_learner import fetch_sample_mails


def test_fetch_delegates_to_adapter():
    user = MagicMock()
    user.imap_host = "imap.gmail.com"
    user.imap_user = "u@x.de"
    user.decrypted_imap_password = "pw"
    fake_mails = [{"subject": "X", "body": "Y"}] * 10
    with patch(
        "services.job_sources.email_jobs.EmailJobsAdapter._fetch_emails",
        return_value=fake_mails,
    ) as m:
        result = fetch_sample_mails(
            user, platform="linkedin",
            folder="INBOX", lookback_days=30, n=10,
        )
    assert result == fake_mails
    assert m.called


def test_fetch_unknown_platform():
    user = MagicMock()
    with pytest.raises(ValueError, match="Unknown platform"):
        fetch_sample_mails(user, platform="myspace",
                           folder="INBOX", lookback_days=30, n=10)
```

- [ ] **Step 2: Implementieren**

```python
def fetch_sample_mails(
    user, platform: str, folder: str, lookback_days: int, n: int = 30,
) -> list[dict]:
    """IMAP-Fetch via EmailJobsAdapter. Raises ValueError bei unbekannter Plattform."""
    from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
    if platform not in PROFILES:
        raise ValueError(f"Unknown platform: {platform}")
    adapter = EmailJobsAdapter(
        config={"folder": folder, "lookback_days": lookback_days, "limit": n},
        user=user,
        platform_profile=PROFILES[platform],
    )
    host = user.imap_host
    imap_user = user.imap_user
    pw = user.decrypted_imap_password
    if not host or not imap_user or not pw:
        raise RuntimeError("User hat keine IMAP-Credentials")
    return adapter._fetch_emails(host, imap_user, pw, folder, lookback_days, n)
```

- [ ] **Step 3: Tests grün** — 13 PASS.

- [ ] **Step 4: Commit**

```bash
git add services/job_sources/pattern_learner.py tests/services/test_pattern_learner.py
git commit -m "feat(pattern-learner): fetch_sample_mails delegiert IMAP an Adapter"
```

---

### Task 6: ai_learn_pattern mit Schema-Retry

**Files:**
- Modify: `services/job_sources/pattern_learner.py`
- Modify: `tests/services/test_pattern_learner.py`

- [ ] **Step 1: Tests (gemockt)**

```python
import json
from unittest.mock import MagicMock, patch
from services.job_sources.pattern_learner import ai_learn_pattern


def test_ai_learn_success(monkeypatch):
    valid = json.dumps(_valid_pattern_dict())
    fake_chat = MagicMock(return_value={"content": valid, "provider": "ollama", "model": "q"})
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="test-uid", ai_provider="ollama", ai_provider_model="qwen2.5")
    result = ai_learn_pattern(user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin")
    assert result == _valid_pattern_dict()


def test_ai_learn_invalid_json_retries_then_raises(monkeypatch):
    fake_chat = MagicMock(return_value={"content": "not json", "provider": "ollama", "model": "q"})
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="t", ai_provider="ollama", ai_provider_model="q")
    with pytest.raises(RuntimeError, match="AI"):
        ai_learn_pattern(user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin")
    assert fake_chat.call_count == 2


def test_ai_learn_schema_fail_retries_then_raises(monkeypatch):
    invalid_schema = json.dumps({"random": "structure"})
    fake_chat = MagicMock(return_value={"content": invalid_schema, "provider": "ollama", "model": "q"})
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="t", ai_provider="ollama", ai_provider_model="q")
    with pytest.raises(RuntimeError, match="Schema"):
        ai_learn_pattern(user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin")
    assert fake_chat.call_count == 2
```

- [ ] **Step 2: Implementieren**

```python
import logging
logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "Du bist ein Mail-Layout-Analyst. Aus den vorgelegten Job-Empfehlungs-"
    "Mails extrahierst du das Layout-Pattern und gibst es als striktes JSON "
    "zurück. KEIN Markdown-Wrapping, KEINE Kommentare, KEINE zusätzlichen "
    "Felder außerhalb des Schemas."
)


def _build_user_prompt(train_samples: list[dict], platform: str, strict: bool = False) -> str:
    lines = [
        f"Platform: {platform}", "",
        "Schema (must match exactly, no extra fields):",
        json.dumps(PATTERN_JSON_SCHEMA, indent=2), "",
        "Sample mails (parse layout from these):",
    ]
    for i, em in enumerate(train_samples):
        subj = (em.get("subject") or "")[:200]
        body = (em.get("body") or "")[:6000]
        lines.append(f"\n--- Mail {i+1} ---\nSubject: {subj}\nBody:\n{body}\n")
    lines.append("\nReturn ONLY the JSON pattern. No prose, no markdown fences.")
    if strict:
        lines.append(
            "\nIMPORTANT: previous attempt failed schema validation. "
            "Ensure EVERY required field is present, types correct, "
            "no extra fields, no markdown."
        )
    return "\n".join(lines)


def ai_learn_pattern(user, train_samples: list[dict], platform: str) -> dict:
    """AI-Call mit Schema-Validation + 1 Retry. Raises RuntimeError bei final-fail."""
    from services.ai_provider_client import AIProviderClient
    client = AIProviderClient(user=user)

    last_error = None
    for attempt in (1, 2):
        strict = (attempt == 2)
        prompt = _build_user_prompt(train_samples, platform, strict=strict)
        try:
            result = client.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.1,
            )
        except Exception as exc:
            last_error = f"AI-Call failed: {exc}"
            logger.warning("ai_learn_pattern attempt %d: %s", attempt, last_error)
            continue
        content = (result or {}).get("content", "").strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rstrip("`").strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = f"AI-Output kein valides JSON: {exc}"
            logger.warning("ai_learn_pattern attempt %d: %s", attempt, last_error)
            continue
        errors = validate_pattern_schema(parsed)
        if errors:
            last_error = f"Schema-Fehler: {'; '.join(errors[:3])}"
            logger.warning("ai_learn_pattern attempt %d: %s", attempt, last_error)
            continue
        return parsed
    raise RuntimeError(f"ai_learn_pattern failed after 2 attempts: {last_error}")
```

- [ ] **Step 3: Tests grün** — 16 PASS.

- [ ] **Step 4: Commit**

```bash
git add services/job_sources/pattern_learner.py tests/services/test_pattern_learner.py
git commit -m "feat(pattern-learner): ai_learn_pattern mit Schema-Retry"
```

---

### Task 7: POST /train-pattern Endpoint

**Files:**
- Modify: `api/jobs_user.py`
- Create: `tests/api/test_pattern_learner_api.py`

- [ ] **Step 1: Integration-Tests**

```python
# tests/api/test_pattern_learner_api.py
import json
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from models import db, JobSource, User, LearnedEmailPattern


def _make_source(db_session, user, type_="linkedin_email"):
    src = JobSource(
        user_id=user.id, type=type_, name="LinkedIn",
        config={"folder": "INBOX", "lookback_days": 30, "limit": 30},
        enabled=True,
    )
    db_session.add(src); db_session.commit()
    return src


def _fake_pattern():
    return {
        "subject_pattern": {"prefix_optional": True, "prefix_keywords": [], "separator": "bei"},
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }


def test_train_pattern_happy_path(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    src = _make_source(db_session, user)
    body = "X\r\nY\r\nDE\r\nJobangebot ansehen: https://linkedin.com/comm/jobs/view/1"
    fake_mails = [{"subject": "X bei Y", "body": body}] * 30
    with patch("services.job_sources.pattern_learner.fetch_sample_mails", return_value=fake_mails), \
         patch("services.job_sources.pattern_learner.ai_learn_pattern", return_value=_fake_pattern()):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=auth_header, json={},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["hit_rate"] >= 0.40
    active = LearnedEmailPattern.query.filter_by(platform="linkedin", is_active=True).first()
    assert active is not None and active.trained_by_user_id == user.id


def test_train_rate_limited(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    src = _make_source(db_session, user)
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json="{}", sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow() - timedelta(minutes=30),
        trained_by_user_id=user.id, is_active=True,
    ))
    db_session.commit()
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=auth_header, json={},
    )
    assert resp.status_code == 429


def test_train_hit_rate_too_low(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    src = _make_source(db_session, user)
    fake_mails = [{"subject": "S", "body": "no structure"}] * 30
    with patch("services.job_sources.pattern_learner.fetch_sample_mails", return_value=fake_mails), \
         patch("services.job_sources.pattern_learner.ai_learn_pattern", return_value=_fake_pattern()):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=auth_header, json={},
        )
    assert resp.status_code == 422
    assert LearnedEmailPattern.query.filter_by(platform="linkedin").count() == 0


def test_train_non_email_source(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    src = _make_source(db_session, user, type_="rss")
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=auth_header, json={},
    )
    assert resp.status_code == 400


def test_train_forbidden(client, auth_header, db_session):
    other = User(email="other@x.de", password_hash="x")
    db_session.add(other); db_session.commit()
    src = _make_source(db_session, other)
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=auth_header, json={},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Endpoint implementieren**

In `api/jobs_user.py`:

```python
@jobs_user_bp.post('/sources/<int:source_id>/train-pattern')
@token_required
def train_pattern(user, source_id):
    """AI-Pattern-Train für Email-Source."""
    from services.job_sources import pattern_learner as pl
    from models import LearnedEmailPattern
    from datetime import datetime, timedelta
    import json as _json
    import re as _re

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if src.type not in _EMAIL_SOURCE_TYPES:
        return jsonify({"error": "Source ist kein Email-Typ"}), 400

    platform = src.type.removesuffix("_email")
    data = request.get_json(silent=True) or {}
    sample_size = int(data.get("sample_size") or 30)
    train_size = int(data.get("train_size") or 5)
    min_hit_rate = float(data.get("min_hit_rate") or 0.40)

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent = LearnedEmailPattern.query.filter(
        LearnedEmailPattern.platform == platform,
        LearnedEmailPattern.trained_at > one_hour_ago,
    ).first()
    if recent is not None:
        return jsonify({
            "error": "Rate-Limit: max 1 Pattern-Train pro Plattform pro Stunde.",
            "last_trained_at": recent.trained_at.isoformat(),
        }), 429

    try:
        mails = pl.fetch_sample_mails(
            user, platform=platform,
            folder=src.config.get("folder", "INBOX"),
            lookback_days=int(src.config.get("lookback_days", 30)),
            n=sample_size,
        )
    except RuntimeError as exc:
        return jsonify({"error": f"IMAP-Fetch fehlgeschlagen: {exc}"}), 400
    if len(mails) < train_size + 1:
        return jsonify({
            "error": f"Zu wenig Mails ({len(mails)}) für Training (mind. {train_size + 1} nötig)."
        }), 400

    train = mails[:train_size]
    test = mails[train_size:]

    try:
        pattern = pl.ai_learn_pattern(user, train_samples=train, platform=platform)
    except RuntimeError as exc:
        return jsonify({"error": f"AI-Train fehlgeschlagen: {exc}"}), 502

    try:
        compiled = pl.compile_pattern(pattern)
    except (ValueError, _re.error) as exc:
        return jsonify({"error": f"Pattern-Compile fehlgeschlagen: {exc}"}), 502

    hit_rate, diagnostics = pl.validate_pattern(compiled, test)
    if hit_rate < min_hit_rate:
        return jsonify({
            "error": "Hit-Rate unter Schwelle - Pattern nicht aktiviert.",
            "hit_rate": hit_rate, "min_hit_rate": min_hit_rate,
            "sample_count": len(test), "diagnostics": diagnostics[:10],
        }), 422

    LearnedEmailPattern.query.filter_by(platform=platform, is_active=True).update(
        {"is_active": False}
    )
    new_row = LearnedEmailPattern(
        platform=platform, pattern_json=_json.dumps(pattern),
        sample_count=len(test), hit_rate=hit_rate,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    )
    db.session.add(new_row)
    db.session.commit()

    return jsonify({
        "ok": True, "hit_rate": hit_rate, "sample_count": len(test),
        "pattern": pattern,
        "example_matches": [d for d in diagnostics if d["matched"]][:3],
    }), 200
```

- [ ] **Step 4: Tests grün** — 5 neue PASS, 79 bestehende Email-Tests grün bleiben.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_pattern_learner_api.py
git commit -m "feat(jobs): POST /train-pattern Endpoint mit Rate-Limit + Validation"
```

---

### Task 8: GET /learned-patterns Endpoint

**Files:**
- Modify: `api/jobs_user.py`
- Modify: `tests/api/test_pattern_learner_api.py`

- [ ] **Step 1: Test**

```python
def test_get_learned_patterns(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json="{}", sample_count=20, hit_rate=0.55,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    ))
    db_session.commit()
    resp = client.get("/api/jobs/learned-patterns", headers=auth_header)
    assert resp.status_code == 200
    platforms = {p["platform"] for p in resp.get_json()["patterns"]}
    assert "linkedin" in platforms
    for p in resp.get_json()["patterns"]:
        assert "history_count" in p
```

- [ ] **Step 2: Endpoint**

```python
@jobs_user_bp.get('/learned-patterns')
@token_required
def list_learned_patterns(user):
    from models import LearnedEmailPattern
    active_rows = LearnedEmailPattern.query.filter_by(is_active=True).all()
    out = []
    for row in active_rows:
        history_count = LearnedEmailPattern.query.filter(
            LearnedEmailPattern.platform == row.platform,
            LearnedEmailPattern.id != row.id,
        ).count()
        d = row.to_dict()
        d["history_count"] = history_count
        out.append(d)
    return jsonify({"patterns": out}), 200
```

- [ ] **Step 3: Tests grün** — 6 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/jobs_user.py tests/api/test_pattern_learner_api.py
git commit -m "feat(jobs): GET /learned-patterns Endpoint"
```

---

### Task 9: POST /rollback Endpoint

**Files:**
- Modify: `api/jobs_user.py`
- Modify: `tests/api/test_pattern_learner_api.py`

- [ ] **Step 1: Tests**

```python
def test_rollback_restores_previous(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    older = LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":1}', sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow() - timedelta(days=2),
        trained_by_user_id=user.id, is_active=False,
    )
    newer = LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":2}', sample_count=20, hit_rate=0.7,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id, is_active=True,
    )
    db_session.add_all([older, newer]); db_session.commit()
    resp = client.post(
        "/api/jobs/learned-patterns/linkedin/rollback",
        headers=auth_header, json={},
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert LearnedEmailPattern.query.filter_by(pattern_json='{"v":1}').first().is_active is True


def test_rollback_no_history(client, auth_header, db_session):
    user = User.query.filter_by(email="test@test.de").first()
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json='{}', sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    ))
    db_session.commit()
    resp = client.post(
        "/api/jobs/learned-patterns/linkedin/rollback",
        headers=auth_header, json={},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Endpoint**

```python
@jobs_user_bp.post('/learned-patterns/<string:platform>/rollback')
@token_required
def rollback_pattern(user, platform):
    from models import LearnedEmailPattern
    from datetime import datetime as _datetime
    current = LearnedEmailPattern.query.filter_by(
        platform=platform, is_active=True,
    ).first()
    if current is None:
        return jsonify({"error": "Keine aktive Pattern-Version"}), 400
    prev = LearnedEmailPattern.query.filter(
        LearnedEmailPattern.platform == platform,
        LearnedEmailPattern.trained_at < current.trained_at,
    ).order_by(LearnedEmailPattern.trained_at.desc()).first()
    if prev is None:
        return jsonify({"error": "Keine ältere Version vorhanden - kann nicht rollback."}), 400
    current.is_active = False
    current.rolled_back_at = _datetime.utcnow()
    current.rolled_back_by_user_id = user.id
    prev.is_active = True
    db.session.commit()
    return jsonify({
        "ok": True,
        "rolled_back_from": current.to_dict(),
        "restored_pattern": prev.to_dict(),
    }), 200
```

- [ ] **Step 3: Tests grün** — 8 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/jobs_user.py tests/api/test_pattern_learner_api.py
git commit -m "feat(jobs): POST /learned-patterns/<platform>/rollback"
```

---

### Task 10: Adapter-Integration

**Files:**
- Modify: `services/job_sources/email_jobs.py:EmailJobsAdapter`
- Modify: `tests/services/test_email_jobs_adapter.py`

- [ ] **Step 1: Test für Learned-Pattern-Override**

```python
import json
from datetime import datetime
from models import LearnedEmailPattern


def test_adapter_uses_learned_when_active(app, db_session):
    """Aktives LearnedEmailPattern überstimmt das hardcoded body_card_re."""
    learned = LearnedEmailPattern(
        platform="linkedin",
        pattern_json=json.dumps({
            "subject_pattern": {"prefix_optional": True, "prefix_keywords": [], "separator": "bei"},
            "body_card": {
                "url_labels": ["MAGIC_LABEL"],
                "fields_before_url": ["title", "company", "location"],
                "separator_lines_allowed": 5,
            },
            "filters": {"title_blacklist": [], "company_blacklist_separators": []},
        }),
        sample_count=10, hit_rate=0.8,
        trained_at=datetime.utcnow(),
        trained_by_user_id="test-uid", is_active=True,
    )
    db_session.add(learned); db_session.commit()

    from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
    from unittest.mock import MagicMock
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    em = {
        "subject": "Senior Dev bei Acme",
        "from": "jobs@linkedin.com",
        "body": (
            "Senior Dev\r\nAcme GmbH\r\nDE\r\n"
            "MAGIC_LABEL: https://linkedin.com/comm/jobs/view/999"
        ),
        "date": "2026-05-19T10:00:00",
    }
    jobs = adapter.parse_emails([em])
    assert len(jobs) == 1
    assert "999" in jobs[0].url
```

- [ ] **Step 2: Test fail**

- [ ] **Step 3: Adapter anpassen**

(a) In `__init__` ergänzen:
```python
self._learned_compiled = None
self._learned_lookup_done = False
```

(b) Neue Methode:
```python
def _get_learned_pattern(self):
    """Lazy-load learned pattern from DB, cached for adapter lifetime."""
    if self._learned_lookup_done:
        return self._learned_compiled
    self._learned_lookup_done = True
    try:
        from models import LearnedEmailPattern
        from services.job_sources.pattern_learner import compile_pattern
        import json as _json
        row = LearnedEmailPattern.query.filter_by(
            platform=self.profile.name, is_active=True,
        ).first()
        if row is None:
            return None
        self._learned_compiled = compile_pattern(_json.loads(row.pattern_json))
    except Exception as exc:
        logger.warning("Learned-pattern-lookup fehlgeschlagen für %s: %s",
                       self.profile.name, exc)
        self._learned_compiled = None
    return self._learned_compiled
```

(c) In `_parse_email`, **Zeile mit** `if self.profile.body_card_re is not None:` ersetzen durch:

```python
learned = self._get_learned_pattern()
active_card_re = learned.body_card_re if learned else self.profile.body_card_re
active_title_blacklist = learned.title_blacklist_re if learned else None
active_company_sep = learned.company_blacklist_separator_re if learned else None
if active_card_re is not None:
    cards = list(active_card_re.finditer(body))
```

(d) Im Card-Filter-Block (skip-logic für Trenner) zusätzlich:
```python
if active_title_blacklist and active_title_blacklist.search(t):
    continue
if active_company_sep and c and active_company_sep.match(c):
    continue
```

- [ ] **Step 4: Tests grün** — Adapter-Tests 6 PASS, alle email-Tests bleiben grün.

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/email_jobs.py tests/services/test_email_jobs_adapter.py
git commit -m "feat(email-jobs): Adapter nutzt aktives LearnedEmailPattern wenn vorhanden"
```

---

### Task 11: UI - 🧠-Button + Confirm-Dialog

**Files:**
- Modify: `index.html` (JdSourcesUI module)
- Modify: `service-worker.js` (CACHE_NAME bump)

**UI-Pattern-Note:** `JdSourcesUI.refresh()` und `renderTypeFields()` nutzen `tbody.innerHTML = templateString` mit `escapeHtml(...)` für alle User-/Server-Daten. Neue UI-Snippets folgen diesem identischen Pattern.

- [ ] **Step 1: 🧠-Button in Source-Action-Spalte**

Im Action-Block (suche `s.type && s.type.endsWith('_email')`):

Original:
```javascript
${s.type && s.type.endsWith('_email')
    ? `<button class="btn btn-sm btn-primary" onclick="JdSourcesUI.importFromEmail(${s.id})" title="Import aus IMAP-Folder">📧 Import</button>`
    : `<button class="btn btn-sm" onclick="JdSourcesUI.testCrawl(${s.id})" title="Test-Crawl">🧪</button>`}
```

Ersetzen mit:
```javascript
${s.type && s.type.endsWith('_email')
    ? `<button class="btn btn-sm btn-primary" onclick="JdSourcesUI.importFromEmail(${s.id})" title="Import aus IMAP-Folder">📧 Import</button>
       <button class="btn btn-sm" onclick="JdSourcesUI.trainPattern(${s.id})" title="Pattern für diese Plattform neu lernen (AI-Analyse, ca. 30-60s)">🧠 Lernen</button>`
    : `<button class="btn btn-sm" onclick="JdSourcesUI.testCrawl(${s.id})" title="Test-Crawl">🧪</button>`}
```

- [ ] **Step 2: trainPattern-Funktion**

Nach `importFromEmail` einfügen:

```javascript
async function trainPattern(sourceId) {
    const src = (state && state.sourcesCache || []).find(s => s.id === sourceId);
    if (!src) { alert('Quelle nicht gefunden (refresh nötig)'); return; }
    const platform = (src.type || '').replace('_email', '');
    const confirmText = (
        `🧠 Pattern für ${platform.toUpperCase()} neu lernen?\n\n` +
        `• Lädt 30 aktuelle Mails aus deinem IMAP-Folder\n` +
        `• 5 Mails an deinen AI-Provider zur Layout-Analyse\n` +
        `• 25 Test-Mails validieren das Pattern (Schwelle: 40%)\n` +
        `• Bei Erfolg: Pattern wird für ALLE Nutzer dieser Plattform aktiv\n` +
        `• Bei Fehlschlag: aktuelles Pattern bleibt unverändert\n\n` +
        `Dauer: 30-60 s. Kosten: 0 EUR (Ollama) bzw. ~0.01 EUR (Claude).\n\n` +
        `Fortsetzen?`
    );
    if (!confirm(confirmText)) return;
    const showToast = typeof window.showToast === 'function' ? window.showToast : ((m) => alert(m));
    showToast('🧠 Pattern-Train laeuft... (kann 30-60s dauern)', 'info');
    try {
        const r = await Auth.fetch(`/jobs/sources/${sourceId}/train-pattern`, {
            method: 'POST', body: JSON.stringify({}),
        });
        if (r && r.ok) {
            const pct = Math.round((r.hit_rate || 0) * 100);
            showToast(`✅ Pattern gelernt: ${pct}% Hit-Rate auf ${r.sample_count} Test-Mails`, 'success');
            refresh();
            if (typeof loadLearnedPatterns === 'function') loadLearnedPatterns();
        } else if (r && r.error) {
            const pct = r.hit_rate != null ? ` (${Math.round(r.hit_rate*100)}%)` : '';
            alert(`❌ Pattern-Train fehlgeschlagen${pct}:\n\n${r.error}`);
        }
    } catch (e) {
        alert(`❌ ${e && e.message ? e.message : 'Fehler beim Pattern-Train'}`);
    }
}
```

Im public-API-return-Block ergänzen: `trainPattern,`.

- [ ] **Step 3: service-worker.js v40**

```javascript
const CACHE_NAME = 'bewerbungs-tracker-v40';
```

- [ ] **Step 4: Smoke-Verifikation**

```bash
grep -n "trainPattern\|🧠 Lernen" index.html | head
grep "v40" service-worker.js
```

- [ ] **Step 5: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(jobs-ui): 🧠 Pattern-Lernen-Button pro Email-Source + Cache v40"
```

---

### Task 12: UI - Warn-Badge bei niedriger Hit-Rate

**Files:**
- Modify: `services/job_sources/email_jobs.py` (Hit-Rate-Tracking)
- Modify: `api/jobs_user.py` (`_source_id_for_tracking` setzen)
- Modify: `index.html` (Badge rendern)
- Modify: `service-worker.js` (v41)

- [ ] **Step 1: Adapter trackt Hit-Rate**

In `EmailJobsAdapter.fetch()` direkt vor `return jobs`:

```python
try:
    from models import db, JobSource
    src_id = getattr(self, '_source_id_for_tracking', None)
    if src_id and len(emails) >= 10:
        ratio = len(jobs) / max(len(emails), 1)
        if ratio < 0.20:
            JobSource.query.filter_by(id=src_id).update({
                'last_error': f'pattern_low_hit_rate: {len(jobs)}/{len(emails)} ({int(ratio*100)}%)'
            })
            db.session.commit()
        else:
            existing = JobSource.query.get(src_id)
            if existing and (existing.last_error or '').startswith('pattern_low_hit_rate'):
                JobSource.query.filter_by(id=src_id).update({'last_error': None})
                db.session.commit()
except Exception:
    logger.exception("Hit-Rate-Tracking schlug fehl (non-fatal)")
```

- [ ] **Step 2: Caller-Setup**

Im `import-from-email`-Endpoint (`api/jobs_user.py`), nach `adapter = get_adapter(...)`:

```python
adapter._source_id_for_tracking = src.id
```

- [ ] **Step 3: Frontend - Warn-Badge im Status-Rendering**

Im `refresh()` von `JdSourcesUI` den Status-Block ersetzen (suche `'⚠️ <span title='`-Block):

```javascript
const isPatternIssue = s.last_error && s.last_error.startsWith('pattern_low_hit_rate');
const status = s.enabled
    ? (isPatternIssue
        ? `⚠️ <span title="${escapeHtml(s.last_error)} - Klick 🧠 fuer Pattern-Train" style="color:var(--warning,#c97e00)">Pattern veraltet?</span>`
        : (s.last_error
            ? `⚠️ <span title="${escapeHtml(s.last_error)}">Fehler</span>`
            : '✅ Aktiv'))
    : '⏸️ Aus';
```

- [ ] **Step 4: service-worker.js v41**

- [ ] **Step 5: Smoke-Test**

```bash
/Library/WebServer/Documents/Bewerbungstracker/venv/bin/python -m pytest tests/services/test_email_jobs_adapter.py tests/api/test_indeed_email_import.py -q 2>&1 | tail -3
```

Expected: keine Regression.

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/email_jobs.py api/jobs_user.py index.html service-worker.js
git commit -m "feat(jobs-ui): Warn-Badge bei niedriger Pattern-Hit-Rate + Cache v41"
```

---

### Task 13: UI - Settings-Karte „Gelernte Pattern"

**Files:**
- Modify: `index.html` (neue Karte in `data-section="jobs"`)
- Modify: `service-worker.js` (v42)

- [ ] **Step 1: HTML-Karte**

Im Block `<div class="settings-section" data-section="jobs">` (nach der Job-Quellen-Karte) einfügen:

```html
<div class="card" style="margin-top:1rem">
  <div class="card-title" style="margin-bottom:0.75rem">🧠 Gelernte Pattern</div>
  <p style="color:var(--text-muted);font-size:0.9rem;margin-bottom:0.5rem">
    Pro Plattform wird ein Layout-Pattern global aktiv. Bei Layout-Drift
    der Mails: 🧠-Button in der Job-Quellen-Tabelle. Rollback wenn neues
    Pattern schlechter als Vorversion.
  </p>
  <table style="width:100%;font-size:0.9rem">
    <thead><tr style="border-bottom:1px solid var(--border)">
      <th style="text-align:left;padding:0.4rem">Plattform</th>
      <th style="text-align:left;padding:0.4rem">Hit-Rate</th>
      <th style="text-align:left;padding:0.4rem">Trainiert am</th>
      <th style="text-align:left;padding:0.4rem">Versionen</th>
      <th style="text-align:left;padding:0.4rem">Aktion</th>
    </tr></thead>
    <tbody id="jdLearnedPatternsTableBody">
      <tr><td colspan="5" style="padding:0.6rem;color:var(--text-muted)">Lade...</td></tr>
    </tbody>
  </table>
  <button class="btn btn-secondary btn-sm" style="margin-top:0.5rem"
          onclick="JdSourcesUI.loadLearnedPatterns()">🔄 Aktualisieren</button>
</div>
```

- [ ] **Step 2: JS-Funktionen**

In JdSourcesUI ergänzen:

```javascript
async function loadLearnedPatterns() {
    const tbody = document.getElementById('jdLearnedPatternsTableBody');
    if (!tbody) return;
    try {
        const r = await Auth.fetch('/jobs/learned-patterns', { method: 'GET' });
        const list = (r && r.patterns) || [];
        const PLATFORMS = ['indeed', 'linkedin', 'xing'];
        const rows = PLATFORMS.map(platform => {
            const entry = list.find(p => p.platform === platform);
            if (!entry) {
                return `<tr><td style="padding:0.4rem">${escapeHtml(platform.toUpperCase())}</td>
                    <td>—</td><td colspan="2" style="color:var(--text-muted)">(Hardcoded Default)</td><td>—</td></tr>`;
            }
            const pct = Math.round((entry.hit_rate || 0) * 100);
            const date = entry.trained_at ? new Date(entry.trained_at).toLocaleString('de-DE') : '—';
            const rollbackBtn = entry.history_count >= 1
                ? `<button class="btn btn-sm btn-secondary" onclick="JdSourcesUI.rollbackPattern('${escapeHtml(platform)}')" title="Zur Vorversion zurueck">↶ Rollback</button>`
                : '<span style="color:var(--text-muted)">—</span>';
            return `<tr style="border-bottom:1px solid var(--border)">
                <td style="padding:0.4rem">${escapeHtml(platform.toUpperCase())}</td>
                <td>${pct}%</td>
                <td>${escapeHtml(date)}</td>
                <td>${entry.history_count + 1}</td>
                <td>${rollbackBtn}</td>
            </tr>`;
        });
        tbody.innerHTML = rows.join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="padding:0.6rem;color:var(--danger)">Fehler: ${escapeHtml(e.message)}</td></tr>`;
    }
}


async function rollbackPattern(platform) {
    if (!confirm(`Pattern fuer ${platform.toUpperCase()} auf Vorversion zuruecksetzen?`)) return;
    try {
        const r = await Auth.fetch(`/jobs/learned-patterns/${platform}/rollback`, {
            method: 'POST', body: JSON.stringify({}),
        });
        if (r && r.ok) {
            const showToast = typeof window.showToast === 'function' ? window.showToast : ((m) => alert(m));
            showToast(`✅ Rollback erfolgreich fuer ${platform}`, 'success');
            loadLearnedPatterns();
        } else if (r && r.error) {
            alert(`❌ Rollback fehlgeschlagen: ${r.error}`);
        }
    } catch (e) {
        alert(`❌ ${e.message}`);
    }
}
```

Im public-API-return: `loadLearnedPatterns, rollbackPattern` ergänzen.

Beim Settings-View-Open-Hook (suche existing `JdSourcesUI.loadImapStatus()`-Aufruf) zusätzlich `loadLearnedPatterns()` aufrufen:
```javascript
if (typeof JdSourcesUI !== 'undefined' && JdSourcesUI.loadLearnedPatterns) {
    JdSourcesUI.loadLearnedPatterns();
}
```

- [ ] **Step 3: service-worker.js v42**

- [ ] **Step 4: Smoke**

```bash
grep -n "jdLearnedPatternsTableBody\|loadLearnedPatterns\|rollbackPattern" index.html | head
grep "v42" service-worker.js
```

- [ ] **Step 5: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(jobs-ui): Settings-Karte 'Gelernte Pattern' mit Rollback + Cache v42"
```

---

### Task 14: Deploy + Memory

**Files:**
- VPS: git pull + alembic upgrade + restart
- Memory: `project_email_jobs_import_live.md` Abschnitt „Pattern-Lerner"

- [ ] **Step 1: Push**

```bash
git push origin HEAD:master 2>&1 | tail -3
```

- [ ] **Step 2: VPS - DB-Backup + Pull + Migration**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && cp bewerbungstracker.db bewerbungstracker.db.bak.pre-pattern-learner-2026-05-19 && git pull origin master 2>&1 | tail -5 && venv/bin/alembic upgrade head 2>&1 | tail -3'
```

- [ ] **Step 3: Service-Restart**

```bash
ssh ionos-vps 'systemctl restart bewerbungen && sleep 2 && systemctl is-active bewerbungen'
```

- [ ] **Step 4: Production-Smoke**

```bash
curl -sk -o /dev/null -w "Frontend: %{http_code}\n" https://bewerbung.wolfinisoftware.de/
curl -sk -o /dev/null -w "Train (no auth): %{http_code}\n" -X POST https://bewerbung.wolfinisoftware.de/api/jobs/sources/17/train-pattern
curl -sk -o /dev/null -w "Learned (no auth): %{http_code}\n" https://bewerbung.wolfinisoftware.de/api/jobs/learned-patterns
```

Expected: 200, 401, 401.

- [ ] **Step 5: Memory-Update**

In `~/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/project_email_jobs_import_live.md` ans Ende anfügen:

```markdown
## Pattern-Lerner (seit 2026-05-19)

Neue Tabelle `learned_email_patterns` (global pro Plattform mit Versionierung).
Service `services/job_sources/pattern_learner.py` mit 4 Funktionen:
fetch_sample_mails, ai_learn_pattern (via ai-provider-service mit
JSON-Schema-Retry), compile_pattern, validate_pattern.

Endpoints:
- POST /api/jobs/sources/<id>/train-pattern - AI-Train, Rate-Limit 1/Plattform/h
- GET /api/jobs/learned-patterns - listet aktive Pattern + History
- POST /api/jobs/learned-patterns/<platform>/rollback

UI: 🧠-Button pro Email-Source, Warn-Badge bei <20% Trefferquote,
Settings-Karte mit Rollback. service-worker v42.

EmailJobsAdapter._parse_email lädt aktives Pattern aus DB (lazy + cached),
nutzt es statt der hardcoded Profile-Regexen wenn vorhanden.
```

- [ ] **Step 6: Manueller Live-Test**

Browser-Refresh, Settings → Bewerbungen & Jobs → Job-Quellen → bei LinkedIn 🧠 → bestätigen → 30-60s warten → Toast.
Settings-Karte „Gelernte Pattern" zeigt LinkedIn mit Hit-Rate.
📧 Import erneut: sollte jetzt mehr Jobs finden.

---

## Verifikation am Schluss

- [ ] Alle Tests grün: `pytest tests/ -q`
- [ ] VPS HEAD = origin/master
- [ ] Tabelle `learned_email_patterns` existiert auf VPS
- [ ] 🧠-Button im Source-Action-Block sichtbar
- [ ] Train auf LinkedIn-Source erfolgreich (Hit-Rate ≥40%)
- [ ] Settings-Karte zeigt LinkedIn mit Rollback-Option

## Out of Scope

- Pro-User-Override globaler Pattern
- Edit-Modus JSON manuell
- Diff-View zwischen Versionen
- HTML-Body-Parsing
- Automatischer Re-Train (nur UI-Hint)
- Multi-Language jenseits DE+EN
