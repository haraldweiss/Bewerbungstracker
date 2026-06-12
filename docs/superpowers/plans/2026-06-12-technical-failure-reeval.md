# Technische Fehlbewertungen neu bewerten + Ollama-Fallback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** JobMatches, die aus technischen Gründen (Provider liefert kein JSON / Tunnel offline) nicht bewertet werden konnten, werden automatisch mit Ollama-Fallback und Backoff erneut bewertet statt als Fake-Score 0 verworfen.

**Architecture:** Neue Spalte `JobMatch.eval_attempts` zählt Inhalts-Fehlversuche. Der Match-Pfad (`_run_match_via_service`) fällt bei HTTP- *und* Inhalts-Fehlern des Free-Modells auf ein lokales Ollama-Modell zurück. Bei endgültigem Inhalts-Fehler wird kein Fake-Score geschrieben, sondern mit Backoff (1→2→4→8→12h) bis zu 5× erneut versucht; danach sichtbarer Marker. Ein Retry-Zweig im stündlichen `cron_claude_match` zieht diese Kandidaten unabhängig vom prefilter-Gate. Ein Einmal-Script stellt Altfälle zurück.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, Alembic, pytest, SQLite (WAL). AI über `ai_provider_client` → ai-provider-service.

**Spec:** `docs/superpowers/specs/2026-06-12-technical-failure-reeval-design.md`

---

## File Structure

| Datei | Verantwortung | Aktion |
|---|---|---|
| `alembic/versions/20260612_*_add_eval_attempts.py` | DB-Migration `eval_attempts` | Create |
| `models.py` | `JobMatch.eval_attempts` Spalte | Modify (~L463) |
| `services/job_matching/claude_matcher.py` | `MatchResult.failed`-Flag | Modify (~L72) |
| `services/job_matching/claude_utils.py` | Konstanten, Backoff/Failure-Helper, `_run_match_via_service`-Kette, `_run_claude_match_for`-Guard, lokaler Pfad | Modify |
| `services/tasks/handlers/cron_claude_match.py` | Retry-Auswahl-Zweig | Modify |
| `scripts/reeval_technical_failures.py` | Einmal-Cleanup Altbestand | Create |
| `tests/services/test_match_eval_retry.py` | Unit-Tests Fallback/Failure/Backoff/Retry | Create |
| `tests/services/test_reeval_script.py` | Test Cleanup-Auswahl | Create |
| `index.html` | (Verifikation — Marker wird schon gerendert) | Verify only |

**Design-Verfeinerung ggü. Spec (3.5):** Statt „beide Mengen vereinigen + deduplizieren" partitionieren wir sauber: Haupt-Zweig nur `prefilter_score >= 50`, Retry-Zweig nur `prefilter_score < 50 OR NULL`. Keine Überlappung, kein Dedup nötig.

---

## Task 1: DB-Migration — `eval_attempts`-Spalte

**Files:**
- Create: `alembic/versions/20260612_1200_add_eval_attempts.py`
- Modify: `models.py:463` (nach `_missing_skills`)

- [ ] **Step 1: Migration schreiben**

Create `alembic/versions/20260612_1200_add_eval_attempts.py`:

```python
"""add_eval_attempts_to_job_matches

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-06-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b0c1d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_matches', sa.Column(
        'eval_attempts', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('job_matches', 'eval_attempts')
```

- [ ] **Step 2: Model-Spalte ergänzen**

In `models.py`, direkt nach Zeile 465 (`_missing_skills = ...`) einfügen:

```python
    # Zähler für technische Inhalts-Fehlversuche (kein gültiges JSON vom Provider).
    # Bei Erfolg -> 0. >= MATCH_MAX_EVAL_ATTEMPTS = permanent technisch fehlgeschlagen.
    eval_attempts = db.Column(db.Integer, nullable=False, server_default='0', default=0)
```

- [ ] **Step 3: Migration lokal anwenden + verifizieren**

Run: `alembic upgrade head && python -c "from app import create_app; from models import JobMatch; app=create_app();
import sqlalchemy as sa;
print([c.name for c in JobMatch.__table__.columns if c.name=='eval_attempts'])"`
Expected: `['eval_attempts']`

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260612_1200_add_eval_attempts.py models.py
git commit -m "feat: JobMatch.eval_attempts Spalte für technische Retry-Logik"
```

---

## Task 2: `MatchResult.failed`-Flag

**Files:**
- Modify: `services/job_matching/claude_matcher.py:72-77`
- Modify: `services/job_matching/claude_utils.py:209-243` (`_parse_match_response`)
- Test: `tests/services/test_match_eval_retry.py`

- [ ] **Step 1: Failing test schreiben**

Create `tests/services/test_match_eval_retry.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from services.job_matching.claude_utils import _parse_match_response


def test_parse_invalid_json_sets_failed_flag():
    r = _parse_match_response("not json at all", 100, 20)
    assert r.failed is True
    assert r.score == 0


