# Per-Feature Model-Konfiguration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** User kann pro KI-Task (Match, Cover-Letter, Email-Analyse, CV-Summarize) ein eigenes Modell wählen mit heuristischer Empfehlung im Frontend.

**Architecture:**
- DB: Nullable JSON-Spalte `users.feature_model_overrides` + `User.get_model_for(feature)` Helper mit Fallback auf Standard
- Backend: 2 neue Profile-Endpoints + Service-Layer-Anpassungen in 4 Stellen
- Frontend: Bestehende Standard-UI bleibt + 4 expandable Override-Cards + heuristische Empfehlungs-Engine (inline in index.html)

**Tech Stack:** Flask + SQLAlchemy + Alembic (backend), vanilla JS (frontend)

**Related Spec:** [2026-05-11-per-feature-model-config-design.md](../specs/2026-05-11-per-feature-model-config-design.md)

---

## File Structure

**Backend:**
- Modify: `models.py` — Spalte + `get_model_for()` Helper auf User
- Create: `alembic/versions/a8c9d0e1f2g3_add_feature_model_overrides.py`
- Modify: `api/profile.py` — 2 neue Endpoints (GET/PATCH `/feature-models`)
- Modify: `api/cover_letters.py:generate_cover_letter` — auf `get_model_for('cover_letter')` umstellen
- Modify: `api/jobs_cron.py:_run_claude_match_for` — auf `get_model_for('match')` umstellen
- Modify: `api/jobs_cron.py:_run_match_via_service` — eigener Override für `cv_summarize` beim Summarize-Retry
- Modify: `claude_integration.py` (analyze_email path) — auf `get_model_for('email_analyse')` umstellen (falls aktiv)

**Tests:**
- Create: `tests/test_user_get_model_for.py`
- Create: `tests/api/test_feature_models.py`
- Modify: `tests/api/test_cover_letters.py`, `tests/api/test_jobs_cron.py` (neue Override-Tests)

**Frontend:**
- Modify: `index.html` — Empfehlungs-Engine + 4 Override-Cards + Modal
- Modify: `service-worker.js` — Cache v8 → v9

---

## Task 1: Alembic-Migration

**Files:**
- Create: `alembic/versions/a8c9d0e1f2g3_add_feature_model_overrides.py`

- [ ] **Step 1: Erstelle Migration-Datei**

Schreibe `alembic/versions/a8c9d0e1f2g3_add_feature_model_overrides.py`:

```python
"""add_feature_model_overrides

Revision ID: a8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-11 10:00:00.000000

Per-User JSON-Overrides für Pro-Task-Modell-Konfiguration.
Nullable — fehlend = Fallback auf user.ai_provider/ai_provider_model.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a8c9d0e1f2g3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('feature_model_overrides', sa.Text, nullable=True))


def downgrade():
    op.drop_column('users', 'feature_model_overrides')
```

- [ ] **Step 2: Migration auf lokaler DB ausführen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
DATABASE_URL=sqlite:///bewerbungstracker.db alembic upgrade head
```

Expected: `Running upgrade a7b8c9d0e1f2 -> a8c9d0e1f2g3, add_feature_model_overrides`

- [ ] **Step 3: Verifizieren dass Spalte existiert**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('instance/bewerbungstracker.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(users)').fetchall()]
print('feature_model_overrides drin?', 'feature_model_overrides' in cols)
v = c.execute('SELECT version_num FROM alembic_version').fetchone()
print('alembic_version:', v[0])
"
```

Expected: `feature_model_overrides drin? True` + `alembic_version: a8c9d0e1f2g3`

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/a8c9d0e1f2g3_add_feature_model_overrides.py
git commit -m "feat(db): Alembic-Migration für feature_model_overrides JSON-Spalte"
```

---

## Task 2: User.feature_model_overrides Spalte + get_model_for() Helper

**Files:**
- Modify: `models.py` (User-Klasse)
- Test: `tests/test_user_get_model_for.py`

- [ ] **Step 1: Spalte zur User-Klasse hinzufügen**

In `models.py`, in der User-Klasse, nach `ai_provider_config` (Zeile ~57), einfügen:

```python
    # Pro-Task-Modell-Overrides als JSON. Fehlt der Key → Fallback auf
    # ai_provider/ai_provider_model. Siehe get_model_for() unten.
    feature_model_overrides = db.Column(db.Text, nullable=True)
```

- [ ] **Step 2: get_model_for() Method zur User-Klasse hinzufügen**

In `models.py`, in der User-Klasse, nach der `job_region_filter`-Property (ca. Zeile ~92), einfügen:

```python
    def get_model_for(self, feature: str):
        """Returns (provider, model) für Feature mit Fallback auf Standard.

        Feature-Keys: 'match', 'cover_letter', 'email_analyse', 'cv_summarize'.
        Bei malformed JSON oder fehlendem Override → Fallback auf
        ai_provider / ai_provider_model.
        """
        try:
            overrides = _json.loads(self.feature_model_overrides or '{}')
        except (ValueError, TypeError):
            overrides = {}
        override = overrides.get(feature)
        if isinstance(override, dict) and override.get('provider'):
            return override['provider'], override.get('model')
        return self.ai_provider, self.ai_provider_model
