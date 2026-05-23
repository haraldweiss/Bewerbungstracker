# Claude-Backup-Cost Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den unkontrollierten Claude-Backup-Fallback bei Ollama-Down so abschotten, dass kein User mehr als sein `job_daily_budget_cents` ($5) pro Tag verbrennen kann.

**Architecture:** Drei Phasen sequentiell. Phase 1 = DB-only (Sonnet→Haiku-Modell). Phase 2A = Whitelist im `build_fallback_kwargs` (nur `match`-Feature darf Backup nutzen). Phase 2B = zentrales `cost_tracker.py` plus Cap-Check und Post-Call-Recording im `ai_provider_client.chat()`-Wrapper. Nach 2B wird die Whitelist wieder geöffnet, weil dann Cost-Tracking überall greift.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, SQLite, pytest, anthropic SDK (lazy import).

---

## Phase 1 — Backup-Modell Sonnet→Haiku

### Task 1: SQL-Update + Verifikation

**Files:**
- Modify: `instance/bewerbungstracker.db` (Prod-DB auf VPS, kein lokales File)

- [ ] **Step 1: Aktuellen Backup-Modell-Wert in der DB sichern**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && python3 -c "
import sqlite3
con = sqlite3.connect(\"instance/bewerbungstracker.db\")
for r in con.execute(\"SELECT id, email, ai_provider_backup, ai_provider_backup_model FROM users\"):
    print(r)
"'
```

Expected output: 1 Zeile mit `harald.weiss@wolfinisoftware.de` + `ai_provider_backup='claude'` + `ai_provider_backup_model='claude-sonnet-4-6'`.

Notiere den ursprünglichen Wert für Rollback.

- [ ] **Step 2: UPDATE durchführen**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && python3 -c "
import sqlite3
con = sqlite3.connect(\"instance/bewerbungstracker.db\")
con.execute(\"UPDATE users SET ai_provider_backup_model=? WHERE id=?\",
            (\"claude-haiku-4-5-20251001\", \"03bd2c3d-791e-46f7-b9b8-e1e51840c05d\"))
con.commit()
print(\"updated rows:\", con.total_changes)
"'
```

Expected: `updated rows: 1`.

- [ ] **Step 3: Verifikation**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && python3 -c "
import sqlite3
con = sqlite3.connect(\"instance/bewerbungstracker.db\")
r = con.execute(\"SELECT ai_provider_backup_model FROM users WHERE id=?\",
                (\"03bd2c3d-791e-46f7-b9b8-e1e51840c05d\",)).fetchone()
print(r)
assert r[0] == \"claude-haiku-4-5-20251001\", f\"unerwartet: {r[0]}\"
print(\"OK\")
"'
```

Expected: `('claude-haiku-4-5-20251001',)` und `OK`.

- [ ] **Step 4: Phase 1 in Memory dokumentieren**

```bash
# Editiere /Users/haraldweiss/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/incident_claude_cost_burst_2026_05_22.md
# Ergaenze am Ende einen "## Phase 1 angewendet (2026-05-23)"-Abschnitt:
# - Backup-Modell von claude-sonnet-4-6 auf claude-haiku-4-5-20251001
# - Rollback: SQL UPDATE zurueck auf 'claude-sonnet-4-6'
```

(Kein git-commit hier — DB-State ist die einzige Aenderung. Memory-Update reicht.)

---

## Phase 2A — Pragmatic Cut: Whitelist im build_fallback_kwargs

### Task 2A.1: Whitelist-Logik in build_fallback_kwargs (TDD)

**Files:**
- Modify: `services/ai_provider_client.py:233-256`
- Test: `tests/services/test_ai_provider_client.py` (vorhandene Datei, am Ende anhaengen)

- [ ] **Step 1: Failing Test schreiben**

Datei: `tests/services/test_ai_provider_client.py` (am Ende anhaengen):

```python


# Phase 2A: Backup-Whitelist
def test_build_fallback_kwargs_without_feature_returns_empty():
    """Default-Aufruf ohne feature= darf KEIN Backup mehr aktivieren.
    Safe by default."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    assert build_fallback_kwargs(user) == {}


def test_build_fallback_kwargs_non_whitelisted_feature_returns_empty():
    """Features ausserhalb der Whitelist bekommen KEIN Backup."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    assert build_fallback_kwargs(user, feature='email_parse') == {}
    assert build_fallback_kwargs(user, feature='cover_letter') == {}
    assert build_fallback_kwargs(user, feature='cv_summarize') == {}
    assert build_fallback_kwargs(user, feature='pattern_learn') == {}


def test_build_fallback_kwargs_match_feature_returns_kwargs():
    """match steht in der Whitelist und bekommt Backup-kwargs."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    kw = build_fallback_kwargs(user, feature='match')
    assert kw['fallback_provider'] == 'claude'
    assert kw['fallback_model'] == 'claude-haiku-4-5-20251001'
```

- [ ] **Step 2: Tests laufen lassen — sollen FAILen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
source venv/bin/activate
python -m pytest tests/services/test_ai_provider_client.py -k "phase_2a or whitelist or feature" -v
```

Expected: 3 Fails — `TypeError: build_fallback_kwargs() got an unexpected keyword argument 'feature'` oder die Whitelist-Logik fehlt.

- [ ] **Step 3: Implementation in services/ai_provider_client.py**

Ersetze die bestehende Funktion (ca. Zeile 233-256):

```python
# Whitelist: nur diese Features duerfen heute Backup-Fallback nutzen.
# Erweitert in Phase 2B nach Einfuehrung des zentralen Cost-Tracker.
ALLOW_BACKUP_FEATURES = {'match'}


def build_fallback_kwargs(user, feature: str | None = None) -> dict:
    """Baut die fallback_provider/fallback_model/fallback_config kwargs für chat().

    - Returns {} wenn der User kein Backup hat
    - Returns {} wenn feature nicht in ALLOW_BACKUP_FEATURES (Safe-by-Default,
      verhindert dass ungetracker Pfade Sonnet/Haiku ungebremst nutzen)
    - Returns nur provider+model wenn explizit konfiguriert
    - Returns provider+model+config wenn Admin-Auto-Fallback
    """
    if feature not in ALLOW_BACKUP_FEATURES:
        return {}
    import os
    backup = user.get_backup_config() if user else None
    if not backup:
        return {}
    provider, model, is_auto = backup
    kwargs = {'fallback_provider': provider}
    if model:
        kwargs['fallback_model'] = model
    if is_auto:
        api_key = os.getenv('CLAUDE_API_KEY')
        if api_key:
            kwargs['fallback_config'] = {'api_key': api_key}
    return kwargs
```

- [ ] **Step 4: Tests laufen — sollen PASSen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -v
```

Expected: 3 neue Tests PASS, 4 alte PASS = 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/ai_provider_client.py tests/services/test_ai_provider_client.py
git commit -m "$(cat <<'EOF'
feat(ai_client): add feature whitelist to build_fallback_kwargs

Phase 2A: nur Features in ALLOW_BACKUP_FEATURES={'match'} duerfen
heute Backup-Fallback auf Claude nutzen. Andere Caller bekommen
{} zurueck und damit fail-loud bei Ollama-Down statt unsichtbaren
Sonnet-Kosten zu produzieren.

Wird in Phase 2B wieder geoeffnet sobald zentrales Cost-Tracking
greift.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2A.2: Alle 5 Caller updaten

**Files:**
- Modify: `api/jobs_cron.py:786` — feature='match'
- Modify: `api/cover_letters.py:124` — feature='cover_letter'
- Modify: `api/providers.py:371` — feature='chat' (= ad-hoc Test-Chat)
- Modify: `services/job_sources/email_jobs.py:1033` — feature='email_parse'
- Modify: `services/job_sources/email_jobs.py:1103` — feature='email_parse'

- [ ] **Step 1: api/jobs_cron.py:786 updaten**

Alt:
```python
    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user)
```

Neu:
```python
    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='match')
```

- [ ] **Step 2: api/cover_letters.py:124 updaten**

Alt:
```python
    fallback_kwargs = build_fallback_kwargs(user)
```

Neu:
```python
    fallback_kwargs = build_fallback_kwargs(user, feature='cover_letter')
```

- [ ] **Step 3: api/providers.py:371 updaten**

Alt:
```python
        fallback_kwargs = ai_provider_client.build_fallback_kwargs(user)
```

Neu:
```python
        fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='chat')
```

- [ ] **Step 4: services/job_sources/email_jobs.py — beide Stellen updaten**

Beide Stellen (Zeile 1033 und 1103) sind identisch:

Alt:
```python
    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user)
```

Neu:
```python
    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='email_parse')
```

(Edit-Tool: `replace_all=true` ist hier safe weil beide Stellen denselben Text haben.)

- [ ] **Step 5: Alle Tests laufen (Regression)**

```bash
python -m pytest tests/services/test_ai_provider_client.py tests/api/test_jobs_user.py tests/api/test_jobs_cron.py -q 2>&1 | tail -10
```

Expected: alle Tests die vorher liefen, laufen weiter. Eventuell brechen Tests die `build_fallback_kwargs` ohne `feature` mocken — die hatte ich beim Design vergessen. Falls ja: Mocks anpassen oder feature='match' im Testaufruf hinzufuegen.

- [ ] **Step 6: Commit + Deploy**

```bash
git add api/jobs_cron.py api/cover_letters.py api/providers.py services/job_sources/email_jobs.py
git commit -m "$(cat <<'EOF'
fix(callers): pass feature= to build_fallback_kwargs

Phase 2A complete: alle 5 Aufrufer markieren ihr Feature.
- match (jobs_cron): bekommt weiter Backup
- cover_letter, chat, email_parse: fail-loud bei Ollama-Down
  bis Phase 2B zentrales Cost-Tracking bringt

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin master && git push vps master
```

Expected: deploy.log auf VPS zeigt `bewerbungen.service neu gestartet`.

---

### Task 2A.3: Smoke-Test auf Production

- [ ] **Step 1: Verify Whitelist-Code ist deployed**

```bash
ssh ionos-vps 'grep -n "ALLOW_BACKUP_FEATURES" /var/www/bewerbungen/services/ai_provider_client.py'
```

Expected: 2 Zeilen Match (Definition + Verwendung).

- [ ] **Step 2: Verify Caller passen feature=**

```bash
ssh ionos-vps 'grep -rn "build_fallback_kwargs(user, feature=" /var/www/bewerbungen/ --include="*.py" | head'
```

Expected: 5 Treffer (match, cover_letter, chat, 2× email_parse).

- [ ] **Step 3: 24h-Monitoring — Cost-Effekt pruefen**

Nach 24h: in Claudetracker `usage_records` schauen:
```bash
ssh ionos-vps 'python3 -c "
import sqlite3
con = sqlite3.connect(\"/var/www/wolfinisoftware/claudetracker/backend/database.sqlite\")
for r in con.execute(\"SELECT date(timestamp), model, COUNT(*), ROUND(MAX(cost_usd),2) FROM usage_records WHERE timestamp > date(\\\"now\\\",\\\"-2 days\\\") GROUP BY date(timestamp), model ORDER BY 1 DESC, 4 DESC LIMIT 20\"):
    print(r)
"'
```

Expected: heutiger Tag zeigt Haiku-Modell (`Anthropic API (bewerbungstracker)` mit cost ≤ $5).

---

## Phase 2B — Zentrales Cost-Tracking + Cap im chat()-Wrapper

### Task 2B.1: services/cost_tracker.py erstellen (TDD)

**Files:**
- Create: `services/cost_tracker.py`
- Create: `tests/services/test_cost_tracker.py`

- [ ] **Step 1: Failing Tests schreiben**

Datei: `tests/services/test_cost_tracker.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from datetime import datetime, timedelta
from app import create_app
from database import db
from models import ApiCall


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_estimate_cost_usd_haiku():
    from services.cost_tracker import estimate_cost_usd
    # Haiku 4.5: $1/MTok in, $5/MTok out
    usd = estimate_cost_usd('claude-haiku-4-5-20251001', tokens_in=1_000_000, tokens_out=1_000_000)
    assert usd == pytest.approx(6.0, rel=0.01)


def test_estimate_cost_usd_sonnet():
    from services.cost_tracker import estimate_cost_usd
    # Sonnet 4.6: $3/MTok in, $15/MTok out
    usd = estimate_cost_usd('claude-sonnet-4-6', tokens_in=1_000_000, tokens_out=1_000_000)
    assert usd == pytest.approx(18.0, rel=0.01)


def test_estimate_cost_usd_ollama_is_zero():
    from services.cost_tracker import estimate_cost_usd
    assert estimate_cost_usd('mistral-nemo:12b', 100_000, 100_000) == 0.0
    assert estimate_cost_usd('deepseek-r1:8b', 100_000, 100_000) == 0.0


def test_record_call_writes_api_calls_row(app):
    from services.cost_tracker import record_call
    record_call(user_id='u1', endpoint='ep', model='claude-haiku-4-5-20251001',
                tokens_in=1000, tokens_out=200, cost_usd=0.002, key_owner='server')
    db.session.commit()
    rows = ApiCall.query.filter_by(user_id='u1').all()
    assert len(rows) == 1
    assert rows[0].model == 'claude-haiku-4-5-20251001'
    assert rows[0].cost == pytest.approx(0.002)


def test_user_today_cost_cents_sums_today(app):
    from services.cost_tracker import record_call, user_today_cost_cents
    # 3 calls heute mit total 0.045 USD = 4.5 cents -> 5 cents (int round)
    for cost in (0.020, 0.015, 0.010):
        record_call(user_id='u1', endpoint='ep', model='m', tokens_in=1, tokens_out=1,
                    cost_usd=cost, key_owner='server')
    db.session.commit()
    assert user_today_cost_cents('u1') == 5


def test_user_today_cost_cents_ignores_yesterday(app):
    from services.cost_tracker import record_call, user_today_cost_cents
    record_call(user_id='u1', endpoint='ep', model='m', tokens_in=1, tokens_out=1,
                cost_usd=99.0, key_owner='server')
    # Manuelle Manipulation: gestern setzen
    db.session.flush()
    call = ApiCall.query.filter_by(user_id='u1').first()
    call.timestamp = datetime.utcnow() - timedelta(days=1, hours=2)
    db.session.commit()
    assert user_today_cost_cents('u1') == 0
```

- [ ] **Step 2: Tests laufen — sollen FAILen**

```bash
python -m pytest tests/services/test_cost_tracker.py -v
```

Expected: alle 6 Fails (ModuleNotFoundError oder NameError).

- [ ] **Step 3: services/cost_tracker.py implementieren**

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Zentralisiertes Cost-Tracking fuer alle AI-Calls.

Ersetzt die fruehere lokale Logik in api/jobs_cron.py — single source of
truth fuer Tageskosten + Modell-aware Cost-Estimation. Ermoeglicht das
globale Daily-Budget-Cap im ai_provider_client.chat()-Wrapper.
"""

from datetime import datetime
from database import db
from models import ApiCall


# Anthropic-Pricing (USD pro 1M Tokens). Aktualisierung wenn sich Modell-Preise aendern.
_PRICING = {
    'claude-haiku-4-5-20251001':  (1.00,  5.00),
    'claude-haiku-4-5':            (1.00,  5.00),  # alias
    'claude-sonnet-4-6':           (3.00, 15.00),
    'claude-opus-4-7':            (15.00, 75.00),
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Berechnet USD-Kosten basierend auf Modell-Pricing.

    Ollama- und andere lokale Modelle: 0.0 (= kein API-Bill).
    Unbekannte Claude-Modelle: 0.0 (conservative — lieber 0 als wilde Schaetzung).
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        return 0.0
    in_per_m, out_per_m = pricing
    return (tokens_in / 1_000_000) * in_per_m + (tokens_out / 1_000_000) * out_per_m


def record_call(user_id: str, endpoint: str, model: str,
                tokens_in: int, tokens_out: int, cost_usd: float,
                key_owner: str = 'server') -> None:
    """Schreibt einen ApiCall-Eintrag. Caller muss db.session.commit() selbst aufrufen."""
    db.session.add(ApiCall(
        user_id=user_id, endpoint=endpoint,
        model=model, tokens_in=tokens_in, tokens_out=tokens_out,
        cost=cost_usd, key_owner=key_owner,
    ))
    db.session.flush()


def user_today_cost_cents(user_id: str) -> int:
    """Summiert ApiCall.cost fuer den User seit Mitternacht UTC. Returns cents."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (db.session.query(db.func.sum(ApiCall.cost))
             .filter(ApiCall.user_id == user_id, ApiCall.timestamp >= today_start)
             .scalar()) or 0.0
    return int(round(total * 100))
```

- [ ] **Step 4: Tests laufen — sollen PASSen**

```bash
python -m pytest tests/services/test_cost_tracker.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add services/cost_tracker.py tests/services/test_cost_tracker.py
git commit -m "feat(cost_tracker): centralize ApiCall recording + budget query

Phase 2B Schritt 1: Single Source of Truth fuer Cost-Tracking.
estimate_cost_usd kennt Modell-Pricing (Haiku/Sonnet/Opus).
record_call schreibt ApiCall, user_today_cost_cents liest Summe.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2B.2: jobs_cron.py auf cost_tracker umstellen

**Files:**
- Modify: `api/jobs_cron.py:90-120` (entferne lokale _get_anthropic_client/_estimate_cost_usd/_user_today_cost_cents)
- Modify: `api/jobs_cron.py:910` (ApiCall-Insert → cost_tracker.record_call)
- Modify: `api/jobs_cron.py:969` (ApiCall-Insert → cost_tracker.record_call)

- [ ] **Step 1: Import oben in jobs_cron.py ergänzen**

In `api/jobs_cron.py` nach den bestehenden imports einfuegen:
```python
from services import cost_tracker
```

- [ ] **Step 2: ApiCall-Insert in L910 ersetzen**

Alt (L910-915):
```python
    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=logged_model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_usd,
        key_owner=key_owner,
    ))
    db.session.flush()
```

Neu:
```python
    cost_tracker.record_call(
        user_id=user.id, endpoint='/api/jobs/match',
        model=logged_model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost_usd=cost_usd,
        key_owner=key_owner,
    )
```

- [ ] **Step 3: ApiCall-Insert in L969 ersetzen**

Alt (L969-975):
```python
    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_usd,
        key_owner=key_owner,
    ))
    db.session.flush()
```

Neu:
```python
    cost_tracker.record_call(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost_usd=cost_usd,
        key_owner=key_owner,
    )
```

- [ ] **Step 4: Lokale Helper-Funktionen entfernen**

In `api/jobs_cron.py` die Funktionen `_estimate_cost_usd` (ca. L99) und
`_user_today_cost_cents` (ca. L113) komplett entfernen.

Suche+ersetze alle Aufrufe von `_user_today_cost_cents(` durch `cost_tracker.user_today_cost_cents(`.
Suche+ersetze alle Aufrufe von `_estimate_cost_usd(` durch `cost_tracker.estimate_cost_usd(` —
ABER `_estimate_cost_usd(tokens_in, tokens_out)` hatte keine Modell-Angabe; pruefen ob der
Caller eine Modell-Info hat. Falls nicht: vorerst Haiku-Pricing annehmen (`cost_tracker.estimate_cost_usd('claude-haiku-4-5-20251001', tokens_in, tokens_out)`).

- [ ] **Step 5: Tests laufen — kein Regression**

```bash
python -m pytest tests/api/test_jobs_cron.py tests/api/test_jobs_user.py tests/services/test_cost_tracker.py -q 2>&1 | tail -5
```

Expected: keine NEUEN Failures. Bestehende anthropic-Import-Fehler bleiben (irrelevant).

- [ ] **Step 6: Commit**

```bash
git add api/jobs_cron.py
git commit -m "refactor(jobs_cron): use central cost_tracker instead of inline ApiCall

Phase 2B Schritt 2: ApiCall-Inserts und _user_today_cost_cents-
Aufrufe ueber services.cost_tracker. Verhaltensgleich, aber jetzt
hat cost_tracker das Monopol auf das api_calls-Schreiben.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2B.3: Cap-Check VOR chat() in ai_provider_client (TDD)

**Files:**
- Modify: `services/ai_provider_client.py` (chat-Methode)
- Test: `tests/services/test_ai_provider_client.py` (anhaengen)

- [ ] **Step 1: Failing Tests schreiben**

In `tests/services/test_ai_provider_client.py` anhaengen:

```python


# Phase 2B: Budget-Cap im chat()-Wrapper
def test_chat_strips_claude_fallback_when_budget_exhausted(monkeypatch, app):
    """Wenn user heute schon ueber Budget: fallback_* aus dem Service-Body strippen."""
    from services.ai_provider_client import AIProviderClient
    # Mock user_today_cost_cents auf "ueber Limit"
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 600)
    # Mock user lookup damit budget_cents bekannt ist
    monkeypatch.setattr('services.ai_provider_client._lookup_user_budget_cents',
                        lambda uid: 500)
    # Mock _post damit wir den body inspizieren koennen
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(AIProviderClient, '_post', fake_post)

    client = AIProviderClient()
    client.chat(user_id='u1', provider='ollama', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='claude', fallback_model='claude-haiku-4-5-20251001')
    assert 'fallback_provider' not in captured['body']
    assert 'fallback_model' not in captured['body']


def test_chat_keeps_fallback_when_budget_remaining(monkeypatch, app):
    """Budget noch da → kwargs bleiben unveraendert."""
    from services.ai_provider_client import AIProviderClient
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 100)  # nur 100 cents von 500
    monkeypatch.setattr('services.ai_provider_client._lookup_user_budget_cents',
                        lambda uid: 500)
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(AIProviderClient, '_post', fake_post)

    client = AIProviderClient()
    client.chat(user_id='u1', provider='ollama', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='claude', fallback_model='claude-haiku-4-5-20251001')
    assert captured['body'].get('fallback_provider') == 'claude'
    assert captured['body'].get('fallback_model') == 'claude-haiku-4-5-20251001'


def test_chat_keeps_non_claude_fallback_unconditionally(monkeypatch, app):
    """Ollama-Fallback ist kostenlos und wird nicht gestripped — egal Budget-Status."""
    from services.ai_provider_client import AIProviderClient
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 9999)
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(AIProviderClient, '_post', fake_post)

    client = AIProviderClient()
    client.chat(user_id='u1', provider='claude', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='ollama', fallback_model='qwen3-coder')
    assert captured['body']['fallback_provider'] == 'ollama'
```

- [ ] **Step 2: Tests laufen — sollen FAILen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -k "chat_strips or chat_keeps or chat_keeps_non" -v
```

Expected: alle 3 Fails (AttributeError oder kein Stripping aktiv).

- [ ] **Step 3: chat()-Wrapper und Helper implementieren**

In `services/ai_provider_client.py` — Helper-Funktion **vor** der Klasse einfuegen:

```python
def _lookup_user_budget_cents(user_id: str) -> int:
    """Liest user.job_daily_budget_cents oder default 500. Isoliert, damit tests mocken koennen."""
    try:
        from models import User
        user = User.query.get(user_id)
        if user is None:
            return 500
        return int(user.job_daily_budget_cents or 500)
    except Exception:
        return 500


def _should_strip_claude_fallback(user_id: str, fallback_provider: str | None,
                                   fallback_model: str | None) -> bool:
    """Prueft ob Budget-Cap greift und Backup gestrippt werden soll."""
    if not user_id:
        return False
    is_claude = (
        (fallback_provider or '').lower() == 'claude'
        or 'claude' in (fallback_model or '').lower()
    )
    if not is_claude:
        return False
    try:
        from services import cost_tracker
        spent = cost_tracker.user_today_cost_cents(user_id)
        budget = _lookup_user_budget_cents(user_id)
        return spent >= budget
    except Exception:
        # Bei DB-Fehler permissiv durchlassen + Warnung
        import logging
        logging.getLogger(__name__).warning(
            "cost_tracker check failed for user %s — allowing call", user_id,
        )
        return False
```

In der `chat()`-Methode, ganz oben (bevor body gebaut wird), einfügen:

```python
    def chat(self, *, user_id: str, provider: str, model: str,
             messages: list, max_tokens: int = 2000,
             fallback_provider: str | None = None,
             fallback_model: str | None = None,
             fallback_config: dict | None = None,
             **extra) -> 'ChatResponse':
        # Phase 2B: Budget-Cap vor Backup-Verwendung
        if _should_strip_claude_fallback(user_id, fallback_provider, fallback_model):
            import logging
            logging.getLogger(__name__).warning(
                "Daily budget cap hit for user %s — stripping claude fallback",
                user_id,
            )
            fallback_provider = None
            fallback_model = None
            fallback_config = None

        # bestehender Body-Aufbau hier weiter — wenn None, dann nicht ins body schreiben
        ...
```

**Wichtig:** das ist eine Skizze. Die echte `chat()` Methode (Zeile ~150-200 in ai_provider_client.py) hat ihre eigene Body-Baulogik. Im Plan-Step muss der Engineer:
- Die Original-`chat()`-Methode lesen
- Den Cap-Check ganz vorne einfuegen
- Sicherstellen dass `fallback_*` None erkannt + ignoriert wird beim Body-Bau (vorhandene Logik macht das schon mit Default-None-kwargs)

- [ ] **Step 4: Tests laufen — sollen PASSen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -v
```

Expected: alle Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/ai_provider_client.py tests/services/test_ai_provider_client.py
git commit -m "feat(ai_client): strip claude fallback when daily budget exhausted

Phase 2B Schritt 3: chat()-Wrapper prueft vor Service-Call ob
user_today_cost_cents >= job_daily_budget_cents. Wenn ja UND
fallback_provider/model auf Claude zeigt: strippe die fallback_*
kwargs aus dem Service-Body. Effekt: ai-provider-service macht
keinen Backup-Call, Ollama-Down wird fail-loud zum User durchgereicht.

Helper _should_strip_claude_fallback isoliert die Logik fuer
Mockability in Tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2B.4: Post-Call-Recording bei fallback_used

**Files:**
- Modify: `services/ai_provider_client.py` (chat-Methode)
- Test: `tests/services/test_ai_provider_client.py` (anhaengen)

- [ ] **Step 1: Failing Tests schreiben**

In `tests/services/test_ai_provider_client.py` anhaengen:

```python


def test_chat_records_cost_when_fallback_used(monkeypatch, app):
    """Wenn response.fallback_used=True: cost_tracker.record_call wird aufgerufen
    mit dem echten Backup-Modell + Cost-Estimate."""
    from services.ai_provider_client import AIProviderClient
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents', lambda uid: 0)
    monkeypatch.setattr('services.ai_provider_client._lookup_user_budget_cents', lambda uid: 500)

    def fake_post(self, path, body):
        return {
            'result': {
                'content': [{'text': 'hi'}],
                'model': 'claude-haiku-4-5-20251001',
                'usage': {'input_tokens': 100, 'output_tokens': 50},
                'fallback_used': True,
            }
        }
    monkeypatch.setattr(AIProviderClient, '_post', fake_post)

    recorded = []
    monkeypatch.setattr('services.cost_tracker.record_call',
                        lambda **kw: recorded.append(kw))

    client = AIProviderClient()
    client.chat(user_id='u1', provider='ollama', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='claude',
                fallback_model='claude-haiku-4-5-20251001')

    assert len(recorded) == 1
    assert recorded[0]['model'] == 'claude-haiku-4-5-20251001'
    assert recorded[0]['tokens_in'] == 100
    assert recorded[0]['tokens_out'] == 50
    assert recorded[0]['cost_usd'] > 0


def test_chat_does_not_record_when_fallback_not_used(monkeypatch, app):
    """Primary-Path (Ollama) erfolgreich: KEIN cost_tracker.record_call (oder nur cost=0)."""
    from services.ai_provider_client import AIProviderClient
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents', lambda uid: 0)
    monkeypatch.setattr('services.ai_provider_client._lookup_user_budget_cents', lambda uid: 500)

    def fake_post(self, path, body):
        return {
            'result': {'content': [{'text': 'hi'}], 'model': 'qwen3-coder',
                       'usage': {'input_tokens': 100, 'output_tokens': 50},
                       'fallback_used': False}
        }
    monkeypatch.setattr(AIProviderClient, '_post', fake_post)

    recorded = []
    monkeypatch.setattr('services.cost_tracker.record_call',
                        lambda **kw: recorded.append(kw))

    client = AIProviderClient()
    client.chat(user_id='u1', provider='ollama', model='qwen3-coder',
                messages=[{'role': 'user', 'content': 'hi'}])

    # Entweder gar kein Record, oder einer mit cost=0 — Test akzeptiert beides
    if recorded:
        assert recorded[0]['cost_usd'] == 0.0
```

- [ ] **Step 2: Tests laufen — sollen FAILen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -k "records_cost or does_not_record" -v
```

Expected: 1 Fail (recorded list ist leer obwohl fallback_used=True).

- [ ] **Step 3: Implementation in chat()**

In `services/ai_provider_client.py` `chat()`-Methode am Ende — nach dem Build und vor dem Return — einfuegen:

```python
        # Phase 2B: Post-Call-Recording wenn Backup-Pfad genommen wurde
        if response.fallback_used and response.model:
            try:
                from services import cost_tracker
                cost_usd = cost_tracker.estimate_cost_usd(
                    response.model, response.usage.input_tokens, response.usage.output_tokens,
                )
                cost_tracker.record_call(
                    user_id=user_id, endpoint='ai_provider_client.chat',
                    model=response.model,
                    tokens_in=response.usage.input_tokens,
                    tokens_out=response.usage.output_tokens,
                    cost_usd=cost_usd, key_owner='server',
                )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "cost_tracker.record_call failed: %s — call already done",
                    exc,
                )
```

- [ ] **Step 4: Tests laufen — sollen PASSen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -v
```

Expected: alle Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/ai_provider_client.py tests/services/test_ai_provider_client.py
git commit -m "feat(ai_client): record cost for backup-fallback calls

Phase 2B Schritt 4: wenn response.fallback_used, schreibt der
chat()-Wrapper einen ApiCall ueber cost_tracker. Damit landen ALLE
Claude-Calls in api_calls — egal aus welchem Feature, egal welcher
Caller. Cost-Visibility ist endlich komplett.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2B.5: Whitelist auf alle Features oeffnen

**Files:**
- Modify: `services/ai_provider_client.py` (`ALLOW_BACKUP_FEATURES`)
- Test: `tests/services/test_ai_provider_client.py` (anpassen oder ergaenzen)

- [ ] **Step 1: ALLOW_BACKUP_FEATURES erweitern**

Alt:
```python
ALLOW_BACKUP_FEATURES = {'match'}
```

Neu:
```python
# Phase 2B: Whitelist wird obsolet, weil zentrales Cost-Tracking + Cap im
# chat()-Wrapper jetzt fuer alle Features gilt. Wir behalten die Konstante
# als Safety-Net (z.B. fuer Features wo wir explizit kein Backup wollen).
ALLOW_BACKUP_FEATURES = {'match', 'cover_letter', 'email_parse',
                         'cv_summarize', 'pattern_learn', 'chat'}
```

- [ ] **Step 2: Existing Phase-2A-Tests anpassen**

Die Tests `test_build_fallback_kwargs_non_whitelisted_feature_returns_empty` testen
`email_parse`, `cover_letter`, `cv_summarize`, `pattern_learn` als NICHT-whitelisted.
Jetzt sind sie whitelisted. Test umbenennen + Pruefe-Logik invertieren:

Alt:
```python
def test_build_fallback_kwargs_non_whitelisted_feature_returns_empty():
    ...
    assert build_fallback_kwargs(user, feature='email_parse') == {}
```

Neu:
```python
def test_build_fallback_kwargs_all_known_features_get_backup():
    """Phase 2B: alle bekannten Features sind whitelisted, Cap erfolgt jetzt
    im chat()-Wrapper."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    for feature in ['match', 'cover_letter', 'email_parse', 'cv_summarize', 'pattern_learn', 'chat']:
        assert build_fallback_kwargs(user, feature=feature) != {}, f"feature {feature} nicht in Whitelist"


def test_build_fallback_kwargs_unknown_feature_returns_empty():
    """Unbekanntes/None Feature bleibt safe-by-default."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    assert build_fallback_kwargs(user, feature=None) == {}
    assert build_fallback_kwargs(user, feature='unbekannt_xyz') == {}
```

- [ ] **Step 3: Tests laufen — sollen PASSen**

```bash
python -m pytest tests/services/test_ai_provider_client.py -v
```

Expected: alle Tests PASS (Phase 2A Tests sind ersetzt, Phase 2B Tests bleiben).

- [ ] **Step 4: Commit**

```bash
git add services/ai_provider_client.py tests/services/test_ai_provider_client.py
git commit -m "feat(ai_client): re-enable backup for all features under global cap

Phase 2B complete: weil chat()-Wrapper jetzt die Tagessumme aller
Claude-Calls trackt und cap-stripping macht, koennen alle Features
wieder Backup-Fallback nutzen. ALLOW_BACKUP_FEATURES wird quasi
obsolet, bleibt aber als Safety-Net (z.B. fuer 'unbekannt' = leer).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 5: Push + Deploy**

```bash
git push origin master && git push vps master
```

Expected: deploy.log auf VPS zeigt restart.

- [ ] **Step 6: End-to-End Smoke**

In Production: manuell einen Match-Cron triggern, schauen ob api_calls einen Eintrag mit Haiku-Cost > 0 bekommt (= echtes Tracking funktioniert), und in den Flask-Logs nach "Daily budget cap hit" suchen (sollte erst auftreten wenn $5 erreicht).

```bash
ssh ionos-vps 'tail -50 /var/log/bewerbungen/error.log | grep -E "budget cap|fallback"'
```

- [ ] **Step 7: Memory final aktualisieren**

In `~/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/incident_claude_cost_burst_2026_05_22.md`
einen "## Resolved 2026-05-23"-Abschnitt mit Commit-Hashes der Phasen 1, 2A, 2B.

---

## Erfolgs-Verifikation (24h nach Deploy von Phase 2B)

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && python3 -c "
import sqlite3
con = sqlite3.connect(\"instance/bewerbungstracker.db\")
print(\"=== api_calls heute ===\")
for r in con.execute(\"SELECT model, COUNT(*), ROUND(SUM(cost),3) FROM api_calls WHERE date(timestamp)=date(\\\"now\\\") GROUP BY model\"):
    print(r)
"'
```

Expected: ALLE Modelle die heute genutzt wurden tauchen auf — inkl. Haiku-Backup-Calls mit cost > 0. Daily-Sum < $5 (= unter Cap).