def test_parse_valid_score_zero_is_not_failed():
    r = _parse_match_response('{"score": 0, "reasoning": "kein Fit", "missing_skills": []}', 100, 20)
    assert r.failed is False
    assert r.score == 0
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: FAIL — `AttributeError: 'MatchResult' object has no attribute 'failed'`

- [ ] **Step 3: `failed`-Feld zur Dataclass hinzufügen**

In `services/job_matching/claude_matcher.py`, die Dataclass (Zeile 72-77) ändern zu:

```python
@dataclass
class MatchResult:
    score: float
    reasoning: str
    missing_skills: list
    tokens_in: int
    tokens_out: int
    failed: bool = False   # True = technischer Inhalts-Fehler (kein echter Score)
```

- [ ] **Step 4: `_parse_match_response` setzt `failed=True` bei beiden Fehler-Returns**

In `services/job_matching/claude_utils.py` in `_parse_match_response`: bei den beiden Fehler-`return MatchResult(...)` (ungültiges JSON ~L219 und Feld-Fehler ~L239) jeweils `failed=True,` ergänzen. Beispiel erster Block:

```python
        return MatchResult(
            score=0,
            reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
            missing_skills=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            failed=True,
        )
```

Und im zweiten Block (`"Bewertung fehlgeschlagen (Felder im JSON unerwartet)."`) ebenfalls `failed=True,`.

- [ ] **Step 5: Test laufen lassen (grün)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add services/job_matching/claude_matcher.py services/job_matching/claude_utils.py tests/services/test_match_eval_retry.py
git commit -m "feat: MatchResult.failed unterscheidet technischen Fehler von echtem Score 0"
```

---

## Task 3: Konstanten + Backoff/Failure-Helper

**Files:**
- Modify: `services/job_matching/claude_utils.py:33-39` (Konstanten) + neue Helper
- Test: `tests/services/test_match_eval_retry.py`

- [ ] **Step 1: Failing tests schreiben**

In `tests/services/test_match_eval_retry.py` anhängen:

```python
from services.job_matching.claude_utils import (
    _retry_backoff_hours, _result_is_content_failure,
    MATCH_MAX_EVAL_ATTEMPTS, MATCH_OLLAMA_FALLBACK_MODEL,
)
from services.job_matching.claude_matcher import MatchResult


def test_backoff_curve():
    assert _retry_backoff_hours(1) == 1
    assert _retry_backoff_hours(2) == 2
    assert _retry_backoff_hours(3) == 4
    assert _retry_backoff_hours(4) == 8
    assert _retry_backoff_hours(5) == 12   # gekappt


def test_content_failure_detection():
    assert _result_is_content_failure(_parse_match_response("xx", 1, 1)) is True
    ok = MatchResult(score=42, reasoning="ok", missing_skills=[], tokens_in=1, tokens_out=1)
    assert _result_is_content_failure(ok) is False


def test_constants_defaults():
    assert MATCH_MAX_EVAL_ATTEMPTS == 5
    assert MATCH_OLLAMA_FALLBACK_MODEL == "gemma4:12b"
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: FAIL — `ImportError: cannot import name '_retry_backoff_hours'`

- [ ] **Step 3: Konstanten + Helper implementieren**

In `services/job_matching/claude_utils.py` nach den Tick-Limits (nach Zeile 39, `AI_CONFIRM_BUDGET = 50`) einfügen:

```python
# Technische-Fehler-Retry (siehe docs/superpowers/specs/2026-06-12-technical-failure-reeval-design.md)
MATCH_MAX_EVAL_ATTEMPTS = int(os.getenv("MATCH_MAX_EVAL_ATTEMPTS", "5"))
MATCH_FALLBACK_ENABLED = os.getenv("MATCH_FALLBACK_ENABLED", "true").lower() in ("1", "true", "yes")
MATCH_OLLAMA_FALLBACK_MODEL = os.getenv("MATCH_OLLAMA_FALLBACK_MODEL", "gemma4:12b")
PERMANENT_FAIL_REASONING = "Technisch nicht bewertbar – bitte manuell prüfen."


def _retry_backoff_hours(attempts: int) -> int:
    """Mindest-Wartezeit bis zum nächsten Versuch: 1,2,4,8,12 (gekappt)."""
    return min(2 ** max(attempts - 1, 0), 12)


def _result_is_content_failure(result) -> bool:
    """True bei technischem Inhalts-Fehler (ungültiges JSON), nicht bei echtem Score 0."""
    if getattr(result, 'failed', False):
        return True
    # Lokaler Pfad (match_job_with_claude) hat kein failed-Flag — Heuristik:
    return (result.score == 0
            and (result.reasoning or '').strip().lower().startswith('bewertung fehlgeschlagen'))
```