```

Note: `_json` ist schon als alias importiert oben im File (`import json as _json`).

- [ ] **Step 3: Test-Datei erstellen**

Schreibe `tests/test_user_get_model_for.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für User.get_model_for() Helper."""
import json
import pytest
from models import User


def make_user(ai_provider='claude', ai_provider_model='claude-haiku-4-5-20251001',
              overrides=None):
    u = User(
        email='test@example.com',
        password_hash='x',
        ai_provider=ai_provider,
        ai_provider_model=ai_provider_model,
        feature_model_overrides=(json.dumps(overrides) if overrides is not None else None),
    )
    return u


def test_fallback_when_no_overrides():
    u = make_user()
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_fallback_when_overrides_empty():
    u = make_user(overrides={})
    assert u.get_model_for('cover_letter') == ('claude', 'claude-haiku-4-5-20251001')


def test_override_returned_when_present():
    u = make_user(overrides={
        'match': {'provider': 'ollama', 'model': 'mistral-nemo:12b'},
    })
    assert u.get_model_for('match') == ('ollama', 'mistral-nemo:12b')


def test_override_with_only_provider_returns_none_model():
    u = make_user(overrides={
        'cover_letter': {'provider': 'claude'},
    })
    assert u.get_model_for('cover_letter') == ('claude', None)


def test_override_null_falls_back():
    u = make_user(overrides={'match': None})
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_override_for_different_feature_does_not_affect_others():
    u = make_user(overrides={
        'cover_letter': {'provider': 'ollama', 'model': 'qwen2.5:32b'},
    })
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')
    assert u.get_model_for('cover_letter') == ('ollama', 'qwen2.5:32b')


def test_malformed_json_falls_back():
    u = User(
        email='t@t.de', password_hash='x',
        ai_provider='claude', ai_provider_model='claude-haiku-4-5-20251001',
        feature_model_overrides='{this is: not json',
    )
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_unknown_feature_falls_back():
    u = make_user(overrides={'match': {'provider': 'ollama', 'model': 'm'}})
    assert u.get_model_for('unknown_feature') == ('claude', 'claude-haiku-4-5-20251001')


def test_empty_provider_in_override_falls_back():
    u = make_user(overrides={'match': {'provider': '', 'model': 'foo'}})
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')
```

- [ ] **Step 4: Tests laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/test_user_get_model_for.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_user_get_model_for.py
git commit -m "feat(models): User.feature_model_overrides + get_model_for() Helper

- Neue Text-Spalte für JSON-Overrides pro Task
- Helper liefert (provider, model) mit Fallback auf ai_provider/ai_provider_model
- Robust gegen malformed JSON, leere strings, unbekannte feature-keys"
```

---

## Task 3: API Endpoints GET/PATCH /feature-models

**Files:**
- Modify: `api/profile.py`
- Test: `tests/api/test_feature_models.py`

- [ ] **Step 1: Lese existing profile.py Pattern**

```bash
head -60 /Library/WebServer/Documents/Bewerbungstracker/api/profile.py
```

Verstehe Bestehende Patterns (Blueprint-Name, decorator, error-handling).

- [ ] **Step 2: Endpoints zu api/profile.py hinzufügen**

Am Ende von `api/profile.py` einfügen:

```python
# ─── Pro-Task-Modell-Overrides ───────────────────────────────────────────────
import json as _profile_json

VALID_FEATURES = {'match', 'cover_letter', 'email_analyse', 'cv_summarize'}
VALID_PROVIDERS = {'claude', 'ollama', 'openai', 'mammouth', 'custom'}


@profile_bp.get('/feature-models')
@token_required
def get_feature_models(user):
    """Liefert Standard-Modell + aktuelle Pro-Task-Overrides."""
    try:
        overrides = _profile_json.loads(user.feature_model_overrides or '{}')
    except (ValueError, TypeError):
        overrides = {}
    return jsonify({
        'standard': {
            'provider': user.ai_provider,
            'model': user.ai_provider_model,
        },
        'overrides': overrides,
    }), 200


@profile_bp.patch('/feature-models')
@token_required
def update_feature_models(user):
    """Update Pro-Task-Overrides. Body: {overrides: {feature: {provider, model} | null}}."""
    data = request.get_json() or {}
    overrides = data.get('overrides')

    if not isinstance(overrides, dict):
        return jsonify({'error': 'overrides muss ein Object sein'}), 400

    for feat, cfg in overrides.items():
        if feat not in VALID_FEATURES:
            return jsonify({'error': f'Unbekanntes Feature: {feat}'}), 400
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            return jsonify({'error': f'{feat}: muss Object oder null sein'}), 400
        provider = cfg.get('provider')
        if provider and provider not in VALID_PROVIDERS:
            return jsonify({'error': f'{feat}: unbekannter Provider {provider}'}), 400

    # Normalisierung: null-Werte rausfiltern, leere Provider-Strings rausfiltern
    clean = {}
    for feat, cfg in overrides.items():
        if cfg is None or not isinstance(cfg, dict):
            continue
        if not cfg.get('provider'):
            continue
        clean[feat] = {
            'provider': cfg['provider'],
            'model': cfg.get('model') or None,
        }

    user.feature_model_overrides = _profile_json.dumps(clean, ensure_ascii=False) if clean else None
    db.session.commit()
    return jsonify({'status': 'updated', 'overrides': clean}), 200
```

Verifiziere dass `request`, `jsonify`, `db`, `token_required` schon importiert sind. Falls nicht, in die Imports am Anfang der Datei mit aufnehmen.

- [ ] **Step 3: Test-Datei erstellen**

Schreibe `tests/api/test_feature_models.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für /api/profile/feature-models Endpoints."""
import json
import pytest


def test_get_without_auth_returns_401(client):
    r = client.get('/api/profile/feature-models')
    assert r.status_code == 401