- [ ] **Step 4: Test laufen lassen (grün)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/claude_utils.py tests/services/test_match_eval_retry.py
git commit -m "feat: Backoff-Kurve + Inhalts-Fehler-Erkennung + Match-Fallback-Konstanten"
```

---

## Task 4: `_run_match_via_service` — Ollama-Fallback-Kette + Failure-Handling

**Files:**
- Modify: `services/job_matching/claude_utils.py:280-391` (`_run_match_via_service`)
- Modify: `services/job_matching/claude_utils.py:459-472` (`_run_claude_match_for` Guard)
- Test: `tests/services/test_match_eval_retry.py`

- [ ] **Step 1: Failing tests schreiben (fake AI-Client)**

In `tests/services/test_match_eval_retry.py` anhängen:

```python
from types import SimpleNamespace
from unittest.mock import patch
import services.job_matching.claude_utils as cu


def _resp(text, via='opencode', fallback_used=False, model='deepseek-v4-flash-free'):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        via=via, fallback_used=fallback_used, model=model)


class _FakeClient:
    """chat() liefert je nach provider-Argument eine vorprogrammierte Antwort."""
    def __init__(self, by_provider):
        self.by_provider = by_provider          # dict provider -> callable() | response | Exception
        self.calls = []

    def chat(self, *, user_id, provider, model, messages, max_tokens, **kw):
        self.calls.append(provider)
        r = self.by_provider[provider]
        if isinstance(r, Exception):
            raise r
        return r() if callable(r) else r


def _make_match_and_user(db_session, user_factory):
    from models import RawJob, JobMatch
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    raw = RawJob(source='test', external_id='e1', title='IT Admin',
                 description='Linux, Netzwerk', location='Berlin', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0,
                 match_score=None, status='new', eval_attempts=0)
    db_session.add(m); db_session.flush()
    return u, raw, m