def test_get_returns_standard_and_empty_overrides(client, auth_header):
    headers, user = auth_header
    r = client.get('/api/profile/feature-models', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert 'standard' in body
    assert body['standard']['provider'] == user.ai_provider
    assert body['standard']['model'] == user.ai_provider_model
    assert body['overrides'] == {}


def test_patch_sets_override(client, auth_header):
    headers, user = auth_header
    payload = {'overrides': {
        'cover_letter': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    }}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'updated'
    assert body['overrides']['cover_letter']['provider'] == 'claude'

    # GET zurück gibt den gespeicherten Override
    r2 = client.get('/api/profile/feature-models', headers=headers)
    assert r2.get_json()['overrides']['cover_letter']['model'] == 'claude-haiku-4-5-20251001'


def test_patch_with_null_removes_override(client, auth_header, db_session):
    from models import User
    headers, user = auth_header
    user.feature_model_overrides = json.dumps({
        'match': {'provider': 'ollama', 'model': 'mistral-nemo:12b'},
    })
    db_session.commit()

    payload = {'overrides': {'match': None}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['overrides'] == {}


def test_patch_unknown_feature_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'unknown_feature': {'provider': 'claude'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400
    assert 'Unbekanntes Feature' in r.get_json()['error']


def test_patch_unknown_provider_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'match': {'provider': 'gpt-5-fake'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400
    assert 'unbekannter Provider' in r.get_json()['error']


def test_patch_non_dict_override_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'match': 'not-a-dict'}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400


def test_patch_overrides_not_dict_returns_400(client, auth_header):
    headers, _ = auth_header
    r = client.patch('/api/profile/feature-models', json={'overrides': 'foo'}, headers=headers)
    assert r.status_code == 400


def test_patch_empty_provider_string_does_not_save(client, auth_header):
    """Leerer Provider-String wird als 'nicht setzen' interpretiert."""
    headers, _ = auth_header
    payload = {'overrides': {'match': {'provider': '', 'model': 'foo'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['overrides'] == {}


def test_user_isolation(client, auth_header, user_factory, db_session):
    """User A sieht nicht die Overrides von User B."""
    headers_a, _ = auth_header
    user_b = user_factory()
    user_b.feature_model_overrides = json.dumps({
        'match': {'provider': 'ollama', 'model': 'should-not-leak'},
    })
    db_session.commit()

    r = client.get('/api/profile/feature-models', headers=headers_a)
    overrides = r.get_json()['overrides']
    assert 'match' not in overrides or overrides['match'].get('model') != 'should-not-leak'
```

- [ ] **Step 4: Tests laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/api/test_feature_models.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add api/profile.py tests/api/test_feature_models.py
git commit -m "feat(api): GET/PATCH /api/profile/feature-models Endpoints

- GET: liefert Standard + aktuelle Overrides
- PATCH: validiert feature-keys (whitelist) + provider (whitelist)
- null/empty provider entfernt Override
- User-Isolation via @token_required"
```

---

## Task 4: Service-Layer auf get_model_for umstellen — Cover-Letter

**Files:**
- Modify: `api/cover_letters.py:generate_cover_letter`

- [ ] **Step 1: Aktueller Code lesen**

```bash
grep -n "user.ai_provider\|provider = " /Library/WebServer/Documents/Bewerbungstracker/api/cover_letters.py
```

- [ ] **Step 2: Ersetze die provider/model-Auflösung**

In `api/cover_letters.py`, in `generate_cover_letter`, ersetze den Block:

```python
    # User-Provider/Modell respektieren (sonst hardcoded auf claude).
    # Cover-Letter braucht ein starkes Modell — Default-Fallback auf Claude
    # falls User Ollama/Mistral o.ä. nutzt und Body ohne Override kommt.
    provider = (data.get('provider') or user.ai_provider or 'claude').strip()
    model = (data.get('model') or user.ai_provider_model or '').strip() or None
```

durch:

```python
    # Pro-Task-Override (cover_letter) → fallback Standard → fallback claude.
    # Body kann beides per Request overriden (explizite User-Wahl in UI).
    feat_provider, feat_model = user.get_model_for('cover_letter')
    provider = (data.get('provider') or feat_provider or 'claude').strip()
    model = (data.get('model') or feat_model or '').strip() or None
```

- [ ] **Step 3: Test schreiben dass Override greift**

In `tests/api/test_cover_letters.py` (existing), neuer Test am Ende anhängen:

```python
def test_generate_uses_cover_letter_override(client, auth_header, db_session):
    """Wenn User feature_model_overrides für cover_letter gesetzt hat,
    wird der Override genutzt statt user.ai_provider."""
    import json as _j
    from unittest.mock import patch, MagicMock
    from models import CoverLetter

    headers, user = auth_header
    user.ai_provider = 'ollama'
    user.ai_provider_model = 'mistral-nemo:12b'
    user.feature_model_overrides = _j.dumps({
        'cover_letter': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    })
    db_session.commit()

    cl = CoverLetter(
        user_id=user.id,
        job_title='Engineer', company_name='X',
        job_description='Wir suchen einen erfahrenen Senior Engineer mit Python und Cloud Skills, langfristig.',
        tone='professional', length='medium', focus='balanced',
        status='draft',
    )
    db_session.add(cl); db_session.commit()

    fake_analysis = {'matched_skills': [], 'matched_experience': [],
                     'interpreted_requirements': [], 'missing_or_weak': []}
    fake_content = '<!-- confidence: 0.9 -->\n<p>Test</p>'

    with patch('api.cover_letters.CoverLetterService') as MockSvc:
        instance = MockSvc.return_value
        instance.analyze.return_value = fake_analysis
        instance.generate.return_value = fake_content

        r = client.post(f'/api/cover-letters/{cl.id}/generate',
                        json={'cv_text': 'Python Dev 5y'}, headers=headers)
        assert r.status_code == 200

        # analyze + generate wurden mit provider='claude' (Override) gerufen,
        # nicht mit 'ollama' (Standard)
        call_kwargs = instance.analyze.call_args.kwargs
        assert call_kwargs.get('provider') == 'claude'
        assert call_kwargs.get('model') == 'claude-haiku-4-5-20251001'

        gen_kwargs = instance.generate.call_args.kwargs
        assert gen_kwargs.get('provider') == 'claude'
        assert gen_kwargs.get('model') == 'claude-haiku-4-5-20251001'
```

- [ ] **Step 4: Bestehende Tests + neuer Test laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/api/test_cover_letters.py -v
```

Expected: alle Tests passen (38 alte + 1 neuer = 39 passed).

- [ ] **Step 5: Commit**

```bash
git add api/cover_letters.py tests/api/test_cover_letters.py
git commit -m "feat(cover-letter): nutzt user.get_model_for('cover_letter')

Statt user.ai_provider direkt zu lesen, wird der Pro-Task-Override
respektiert. Body kann beides per Request weiter overriden."
```

---

## Task 5: Service-Layer auf get_model_for umstellen — Job-Match

**Files:**
- Modify: `api/jobs_cron.py:_run_claude_match_for`
- Test: bestehende `tests/api/test_jobs_user.py`, `tests/api/test_jobs_cron.py` müssen grün bleiben

- [ ] **Step 1: Aktueller Code lesen**

```bash
grep -n "provider = user.ai_provider\|model = user.ai_provider_model" /Library/WebServer/Documents/Bewerbungstracker/api/jobs_cron.py
```

- [ ] **Step 2: Ersetze die Auflösung im Helper**

In `api/jobs_cron.py`, in `_run_claude_match_for`, finde:

```python
    cv_summary = _build_cv_summary(user.cv_data_json)
    provider = user.ai_provider or ProviderConfig.CLAUDE
    model = user.ai_provider_model or DEFAULT_MODEL
```

und ersetze durch:

```python
    cv_summary = _build_cv_summary(user.cv_data_json)
    # Pro-Task-Override für 'match' (fallback auf user.ai_provider/_model)
    feat_provider, feat_model = user.get_model_for('match')
    provider = feat_provider or ProviderConfig.CLAUDE
    model = feat_model or DEFAULT_MODEL
```

- [ ] **Step 3: Match-Override-Test schreiben**

In `tests/api/test_jobs_cron.py` (existing), am Ende anhängen:

```python
def test_match_uses_feature_override(app, user_factory, db_session):
    """Wenn User feature_model_overrides für match gesetzt hat,
    wird der Override genutzt."""
    import json as _j
    from unittest.mock import patch, MagicMock
    from api.jobs_cron import _run_claude_match_for
    from models import JobSource, RawJob, JobMatch

    user = user_factory(cv_data_json='{"cv": {"summary": "Dev"}}')
    user.ai_provider = 'ollama'
    user.ai_provider_model = 'mistral-nemo:12b'
    user.feature_model_overrides = _j.dumps({
        'match': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    })
    user.job_daily_budget_cents = 1000
    db_session.commit()

    src = JobSource(name='x', type='rss', config={'url': 'x'})
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='a', title='Dev',
                 url='https://j/1', description='Wir suchen Python', crawl_status='raw')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db_session.add(m); db_session.commit()

    fake_result = MagicMock(score=80, reasoning='ok', missing_skills=[],
                            tokens_in=10, tokens_out=10)
    captured = {}
    def fake_get_client(provider, *args, **kwargs):
        captured['provider'] = provider
        return MagicMock()

    with patch('api.jobs_cron.ProviderFactory.get_client', side_effect=fake_get_client), \
         patch('api.jobs_cron.match_job_with_claude', return_value=fake_result):
        _run_claude_match_for(None, user, m)

    # ProviderFactory.get_client wurde mit 'claude' aufgerufen (Override), nicht 'ollama'
    assert captured.get('provider') == 'claude'
```

- [ ] **Step 4: Bestehende Tests + neuer laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/api/test_jobs_cron.py tests/api/test_jobs_user.py -v
```

Expected: alle Tests passen.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat(jobs): match nutzt user.get_model_for('match')

Override-Logik im _run_claude_match_for Helper. Bestehender Default-Path
(kein Override) bleibt unverändert."
```

---

## Task 6: Service-Layer auf get_model_for umstellen — CV-Summarize

**Files:**
- Modify: `api/jobs_cron.py:_run_match_via_service`

- [ ] **Step 1: Aktueller Code lesen**

```bash
grep -n "_summarize_description(" /Library/WebServer/Documents/Bewerbungstracker/api/jobs_cron.py
```

- [ ] **Step 2: Eigenen Override für cv_summarize hinzufügen**

In `api/jobs_cron.py`, in `_run_match_via_service`, finde den Aufruf:

```python
            short_desc = _summarize_description(
                client, user.id, provider, model, raw.description or ''
            )
```

Ersetze durch:

```python
            # CV-Summarize hat eigenen Pro-Task-Override (sonst: match-Modell)
            sum_provider, sum_model = user.get_model_for('cv_summarize')
            short_desc = _summarize_description(
                client, user.id,
                sum_provider or provider,
                sum_model or model,
                raw.description or ''
            )
```

- [ ] **Step 3: Test schreiben**

In `tests/api/test_jobs_cron.py` (existing), am Ende anhängen:

```python
def test_summarize_uses_cv_summarize_override(app, user_factory, db_session):
    """Wenn User feature_model_overrides für cv_summarize gesetzt hat,
    wird der Override genutzt für die Description-Zusammenfassung."""
    import json as _j
    from unittest.mock import patch, MagicMock
    from api.jobs_cron import _run_match_via_service
    from models import JobSource, RawJob, JobMatch

    user = user_factory(cv_data_json='{"cv": {"summary": "Dev"}}')
    user.ai_provider = 'claude'
    user.ai_provider_model = 'claude-haiku-4-5-20251001'
    user.feature_model_overrides = _j.dumps({
        'cv_summarize': {'provider': 'ollama', 'model': 'mistral-nemo:12b'},
    })
    db_session.commit()

    src = JobSource(name='x', type='rss', config={'url': 'x'})
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='a', title='Dev',
                 url='https://j/1', description='X' * 10000, crawl_status='raw')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db_session.add(m); db_session.commit()

    bad_response = MagicMock(
        content=[MagicMock(text='nicht parsbar')],
        usage=MagicMock(input_tokens=10, output_tokens=10),
        via='claude', fallback_used=False,
    )

    summarize_calls = []
    def fake_summarize(client, user_id, prov, mdl, desc):
        summarize_calls.append((prov, mdl))
        return 'kurzversion'

    fake_client = MagicMock()
    fake_client.chat.return_value = bad_response

    with patch('api.jobs_cron.ai_provider_client.get_client', return_value=fake_client), \
         patch('api.jobs_cron._summarize_description', side_effect=fake_summarize), \
         patch('api.jobs_cron._extract_first_json_object', return_value=None):
        _run_match_via_service(user, m, raw, 'cv_summary', 'claude', 'claude-haiku-4-5-20251001')

    # _summarize_description wurde mit dem cv_summarize-Override aufgerufen (ollama)
    assert len(summarize_calls) == 1
    assert summarize_calls[0][0] == 'ollama'
    assert summarize_calls[0][1] == 'mistral-nemo:12b'
```

- [ ] **Step 4: Tests laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/api/test_jobs_cron.py -v
```

Expected: alle Tests passen.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "feat(jobs): cv_summarize nutzt user.get_model_for('cv_summarize')

Eigener Override für Description-Zusammenfassung. Fallback ist das
match-Modell (was wiederum Standard sein kann)."
```

---

## Task 7: Service-Layer auf get_model_for umstellen — Email-Analyse

**Files:**
- Modify: `claude_integration.py` (falls aktiv)

- [ ] **Step 1: analyze_email Funktion finden**

```bash
grep -n "def analyze_email\|ai_provider\|user.ai_provider" /Library/WebServer/Documents/Bewerbungstracker/claude_integration.py | head -10
```

- [ ] **Step 2: Falls vorhanden, provider/model umstellen**

Falls die Funktion `user.ai_provider`/`user.ai_provider_model` liest, ersetze diese Zeilen durch:

```python
    # Pro-Task-Override für 'email_analyse' (fallback auf Standard)
    feat_provider, feat_model = user.get_model_for('email_analyse')
    provider = feat_provider or 'claude'
    model = feat_model or DEFAULT_MODEL
```

Falls die Funktion **nicht** existiert oder andere Struktur hat: Diesen Task **überspringen** und dokumentieren.

- [ ] **Step 3: Falls Änderung gemacht, committen**

```bash
git add claude_integration.py
git commit -m "feat(email): analyze_email nutzt user.get_model_for('email_analyse')

Konsistent mit den anderen KI-Tasks."
```

Falls keine Änderung möglich:

```bash
git commit --allow-empty -m "chore(email): analyze_email Pfad nicht aktiv, Override-Verdrahtung verschoben

Spec sagt: email_analyse ist aktuell inaktiv. Wenn der Pfad reaktiviert
wird, muss er user.get_model_for('email_analyse') nutzen."
```

---

## Task 8: Empfehlungs-Engine in index.html

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Stelle für JS-Einfügung finden**

```bash
grep -n "function onProviderChange" /Library/WebServer/Documents/Bewerbungstracker/index.html
```

- [ ] **Step 2: Empfehlungs-Engine JS einfügen**

Direkt VOR `function onProviderChange` einfügen:

```javascript
// ═══════════════════════════════════════════════════════════════════
// PRO-TASK MODEL EMPFEHLUNGS-ENGINE (heuristisch)
// ═══════════════════════════════════════════════════════════════════

const FEATURE_LABELS = {
    match: 'Job-Matching',
    cover_letter: 'Cover-Letter',
    cv_summarize: 'CV-Summarize',
    email_analyse: 'Email-Analyse',
};

const TASK_THRESHOLDS = {
    match:         { ok: 60, warn: 40 },
    cover_letter:  { ok: 75, warn: 55 },
    cv_summarize:  { ok: 65, warn: 45 },
    email_analyse: { ok: 50, warn: 30 },
};

function capabilityScore(provider, model) {
    if (!model) return 50;
    const m = String(model).toLowerCase();

    // Cloud-Modelle: Whitelist
    const CLOUD = [
        ['claude-opus', 98],
        ['claude-sonnet-4', 92],
        ['claude-sonnet-3.5', 88],
        ['claude-haiku-4-5', 82],
        ['claude-haiku-3', 65],
        ['gpt-4o', 92],
        ['gpt-4-turbo', 90],
        ['gpt-4', 88],
        ['gpt-3.5', 60],
        ['o1', 95],
        ['o3', 96],
        ['gemini-1.5-pro', 90],
        ['gemini-1.5-flash', 70],
    ];
    for (const [pattern, score] of CLOUD) {
        if (m.includes(pattern)) return score;
    }

    // Open-Source: Parameter-Count
    const paramMatch = m.match(/(\d+)b\b/);
    const params = paramMatch ? parseInt(paramMatch[1], 10) : null;

    let score = 50;
    if (params) {
        if (params >= 400)     score = 95;
        else if (params >= 70) score = 88;
        else if (params >= 30) score = 78;
        else if (params >= 13) score = 65;
        else if (params >= 7)  score = 50;
        else                   score = 30;
    }

    // Familie-Modifier
    if (m.includes('qwen2.5') || m.includes('qwen3')) score += 5;
    if (m.includes('llama3.1') || m.includes('llama3.2') || m.includes('llama3.3')) score += 3;
    if (m.includes('deepseek')) score += 5;
    if (m.includes('phi-3') || m.includes('phi3')) score -= 5;

    return Math.min(100, Math.max(0, score));
}

function modelRecommendation(provider, model, feature) {
    let score = capabilityScore(provider, model);
    const isReasoning = /(thinking|\br1\b|\bo1\b|\bo3\b)/i.test(model || '');
    if (isReasoning && (feature === 'cover_letter' || feature === 'match')) score += 8;

    const t = TASK_THRESHOLDS[feature];
    if (!t) return { level: 'unknown', icon: '❔', text: 'Unbekannte Task' };
    if (score >= t.ok)   return { level: 'ok',   icon: '✅', text: 'Empfohlen' };
    if (score >= t.warn) return { level: 'warn', icon: '⚠️', text: 'Geht, aber suboptimal' };
    return                       { level: 'bad',  icon: '❌', text: 'Wird vermutlich scheitern' };
}
```

- [ ] **Step 3: Browser-Test (manuell)**

Nach Reload, in DevTools Console:

```javascript
capabilityScore('claude', 'claude-haiku-4-5-20251001')  // expected: 82
capabilityScore('ollama', 'mistral-nemo:12b-instruct-2407')  // expected: 65
modelRecommendation('claude', 'claude-haiku-4-5-20251001', 'cover_letter')
// expected: {level: 'ok', icon: '✅', text: 'Empfohlen'}
modelRecommendation('ollama', 'mistral-nemo:12b', 'cover_letter')
// expected: {level: 'warn', icon: '⚠️', text: 'Geht, aber suboptimal'}
modelRecommendation('ollama', 'llama3.2:3b', 'cover_letter')
// expected: {level: 'bad', icon: '❌', text: 'Wird vermutlich scheitern'}
```

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(frontend): Heuristische Empfehlungs-Engine für KI-Modelle

- capabilityScore(provider, model) → 0-100 basierend auf Cloud-Whitelist
  + Param-Count (Ollama/Open-Source) + Familie-Modifier
- modelRecommendation(provider, model, feature) → {level, icon, text}
- Schwellen pro Task: match (60/40), cover_letter (75/55),
  cv_summarize (65/45), email_analyse (50/30)
- Reasoning-Modelle (o1, o3, r1, thinking) bekommen +8 für JSON-Tasks"
```

---

## Task 9: Override-Cards UI im Settings

**Files:**
- Modify: `index.html` — neue HTML-Sektion + JS-Handler

- [ ] **Step 1: Aktuelle Settings-Provider-Block-Position finden**

```bash
grep -n "id=\"aiModelSelect\"\|saveAIProvider" /Library/WebServer/Documents/Bewerbungstracker/index.html | head -5
```

Finde das schließende `</div>` des Provider-Blocks (nach `aiModelSelect` und dem Save-Button).

- [ ] **Step 2: HTML-Block einfügen**

Direkt nach dem schließenden `</div>` des `🤖 KI Provider` Blocks folgende HTML einfügen:

```html
<!-- ═══ PRO-TASK MODELL-OVERRIDES ═══ -->
<div class="card" style="padding:1rem;margin-top:1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
        <div style="font-weight:600;">🎯 Pro-Task-Modelle (optional)</div>
        <button class="btn btn-secondary btn-sm" onclick="openModelComparisonModal()">📊 Modelle vergleichen</button>
    </div>
    <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.75rem;">
        Wenn du verschiedene Modelle für verschiedene Tasks nutzen willst — z.B. ein
        kleines lokales Modell für Job-Matching aber Claude für Cover-Letter.
        Wenn nicht aktiv, wird das Standard-Modell oben genutzt.
    </div>
    <div id="featureOverrideCards"></div>
</div>

<!-- Modal: Empfehlungs-Tabelle -->
<div id="modelComparisonModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;">
    <div style="background:var(--bg-card);padding:1.5rem;border-radius:8px;max-width:800px;width:90%;max-height:80vh;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <h3 style="margin:0;">📊 Modell-Vergleich</h3>
            <button class="btn btn-secondary btn-sm" onclick="closeModelComparisonModal()">✕</button>
        </div>
        <div id="modelComparisonContent"></div>
    </div>
</div>
```

- [ ] **Step 3: JS-Handler einfügen**

Nach den Empfehlungs-Engine-Funktionen aus Task 8, folgende Funktionen einfügen.

**WICHTIG:** Alle dynamisch eingefügten Strings im HTML MÜSSEN durch `escapeHtml()` laufen (die Funktion existiert schon im Codebase). User-Modell-Namen kommen vom Provider-Service und sind nicht direkt user-kontrolliert, aber wir bleiben sicher.

```javascript
// ═══════════════════════════════════════════════════════════════════
// FEATURE-OVERRIDES UI
// ═══════════════════════════════════════════════════════════════════

let _featureOverridesState = {};
let _standardModelState = { provider: '', model: '' };

async function loadFeatureOverrides() {
    try {
        const r = await fetchAPI('/api/profile/feature-models');
        if (!r.ok) {
            console.error('feature-models load failed:', r.status);
            return;
        }
        const data = await r.json();
        _featureOverridesState = data.overrides || {};
        _standardModelState = data.standard || { provider: '', model: '' };
        renderFeatureOverrideCards();
    } catch (e) {
        console.error('feature-models error:', e);
    }
}

function renderFeatureOverrideCards() {
    const container = document.getElementById('featureOverrideCards');
    if (!container) return;
    const features = ['match', 'cover_letter', 'email_analyse', 'cv_summarize'];
    // Render via DOM API (kein innerHTML mit user-data)
    container.replaceChildren();
    for (const f of features) {
        container.appendChild(buildOverrideCard(f));
    }
}

function buildOverrideCard(feature) {
    const label = FEATURE_LABELS[feature] || feature;
    const override = _featureOverridesState[feature];
    const isActive = !!(override && override.provider);
    const activeProv = isActive ? override.provider : _standardModelState.provider;
    const activeModel = isActive ? override.model : _standardModelState.model;
    const rec = modelRecommendation(activeProv, activeModel, feature);

    const details = document.createElement('details');
    details.style.cssText = 'border:1px solid var(--border);border-radius:6px;margin-bottom:0.5rem;padding:0.5rem;';

    const summary = document.createElement('summary');
    summary.style.cssText = 'cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:500;';

    const labelSpan = document.createElement('span');
    labelSpan.textContent = label;
    summary.appendChild(labelSpan);

    const statusSpan = document.createElement('span');
    statusSpan.textContent = rec.icon + ' ' + (isActive ? 'Override aktiv' : 'Standard') + ' (' + rec.text + ')';
    summary.appendChild(statusSpan);
    details.appendChild(summary);

    const body = document.createElement('div');
    body.style.cssText = 'margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid var(--border);';

    const checkboxLabel = document.createElement('label');
    checkboxLabel.style.cssText = 'display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = 'override-active-' + feature;
    checkbox.checked = isActive;
    checkbox.onchange = () => toggleOverride(feature, checkbox.checked);
    const checkboxText = document.createElement('span');
    checkboxText.textContent = 'Eigenes Modell für diese Task nutzen';
    checkboxLabel.appendChild(checkbox);
    checkboxLabel.appendChild(checkboxText);
    body.appendChild(checkboxLabel);

    const fields = document.createElement('div');
    fields.id = 'override-fields-' + feature;
    fields.style.display = isActive ? 'block' : 'none';

    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:0.5rem;';

    const provSelect = document.createElement('select');
    provSelect.id = 'override-provider-' + feature;
    provSelect.style.cssText = 'padding:0.4rem;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text);';
    provSelect.onchange = () => onOverrideProviderChange(feature);
    grid.appendChild(provSelect);

    const modelSelect = document.createElement('select');
    modelSelect.id = 'override-model-' + feature;
    modelSelect.style.cssText = 'padding:0.4rem;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text);';
    modelSelect.onchange = () => onOverrideModelChange(feature);
    grid.appendChild(modelSelect);

    fields.appendChild(grid);

    const recDiv = document.createElement('div');
    recDiv.id = 'override-recommendations-' + feature;
    recDiv.style.cssText = 'font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;';
    fields.appendChild(recDiv);

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-primary btn-sm';
    saveBtn.textContent = '💾 Speichern';
    saveBtn.onclick = () => saveOverride(feature);
    fields.appendChild(saveBtn);

    body.appendChild(fields);
    details.appendChild(body);

    return details;
}

async function toggleOverride(feature, checked) {
    const fields = document.getElementById('override-fields-' + feature);
    fields.style.display = checked ? 'block' : 'none';
    if (checked) {
        await populateOverrideProviders(feature);
    } else {
        delete _featureOverridesState[feature];
        await persistOverrides();
        renderFeatureOverrideCards();
    }
}

async function populateOverrideProviders(feature) {
    const select = document.getElementById('override-provider-' + feature);
    if (!select) return;
    try {
        const r = await fetchAPI('/api/providers');
        if (!r.ok) return;
        const data = await r.json();
        const providers = (data.providers || []).filter(p => p.configured);
        select.replaceChildren();
        for (const p of providers) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name || p.id;
            select.appendChild(opt);
        }
        const current = _featureOverridesState[feature];
        if (current && current.provider) select.value = current.provider;
        await onOverrideProviderChange(feature);
    } catch (e) {
        console.error('providers load:', e);
    }
}

async function onOverrideProviderChange(feature) {
    const provSel = document.getElementById('override-provider-' + feature);
    const modelSel = document.getElementById('override-model-' + feature);
    if (!provSel || !modelSel) return;
    const provider = provSel.value;
    try {
        const r = await fetchAPI('/api/providers/' + provider + '/models');
        modelSel.replaceChildren();
        if (!r.ok) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = '⚠️ Models nicht verfügbar';
            modelSel.appendChild(opt);
            return;
        }
        const data = await r.json();
        for (const m of (data.models || [])) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            modelSel.appendChild(opt);
        }
        const current = _featureOverridesState[feature];
        if (current && current.model) modelSel.value = current.model;
        else modelSel.value = data.default || (data.models[0] || '');
        onOverrideModelChange(feature);
    } catch (e) {
        console.error('models load:', e);
    }
}

function onOverrideModelChange(feature) {
    const provSel = document.getElementById('override-provider-' + feature);
    const modelSel = document.getElementById('override-model-' + feature);
    const recDiv = document.getElementById('override-recommendations-' + feature);
    if (!provSel || !modelSel || !recDiv) return;
    const provider = provSel.value;
    const model = modelSel.value;
    recDiv.replaceChildren();
    const features = ['match', 'cover_letter', 'cv_summarize', 'email_analyse'];
    for (const f of features) {
        const rec = modelRecommendation(provider, model, f);
        const isActive = (f === feature);
        const line = document.createElement('div');
        if (isActive) line.style.fontWeight = '600';
        line.textContent = FEATURE_LABELS[f] + ': ' + rec.icon + ' ' + rec.text + (isActive ? ' ← aktiv' : '');
        recDiv.appendChild(line);
    }
}

async function saveOverride(feature) {
    const provSel = document.getElementById('override-provider-' + feature);
    const modelSel = document.getElementById('override-model-' + feature);
    if (!provSel || !modelSel) return;
    _featureOverridesState[feature] = {
        provider: provSel.value,
        model: modelSel.value || null,
    };
    const ok = await persistOverrides();
    if (ok) {
        renderFeatureOverrideCards();
    }
}

async function persistOverrides() {
    try {
        const r = await fetchAPI('/api/profile/feature-models', {
            method: 'PATCH',
            body: JSON.stringify({ overrides: _featureOverridesState }),
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert('Speichern fehlgeschlagen: ' + (err.error || r.status));
            return false;
        }
        const data = await r.json();
        _featureOverridesState = data.overrides || {};
        return true;
    } catch (e) {
        console.error('persistOverrides:', e);
        alert('Fehler: ' + e.message);
        return false;
    }
}

async function openModelComparisonModal() {
    const modal = document.getElementById('modelComparisonModal');
    const content = document.getElementById('modelComparisonContent');
    modal.style.display = 'flex';
    content.replaceChildren();
    const loading = document.createElement('em');
    loading.textContent = 'Lade Modelle...';
    content.appendChild(loading);

    try {
        const provRes = await fetchAPI('/api/providers');
        if (!provRes.ok) throw new Error('providers load failed');
        const provData = await provRes.json();
        const providers = (provData.providers || []).filter(p => p.configured);

        const rows = [];
        for (const p of providers) {
            try {
                const mr = await fetchAPI('/api/providers/' + p.id + '/models');
                if (!mr.ok) continue;
                const mdata = await mr.json();
                for (const m of (mdata.models || [])) {
                    rows.push({ provider: p.id, providerName: p.name || p.id, model: m });
                }
            } catch (e) { /* skip */ }
        }

        content.replaceChildren();
        if (rows.length === 0) {
            const em = document.createElement('em');
            em.textContent = 'Keine Modelle gefunden.';
            content.appendChild(em);
            return;
        }

        const features = ['match', 'cover_letter', 'cv_summarize', 'email_analyse'];
        const table = document.createElement('table');
        table.style.cssText = 'width:100%;border-collapse:collapse;';

        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.style.background = 'var(--bg-card2)';
        const thModel = document.createElement('th');
        thModel.style.cssText = 'padding:0.5rem;text-align:left;';
        thModel.textContent = 'Modell';
        headerRow.appendChild(thModel);
        for (const f of features) {
            const th = document.createElement('th');
            th.style.cssText = 'padding:0.5rem;text-align:center;';
            th.textContent = FEATURE_LABELS[f];
            headerRow.appendChild(th);
        }
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        for (const r of rows) {
            const tr = document.createElement('tr');
            tr.style.borderTop = '1px solid var(--border)';
            const tdModel = document.createElement('td');
            tdModel.style.cssText = 'padding:0.4rem;font-size:0.85rem;';
            const muted = document.createElement('span');
            muted.style.color = 'var(--text-muted)';
            muted.textContent = r.providerName + ': ';
            tdModel.appendChild(muted);
            tdModel.appendChild(document.createTextNode(r.model));
            tr.appendChild(tdModel);

            for (const f of features) {
                const rec = modelRecommendation(r.provider, r.model, f);
                const td = document.createElement('td');
                td.style.cssText = 'padding:0.4rem;text-align:center;cursor:pointer;';
                td.title = rec.text;
                td.textContent = rec.icon;
                td.onclick = () => quickSetOverride(r.provider, r.model, f);
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        content.appendChild(table);

        const hint = document.createElement('div');
        hint.style.cssText = 'margin-top:0.75rem;font-size:0.8rem;color:var(--text-muted);';
        hint.textContent = 'Klick auf eine Zelle übernimmt das Modell als Override für die Task.';
        content.appendChild(hint);
    } catch (e) {
        content.replaceChildren();
        const err = document.createElement('em');
        err.textContent = 'Fehler: ' + e.message;
        content.appendChild(err);
    }
}

function closeModelComparisonModal() {
    document.getElementById('modelComparisonModal').style.display = 'none';
}

async function quickSetOverride(provider, model, feature) {
    _featureOverridesState[feature] = { provider, model: model || null };
    const ok = await persistOverrides();
    if (ok) {
        renderFeatureOverrideCards();
        closeModelComparisonModal();
        alert('✓ ' + FEATURE_LABELS[feature] + ' → ' + model);
    }
}
```

- [ ] **Step 4: loadFeatureOverrides bei Settings-Mount aufrufen**

```bash
grep -n "function showSettingsSection" /Library/WebServer/Documents/Bewerbungstracker/index.html
```

In der `showSettingsSection`-Funktion, am Ende einfügen:

```javascript
    if (name === 'ai') {
        loadFeatureOverrides();
    }
```

- [ ] **Step 5: Service-Worker Cache bumpen**

In `service-worker.js`, Zeile 15:

```javascript
const CACHE_NAME = 'bewerbungs-tracker-v9';  // war v8
```

- [ ] **Step 6: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(frontend): Pro-Task Override-Cards + Modell-Vergleichs-Modal

- 4 Override-Cards (Match, Cover-Letter, CV-Summarize, Email-Analyse)
- Checkbox aktiviert Override -> Provider+Model-Dropdowns werden enabled
- Live-Empfehlungen für gewähltes Modell über alle 4 Tasks
- Modell-Vergleichs-Modal mit allen verfügbaren Modellen x Tasks
- Click-to-set in der Vergleichs-Tabelle
- Alle dynamischen Strings via DOM-API (kein innerHTML mit user-data)
- SW-Cache v8 -> v9 für Refresh"
```

---

## Task 10: Full-Test-Run + Deploy

**Files:** keine

- [ ] **Step 1: Komplette Test-Suite laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -m pytest tests/ -q --tb=short
```

Expected: alle Tests passen (vorher 293, nach den neuen Tasks ca. 313+).

- [ ] **Step 2: Push zu origin**

```bash
git push origin master
```

- [ ] **Step 3: VPS-Pull + Migration + Restart**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && \
  cp instance/bewerbungstracker.db instance/bewerbungstracker.db.before-feature-overrides && \
  git pull origin master && \
  alembic upgrade head && \
  systemctl restart bewerbungen.service && \
  sleep 2 && \
  systemctl is-active bewerbungen.service'
```

Expected:
- Backup erstellt
- Pull erfolgreich
- Migration `a8c9d0e1f2g3` applied
- Service `active`

- [ ] **Step 4: Smoke-Test**

```bash
ssh ionos-vps 'curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://127.0.0.1:5000/api/profile/feature-models'
```

Expected: `HTTP: 401` (Auth-required = korrekt, Endpoint existiert)

- [ ] **Step 5: Browser-Verifikation**

Im Browser:
1. Hard-Reload (Cmd+Shift+R) — SW v9 aktiviert sich
2. Nochmal Cmd+Shift+R — SW übernimmt
3. Settings → KI Provider → siehe neue "🎯 Pro-Task-Modelle" Sektion
4. Eine Override-Card aufklappen → Checkbox aktivieren → Provider+Modell wählen → Speichern
5. Test: Anschreiben generieren mit Override → Backend nutzt den Override

---

## Verification Checklist

Nach allen Tasks:
- ✅ Alembic-Migration `a8c9d0e1f2g3` applied lokal + VPS
- ✅ `User.get_model_for(feature)` Helper mit Fallback
- ✅ GET/PATCH `/api/profile/feature-models` Endpoints
- ✅ 4 Service-Layer-Anpassungen (Cover-Letter, Match, CV-Summarize, Email-Analyse)
- ✅ Empfehlungs-Engine im Frontend (heuristisch, model-name-basiert)
- ✅ 4 expandable Override-Cards in Settings-View
- ✅ Empfehlungs-Tabelle als Modal mit Click-to-Set
- ✅ Bestehende Tests grün geblieben (Default-Path unverändert)
- ✅ SW-Cache v8 → v9 für Browser-Refresh
- ✅ Deployment auf VPS ohne Daten-Verlust