def test_ollama_fallback_succeeds_on_opencode_prose(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({
        'opencode': _resp('Hier meine Einschätzung in Prosa, kein JSON.'),
        'ollama': _resp('{"score": 73, "reasoning": "passt", "missing_skills": []}',
                        via='ollama', model='gemma4:12b'),
    })
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is True
    assert m.match_score == 73
    assert m.eval_attempts == 0
    assert 'ollama' in fake.calls


def test_content_failure_increments_attempts_when_ollama_also_prose(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({
        'opencode': _resp('Prosa'),
        'ollama': _resp('Auch Prosa', via='ollama'),
    })
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is False
    assert m.match_score is None          # KEIN Fake-Score 0
    assert m.eval_attempts == 1
    assert m.match_reasoning is None      # < 5 -> unauffällig


def test_infra_failure_leaves_attempts_untouched(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({'opencode': RuntimeError('connection refused')})
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is False
    assert m.match_score is None
    assert m.eval_attempts == 0           # Infra zählt NICHT zur Kappe


def test_fifth_content_failure_sets_permanent_marker(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    m.eval_attempts = 4
    fake = _FakeClient({'opencode': _resp('Prosa'), 'ollama': _resp('Prosa', via='ollama')})
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert m.eval_attempts == 5
    assert m.match_reasoning == cu.PERMANENT_FAIL_REASONING
    assert m.match_score is None
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_match_eval_retry.py -k "fallback or failure or permanent or infra" -v`
Expected: FAIL (Score 0 wird noch geschrieben, kein Ollama-Fallback-Call)

- [ ] **Step 3: `_run_match_via_service` neu implementieren**

In `services/job_matching/claude_utils.py` den Body von `_run_match_via_service` (Zeile 280-391) ersetzen durch:

```python
def _run_match_via_service(user: User, match: JobMatch, raw: RawJob, cv_summary: str,
                            provider: str, model: str) -> bool:
    """Match-Pfad via ai-provider-service (Production) mit Ollama-Fallback-Kette."""
    client = ai_provider_client.get_client()
    if MATCH_FALLBACK_ENABLED:
        # HTTP-Fehler des Free-Modells -> Service fällt automatisch auf Ollama.
        fallback_kwargs = {
            'fallback_provider': ProviderConfig.OLLAMA,
            'fallback_model': MATCH_OLLAMA_FALLBACK_MODEL,
        }
    else:
        fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='match')

    from services.job_matching.feedback_context import get_user_feedback_context
    feedback_context = get_user_feedback_context(user.id)

    def call_match(description: str, *, force_provider=None, force_model=None, use_fallback=True):
        user_msg = _build_user_message(cv_summary, {
            "title": raw.title, "description": description, "location": raw.location,
        }, feedback_context=feedback_context)
        eff_model = force_model or model
        kwargs = dict(fallback_kwargs) if use_fallback else {}
        return client.chat(
            user_id=user.id, provider=force_provider or provider, model=eff_model,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE_MATCH},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=_max_tokens_for(eff_model),
            **kwargs,
        )

    # 1) Primär-Call (+ Service-seitiger Ollama-Fallback bei HTTP-Fehler)
    try:
        response = call_match(raw.description)
    except AIProviderQueuedError:
        raise
    except Exception as e:
        logger.warning(
            "service-match infra-fail match=%s user=%s provider=%s: %s: %s",
            match.id, user.id, provider, type(e).__name__, e,
        )
        return False  # Infra: kein Score, eval_attempts unberührt

    text = _strip_thinking_block(
        (response.content[0].text if response.content else '').strip()
    )
    match._last_via = response.via
    match._last_fallback_used = response.fallback_used

    # 2) Summarize-Retry mit gleichem Primär-Modell
    if not _extract_first_json_object(text):
        logger.info(f'match={match.id} unparseable, summarize-retry')
        try:
            sum_provider, sum_model = user.get_model_for('cv_summarize')
            short_desc = _summarize_description(
                client, user.id, sum_provider or provider, sum_model or model,
                raw.description or '', fallback_kwargs=fallback_kwargs,
            )
            if short_desc and short_desc != raw.description:
                response2 = call_match(short_desc)
                text2 = _strip_thinking_block(
                    (response2.content[0].text if response2.content else '').strip()
                )
                if _extract_first_json_object(text2):
                    response.usage.input_tokens += response2.usage.input_tokens
                    response.usage.output_tokens += response2.usage.output_tokens
                    text = text2
        except AIProviderQueuedError:
            raise
        except Exception as e:
            logger.warning(f'summarize-retry failed for match={match.id}: {e}')

    # 3) Inhalts-Fallback auf Ollama (eigener Call), falls noch kein JSON & nicht schon Ollama
    if (not _extract_first_json_object(text)
            and MATCH_FALLBACK_ENABLED
            and response.via != ProviderConfig.OLLAMA):
        logger.info(f'match={match.id} content-fallback -> ollama {MATCH_OLLAMA_FALLBACK_MODEL}')
        try:
            resp_o = call_match(
                raw.description, force_provider=ProviderConfig.OLLAMA,
                force_model=MATCH_OLLAMA_FALLBACK_MODEL, use_fallback=False,
            )
            text_o = _strip_thinking_block(
                (resp_o.content[0].text if resp_o.content else '').strip()
            )
            if _extract_first_json_object(text_o):
                text = text_o
                response = resp_o
                match._last_via = resp_o.via
                match._last_fallback_used = True
        except AIProviderQueuedError:
            raise
        except Exception as e:
            logger.warning(
                "ollama content-fallback infra-fail match=%s: %s: %s",
                match.id, type(e).__name__, e,
            )
            return False  # Ollama nicht erreichbar = Infra: kein Score, Kappe unberührt

    # 4) Finale Auswertung
    result = _parse_match_response(
        text, response.usage.input_tokens, response.usage.output_tokens,
    )

    # 5) Inhalts-Fehler (auch Ollama lieferte kein JSON)
    if _result_is_content_failure(result):
        match.eval_attempts = (match.eval_attempts or 0) + 1
        match.match_score = None
        match.missing_skills = []
        match.match_reasoning = (
            PERMANENT_FAIL_REASONING
            if match.eval_attempts >= MATCH_MAX_EVAL_ATTEMPTS else None
        )
        logger.info(f'match={match.id} content-failure, eval_attempts={match.eval_attempts}')
        return False

    # 6) Erfolg
    match.match_score = result.score
    match.match_reasoning = result.reasoning
    match.missing_skills = result.missing_skills
    match.eval_attempts = 0
    raw.crawl_status = 'matched'

    suspicious_reasons: list[str] = []
    desc_for_check = (raw.description or '') + ' ' + (raw.title or '')
    injection_hits = detect_injection_patterns(desc_for_check)
    if injection_hits:
        suspicious_reasons.extend(f'input:{h}' for h in injection_hits)
    if has_suspicious_score_jump(match.prefilter_score, result.score):
        suspicious_reasons.append('score_jump')
    match.suspicious_reasons = ','.join(suspicious_reasons) if suspicious_reasons else None
    if suspicious_reasons:
        logger.info(
            f'match={match.id} flagged suspicious: {suspicious_reasons} '
            f'(score={result.score}, prefilter={match.prefilter_score})'
        )

    if response.via in ('ollama', 'mammouth', 'custom'):
        cost_usd = 0.0
        key_owner = 'user' if response.via == 'ollama' else 'custom_endpoint'
    else:
        logged_model_for_cost = response.model if (response.fallback_used and response.model) else model
        cost_usd = cost_tracker.estimate_cost_usd(logged_model_for_cost, result.tokens_in, result.tokens_out)
        key_owner = 'server'

    logged_model = response.model if (response.fallback_used and response.model) else model
    cost_tracker.record_call(
        user_id=user.id, endpoint='/api/jobs/match',
        model=logged_model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost_usd=cost_usd,
        key_owner=key_owner,
    )
    return True
```

- [ ] **Step 4: `_run_claude_match_for` Cap-Guard ergänzen**

In `services/job_matching/claude_utils.py` in `_run_claude_match_for` (ab Zeile 459) als allererste Bedingung im Funktionskörper (vor `if match.match_score is not None ...`) einfügen:

```python
    if (match.eval_attempts or 0) >= MATCH_MAX_EVAL_ATTEMPTS:
        return False  # permanent technisch fehlgeschlagen — nicht weiter auto-bewerten
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS (alle, inkl. fallback/failure/infra/permanent)

- [ ] **Step 6: Commit**

```bash
git add services/job_matching/claude_utils.py tests/services/test_match_eval_retry.py
git commit -m "feat: Ollama-Fallback-Kette + technische Fehlerklassifizierung im Match-Pfad"
```

---

## Task 5: Lokaler Pfad (`_run_match_via_local_factory`) — kein Fake-Score 0

**Files:**
- Modify: `services/job_matching/claude_utils.py:394-446`
- Test: `tests/services/test_match_eval_retry.py`

- [ ] **Step 1: Failing test schreiben**

In `tests/services/test_match_eval_retry.py` anhängen:

```python
def test_local_factory_content_failure_no_fake_score(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    failed = MatchResult(score=0, reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                         missing_skills=[], tokens_in=1, tokens_out=1, failed=True)
    with patch.object(cu, 'match_job_with_claude', return_value=failed), \
         patch.object(cu.ai_provider_client, 'is_enabled', return_value=False), \
         patch.object(cu.ProviderFactory, 'get_client', return_value=object()):
        ok = cu._run_match_via_local_factory(u, m, raw, 'CV', 'ollama', 'gemma4:12b')
    assert ok is False
    assert m.match_score is None
    assert m.eval_attempts == 1
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_match_eval_retry.py::test_local_factory_content_failure_no_fake_score -v`
Expected: FAIL — `match_score` ist 0 statt None

- [ ] **Step 3: Failure-Behandlung im lokalen Pfad einbauen**

In `services/job_matching/claude_utils.py` nach dem `try/except` von `_run_match_via_local_factory` (also direkt vor `match.match_score = result.score`, ~Zeile 426) einfügen:

```python
    if _result_is_content_failure(result):
        match.eval_attempts = (match.eval_attempts or 0) + 1
        match.match_score = None
        match.missing_skills = []
        match.match_reasoning = (
            PERMANENT_FAIL_REASONING
            if match.eval_attempts >= MATCH_MAX_EVAL_ATTEMPTS else None
        )
        return False
```

Und im Erfolgsfall danach `match.eval_attempts = 0` ergänzen (direkt nach `match.missing_skills = result.missing_skills`, ~Zeile 428).

- [ ] **Step 4: Test laufen lassen (grün)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS (alle)

- [ ] **Step 5: Commit**

```bash
git add services/job_matching/claude_utils.py tests/services/test_match_eval_retry.py
git commit -m "feat: lokaler Match-Pfad schreibt keinen Fake-Score 0 mehr"
```

---

## Task 6: Retry-Zweig in `cron_claude_match`

**Files:**
- Modify: `services/tasks/handlers/cron_claude_match.py`
- Test: `tests/services/test_match_eval_retry.py`

- [ ] **Step 1: Failing test schreiben**

In `tests/services/test_match_eval_retry.py` anhängen:

```python
from datetime import datetime, timedelta


def test_retry_branch_selects_low_prefilter_failed_match(app, db_session, user_factory):
    from models import RawJob, JobMatch
    from services.tasks.handlers.cron_claude_match import handle_cron_claude_match
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    raw = RawJob(source='t', external_id='r9', title='IT Admin', description='Linux', url='http://x')
    db_session.add(raw); db_session.flush()
    old = datetime.utcnow() - timedelta(hours=5)
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0, match_score=None,
                 status='new', eval_attempts=1, updated_at=old)
    db_session.add(m); db_session.commit()

    called = {}
    def fake_run(client, user, match):
        called['id'] = match.id
        match.match_score = 80.0
        match.eval_attempts = 0
        return True

    with patch('services.job_matching.claude_utils._run_claude_match_for', side_effect=fake_run), \
         patch('services.ai_provider_client.is_enabled', return_value=True):
        handle_cron_claude_match({})
    assert called.get('id') == m.id     # niedriger prefilter, aber wegen eval_attempts gezogen
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_match_eval_retry.py::test_retry_branch_selects_low_prefilter_failed_match -v`
Expected: FAIL — Match wird nicht gezogen (prefilter 20 < 50)

- [ ] **Step 3: Retry-Zweig implementieren**

In `services/tasks/handlers/cron_claude_match.py`:

Imports oben (nach Zeile 7) ergänzen:

```python
from datetime import datetime, timedelta
from sqlalchemy import or_
```

Innerhalb von Step 25-28 Import-Block zusätzlich `MATCH_MAX_EVAL_ATTEMPTS, _retry_backoff_hours` importieren:

```python
    from services.job_matching.claude_utils import (
        _run_claude_match_for, _get_anthropic_client,
        AUTO_CLAUDE_THRESHOLD, HARD_TIME_LIMIT_SEC,
        MATCH_MAX_EVAL_ATTEMPTS, _retry_backoff_hours,
    )
```

Die User-Auswahl (Zeile 46-51) erweitern, damit auch User mit reinen Retry-Kandidaten erfasst werden:

```python
    users_with_pending = (db.session.query(User)
                          .join(JobMatch, JobMatch.user_id == User.id)
                          .filter(JobMatch.match_score.is_(None),
                                  JobMatch.status.in_(['new', 'seen']),
                                  JobMatch.eval_attempts < MATCH_MAX_EVAL_ATTEMPTS,
                                  or_(JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
                                      JobMatch.eval_attempts >= 1))
                          .distinct().all())
```

Den `candidates`-Block (Zeile 65-71) ersetzen durch Haupt- + Retry-Zweig:

```python
        now = datetime.utcnow()
        # Haupt-Zweig: neue, gut vorgefilterte Matches (prefilter >= 50)
        candidates = (JobMatch.query
                      .filter(JobMatch.user_id == user.id,
                              JobMatch.match_score.is_(None),
                              JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
                              JobMatch.status == 'new',
                              JobMatch.eval_attempts < MATCH_MAX_EVAL_ATTEMPTS)
                      .order_by(JobMatch.prefilter_score.desc())
                      .limit(user.job_claude_budget_per_tick).all())

        # Retry-Zweig: technische Fehlschläge mit niedrigem/keinem prefilter, mit Backoff
        retry_raw = (JobMatch.query
                     .filter(JobMatch.user_id == user.id,
                             JobMatch.match_score.is_(None),
                             JobMatch.eval_attempts.between(1, MATCH_MAX_EVAL_ATTEMPTS - 1),
                             JobMatch.status.in_(['new', 'seen']),
                             or_(JobMatch.prefilter_score < AUTO_CLAUDE_THRESHOLD,
                                 JobMatch.prefilter_score.is_(None)),
                             JobMatch.updated_at < now - timedelta(hours=1))
                     .order_by(JobMatch.eval_attempts.asc())
                     .all())
        retry = [m for m in retry_raw
                 if (m.updated_at or now) < now - timedelta(hours=_retry_backoff_hours(m.eval_attempts))]
        candidates = candidates + retry[:user.job_claude_budget_per_tick]
```

- [ ] **Step 4: Test laufen lassen (grün)**

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS (alle)

- [ ] **Step 5: Regression — kein never-attempted Low-Prefilter-Match wird gezogen**

In `tests/services/test_match_eval_retry.py` anhängen:

```python
def test_retry_branch_ignores_fresh_low_prefilter(app, db_session, user_factory):
    from models import RawJob, JobMatch
    from services.tasks.handlers.cron_claude_match import handle_cron_claude_match
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    raw = RawJob(source='t', external_id='r10', title='X', description='Y', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0, match_score=None,
                 status='new', eval_attempts=0, updated_at=datetime.utcnow() - timedelta(hours=5))
    db_session.add(m); db_session.commit()
    called = {}
    with patch('services.job_matching.claude_utils._run_claude_match_for',
               side_effect=lambda c, u, mm: called.setdefault('id', mm.id) or True), \
         patch('services.ai_provider_client.is_enabled', return_value=True):
        handle_cron_claude_match({})
    assert 'id' not in called   # eval_attempts=0 + prefilter<50 -> NICHT gezogen
```

Run: `pytest tests/services/test_match_eval_retry.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/tasks/handlers/cron_claude_match.py tests/services/test_match_eval_retry.py
git commit -m "feat: Retry-Zweig zieht technische Fehlschläge unabhängig vom prefilter-Gate"
```

---

## Task 7: Einmal-Cleanup-Script für Altbestand

**Files:**
- Create: `scripts/reeval_technical_failures.py`
- Test: `tests/services/test_reeval_script.py`

- [ ] **Step 1: Failing test schreiben**

Create `tests/services/test_reeval_script.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from scripts.reeval_technical_failures import select_candidates, reset_match


def test_selects_dismissed_failure_without_human_judgment(app, db_session, user_factory):
    from models import RawJob, JobMatch
    u = user_factory()
    raw = RawJob(source='t', external_id='a', title='X', description='Y', url='http://x')
    db_session.add(raw); db_session.flush()
    fail = JobMatch(raw_job_id=raw.id, user_id=u.id, status='dismissed', match_score=0.0,
                    match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                    feedback_reasons=None)
    human = JobMatch(raw_job_id=raw.id, user_id=u.id, status='dismissed', match_score=0.0,
                     match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                     feedback_reasons='["wrong_seniority"]')
    db_session.add_all([fail, human]); db_session.commit()
    ids = {m.id for m in select_candidates()}
    assert fail.id in ids
    assert human.id not in ids        # menschliches Urteil respektiert


def test_reset_match_makes_retriable(app, db_session, user_factory):
    from models import RawJob, JobMatch
    u = user_factory()
    raw = RawJob(source='t', external_id='b', title='X', description='Y', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, status='dismissed', match_score=0.0,
                 match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                 notified_at=None, eval_attempts=0)
    db_session.add(m); db_session.commit()
    reset_match(m)
    db_session.commit()
    assert m.status == 'new'
    assert m.match_score is None
    assert m.match_reasoning is None
    assert m.eval_attempts == 1       # Retry-Zweig greift
```

- [ ] **Step 2: Test laufen lassen (rot)**

Run: `pytest tests/services/test_reeval_script.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.reeval_technical_failures'`

- [ ] **Step 3: Script implementieren**

Create `scripts/reeval_technical_failures.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Einmal-Cleanup: technische Fehlbewertungen (ohne menschliches Urteil) zur Neubewertung zurückstellen.

Usage:
    python scripts/reeval_technical_failures.py            # Dry-run
    python scripts/reeval_technical_failures.py --apply    # schreibt (mit JSON-Backup)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from database import db
from models import JobMatch


def select_candidates():
    """Verworfene/neue Matches mit technischer Fehlbegründung, ohne menschliches feedback_reasons."""
    return (JobMatch.query
            .filter(JobMatch.match_reasoning.like('Bewertung fehlgeschlagen%'),
                    JobMatch.feedback_reasons.is_(None))
            .all())


def reset_match(m: JobMatch) -> None:
    """Stellt einen Match auf retriable: status='new', Score/Reasoning geleert, eval_attempts=1."""
    if m.status == 'dismissed':
        m.status = 'new'
    m.match_score = None
    m.match_reasoning = None
    m.missing_skills = []
    m.notified_at = None
    m.eval_attempts = 1


def main() -> None:
    apply = '--apply' in sys.argv
    from app import create_app
    app = create_app()
    with app.app_context():
        rows = select_candidates()
        print(f"Technische Fehlschläge ohne menschliches Urteil: {len(rows)}")
        for m in rows:
            print(f"  match {m.id}: status={m.status} score={m.match_score} "
                  f"feedback_text={m.feedback_text!r}")
        if not apply:
            print("\n(DRY-RUN — nichts geändert. Mit --apply ausführen.)")
            return
        backup = [{'id': m.id, 'status': m.status, 'match_score': m.match_score,
                   'match_reasoning': m.match_reasoning, 'feedback_text': m.feedback_text,
                   'eval_attempts': m.eval_attempts} for m in rows]
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        path = f"/tmp/reeval_backup_{ts}.json"
        with open(path, 'w') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
        for m in rows:
            reset_match(m)
        db.session.commit()
        print(f"\nAPPLIED: {len(rows)} Matches zurückgestellt. Backup: {path}")


if __name__ == '__main__':
    main()
```

Sicherstellen, dass `scripts/__init__.py` existiert (für den Test-Import); falls nicht: `touch scripts/__init__.py`.

- [ ] **Step 4: Test laufen lassen (grün)**

Run: `pytest tests/services/test_reeval_script.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/reeval_technical_failures.py tests/services/test_reeval_script.py
git status --short scripts/__init__.py >/dev/null 2>&1 && git add scripts/__init__.py
git commit -m "feat: Einmal-Cleanup-Script für technische Fehlbewertungen im Altbestand"
```

---

## Task 8: Frontend-Verifikation (kein Code-Change erwartet)

**Files:**
- Verify: `index.html:4847,4908-4910`

- [ ] **Step 1: Render-Pfad prüfen**

`index.html:4847` setzt `hasClaudeScore = m.match_score != null`. Bei `match_score = null` (permanent technisch fehlgeschlagen) wird der Match als „⚪ unbewertet" gerendert, und `index.html:4908-4910` zeigt `match_reasoning` (= `PERMANENT_FAIL_REASONING`) darunter an. Der User kann manuell „bewerten" erneut auslösen (`index.html:5340-5367`).

Bestätigen via Lesen, dass kein Code-Change nötig ist:
Run: `grep -n "hasClaudeScore\|match_reasoning ?" index.html | head`
Expected: Zeilen 4847 + 4908 vorhanden → Marker wird automatisch angezeigt.

- [ ] **Step 2: (Optional, nur falls gewünscht) deutlicher Badge** — übersprungen (YAGNI). Kein Commit.

---

## Task 9: Deploy + Daten-Reconciliation + Smoke (Oracle VM)

**Kontext:** Prod-DB liegt im Container `bewerbungen-app` unter `/app/data/bewerbungstracker.db` auf der **Oracle VM** (`ssh oracle-vm`, docker). 8 Matches wurden bereits manuell auf `status='new'` zurückgesetzt (ids: 2451,2453,2473,2502,2554,2721,3057,3060) — diese brauchen `eval_attempts=1`, da ihre Reasoning bereits geleert ist und das Cleanup-Script sie nicht mehr findet.

- [ ] **Step 1: Branch mergen + deployen** (nach Merge zu `master`)

Der Git-Deploy auf der VM wendet neue Alembic-Migrationen automatisch an (`deploy/git-deploy/post-receive`). Falls Container-Deploy: Image neu bauen + `alembic upgrade head` im `bewerbungen-app`-Container ausführen.

Run (Container-Variante):
```bash
ssh oracle-vm "docker exec bewerbungen-app alembic upgrade head"
```
Expected: `Running upgrade b0c1d2e3f4a5 -> c1d2e3f4a5b6`

- [ ] **Step 2: Spalte verifizieren**

```bash
ssh oracle-vm "docker exec bewerbungen-app python3 -c \"import sqlite3; c=sqlite3.connect('/app/data/bewerbungstracker.db'); print([r[1] for r in c.execute('pragma table_info(job_matches)') if r[1]=='eval_attempts'])\""
```
Expected: `['eval_attempts']`

- [ ] **Step 3: Cleanup-Script Dry-run, dann Apply**

```bash
ssh oracle-vm "docker exec bewerbungen-app python3 scripts/reeval_technical_failures.py"
ssh oracle-vm "docker exec bewerbungen-app python3 scripts/reeval_technical_failures.py --apply"
```
Expected: zeigt verbleibende Altfälle (z.B. die 1 dismissed mit feedback_reasons wird NICHT erfasst), `--apply` mit Backup-Pfad.

- [ ] **Step 4: Die 8 bereits zurückgesetzten Matches retriable machen**

```bash
ssh oracle-vm "docker exec bewerbungen-app python3 -c \"
import sqlite3; c=sqlite3.connect('/app/data/bewerbungstracker.db', timeout=15)
c.execute('PRAGMA busy_timeout=15000')
ids=[2451,2453,2473,2502,2554,2721,3057,3060]
ph=','.join('?'*len(ids))
n=c.execute(f'update job_matches set eval_attempts=1 where id in ({ph}) and match_score is null and status=\\\"new\\\" and eval_attempts=0', ids).rowcount
c.commit(); print('eval_attempts=1 gesetzt für', n, 'Matches')\""
```
Expected: `eval_attempts=1 gesetzt für <=8 Matches`

- [ ] **Step 5: Smoke — claude-match triggern, Neubewertung prüfen**

Nur sinnvoll wenn ein Provider gesund ist (opencode oder Ollama). Trigger + nach ~30s prüfen:
```bash
ssh oracle-vm "docker exec bewerbungen-cron sh -c 'curl -fsS -X POST -H \"X-Cron-Token: \${JOB_CRON_TOKEN}\" \${APP_INTERNAL_URL}/api/jobs/claude-match'"
ssh oracle-vm "sleep 30; docker exec bewerbungen-app python3 -c \"
import sqlite3; c=sqlite3.connect('/app/data/bewerbungstracker.db'); c.row_factory=sqlite3.Row
for r in c.execute('select id,status,match_score,eval_attempts from job_matches where id in (3057,3060) order by id'):
    print(dict(r))\""
```
Expected: mind. ein Match erhält einen echten `match_score` (oder `eval_attempts` erhöht sich bei anhaltendem Free-Modell-Problem, ohne Fake-Score 0).

- [ ] **Step 6: AGENTS.md §7 Handoff-Eintrag + Verifikations-Statement**

Neuen datierten Eintrag in `CLAUDE.md` §7 mit: Commits, Migration `c1d2e3f4a5b6`, Env-Vars (`MATCH_FALLBACK_ENABLED`, `MATCH_OLLAMA_FALLBACK_MODEL`), Cleanup-Ergebnis, ob mit echten Providern oder Mocks getestet (CLAUDE.md §4).

```bash
git add CLAUDE.md && git commit -m "doc: Handoff — technische Fehlbewertungs-Neubewertung deployed"
```

---

## Self-Review

**Spec-Coverage:**
- Ziel 1 (kein Fake-Score 0) → Task 4 Step 3 (Punkt 5), Task 5. ✅
- Ziel 2 (Ollama-Fallback HTTP + Inhalt) → Task 4 Step 3 (Punkte 1+3). ✅
- Ziel 3 (5× Backoff, dann Marker) → Task 3 (Backoff), Task 4 (Marker), Task 6 (Backoff-Auswahl). ✅
- Ziel 4 (Infra verbraucht Kappe nicht) → Task 4 Step 3 (Punkte 1+3 return False ohne Inkrement), Test `test_infra_failure_leaves_attempts_untouched`. ✅
- Ziel 5 (Altbestand) → Task 7 + Task 9 Steps 3-4. ✅
- Notify unverändert (3.7) → kein Code-Change, NULL-Score filtert bestehend. ✅
- Frontend (3.8) → Task 8 (Verifikation, kein Change). ✅
- Konfig-Env (4) → Task 3 Step 3. ✅
- Tests (6) → Tasks 2,3,4,5,6,7. ✅

**Placeholder-Scan:** keine TBD/TODO; alle Code-Steps mit vollständigem Code. ✅

**Typ-Konsistenz:** `eval_attempts` (Int), `MatchResult.failed` (bool), `_result_is_content_failure`/`_retry_backoff_hours`/`PERMANENT_FAIL_REASONING`/`MATCH_MAX_EVAL_ATTEMPTS`/`MATCH_OLLAMA_FALLBACK_MODEL` durchgängig gleich benannt in Tasks 3,4,5,6,7. ✅
