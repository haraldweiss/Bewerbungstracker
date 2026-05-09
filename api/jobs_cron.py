# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cron-Endpoints für Job-Discovery Pipeline (Token-geschützt)."""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify

from database import db
from models import User, JobSource, RawJob, JobMatch, ApiCall
from services.cron_auth import require_cron_token
from services.job_sources import get_adapter
from services.job_matching.cv_tokenizer import tokenize_cv
from services.job_matching.prefilter import score_job, PrefilterContext
from services.job_matching.claude_matcher import (
    match_job_with_claude, _build_prompt, MatchResult,
    SYSTEM_MESSAGE_MATCH, _build_user_message,
)
from services.job_matching.injection_detector import (
    detect_injection_patterns, has_suspicious_score_jump,
)
from services.provider_service import ProviderFactory, ProviderConfig
from services.job_matching.notifier import send_match_notification
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from services import ai_provider_client
from services.ai_provider_client import AIProviderQueuedError

logger = logging.getLogger(__name__)


jobs_cron_bp = Blueprint('jobs_cron', __name__, url_prefix='/api/jobs')

# Tick-Limits
MAX_NEW_JOBS_PER_TICK = 50
MAX_PREFILTER_PER_TICK = 100
# Score-Threshold ab dem ein Job auto-dismissed wird (NICHT mehr in 'new').
# Sehr niedrig gehalten (5), damit der User mehr Vorschläge sieht und selbst
# entscheiden kann — die ausführliche Claude-Bewertung läuft on-demand
# (POST /matches/<id>/score) oder beim Auto-Cron für AUTO_CLAUDE_THRESHOLD.
# Vorher: 15 — führte zu 600+ Auto-Dismisses bei breiten Adzuna-Suchen.
PREFILTER_DISMISS_THRESHOLD = 5
# Auto-Cron bewertet nur prefilter_score >= AUTO_CLAUDE_THRESHOLD.
# User-getriggerte Bewertungen (single, bulk, import) ignorieren diesen Threshold.
AUTO_CLAUDE_THRESHOLD = 50
MAX_NOTIFICATIONS_PER_TICK = 20
HARD_TIME_LIMIT_SEC = 25
AUTO_DISABLE_FAILURE_COUNT = 5
ARCHIVE_AFTER_DAYS = 60

DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "claude-haiku-4-5-20251001")
COST_USD_PER_1M_TOKENS_IN = 0.80
COST_USD_PER_1M_TOKENS_OUT = 4.00


def _get_anthropic_client():
    """Phase A: einziger Server-Key. Phase B ersetzt dies durch Factory."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic  # lazy import — nicht im venv bei Tests
    return Anthropic(api_key=api_key)


def _estimate_cost_cents(tokens_in: int, tokens_out: int) -> int:
    """USD-Kosten in Cents — KEIN Min-Floor.

    Vorher: max(1, round(...)) — bei Calls mit ~2500 in / 250 out tokens
    sind die echten Kosten ~0.2¢, das wurde fälschlich auf 1¢ aufgerundet.
    Bei 50 Calls/Tag → fälschlich 50¢ statt der realen ~10¢ → Tagesbudget
    sprang in HTTP 402 obwohl noch viel Luft war.
    """
    usd = (tokens_in / 1_000_000 * COST_USD_PER_1M_TOKENS_IN
           + tokens_out / 1_000_000 * COST_USD_PER_1M_TOKENS_OUT)
    return max(0, round(usd * 100))


def _user_today_cost_cents(user_id: str) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (db.session.query(db.func.sum(ApiCall.cost))
            .filter(ApiCall.user_id == user_id, ApiCall.timestamp >= today_start)
            .scalar()) or 0
    return int(round(rows * 100))


def _build_cv_summary(cv_data_json: str) -> str:
    """CV-Zusammenfassung für Claude-Prompt.

    Akzeptiert beide cv_data_json-Schemas (analog zum cv_tokenizer):
    1. Strukturiert: ``{"cv": {summary, skills, experiences}}``
    2. Text-Blob: ``{"cvData": {"text": "<volltext>"}}`` aus PDF/DOCX-Upload

    Bei Text-Blob wird der CV-Volltext direkt durchgereicht (auf 3000 Zeichen
    gekappt im Prompt-Builder weiter unten).
    """
    if not cv_data_json:
        return ""
    data = json.loads(cv_data_json)
    parts = []

    # Format 1: strukturiert
    cv = data.get("cv") or {}
    if isinstance(cv, dict):
        if cv.get("summary"):
            parts.append(f"Zusammenfassung: {cv['summary']}")
        if cv.get("skills"):
            parts.append(f"Skills: {', '.join(cv['skills'])}")
        if cv.get("experiences"):
            titles = [e.get("title", "") for e in cv["experiences"][:5]]
            parts.append(f"Letzte Positionen: {' | '.join(titles)}")

    # Format 2: Text-Blob (PDF/DOCX-Upload)
    blob = data.get("cvData") or {}
    if isinstance(blob, dict):
        text = blob.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(f"CV-Volltext:\n{text}")

    return "\n".join(parts)


def _select_due_source() -> JobSource | None:
    candidates = JobSource.query.filter(JobSource.enabled == True).all()
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
        raw.raw_payload = {
            k: v for k, v in fj.raw.items()
            if isinstance(v, (str, int, float, bool, type(None), list, dict))
        }
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


@jobs_cron_bp.post('/prefilter')
@require_cron_token
def prefilter():
    started = time.time()
    pending = (JobMatch.query
               .filter(JobMatch.prefilter_score.is_(None), JobMatch.status == 'new')
               .limit(MAX_PREFILTER_PER_TICK).all())

    cv_cache: dict = {}
    ctx_cache: dict = {}
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

    db.session.commit()
    return jsonify({"scored": scored, "dismissed": dismissed,
                    "duration_sec": round(time.time() - started, 2)}), 200


def _extract_first_json_object(text: str) -> dict | None:
    """Extrahiert das erste balanciert geschlossene JSON-Objekt aus dem Text.

    Robust gegen umgebenden Erklärungstext und Code-Fences (```json ... ```),
    die kleine Modelle wie Mistral/Llama oft erzeugen, obwohl der Prompt
    explizit nur JSON verlangt.
    """
    if not text:
        return None

    # Code-Fences entfernen
    cleaned = text.replace('```json', '').replace('```JSON', '').replace('```', '')

    start = cleaned.find('{')
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                snippet = cleaned[start:i + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    return None
    return None


def _validate_match_schema(data: dict) -> tuple[float, str, list, list]:
    """Strikte Schema-Validierung. Schützt gegen kompromittierte Provider-Antworten
    (z.B. score=999, reasoning=10000-Zeichen, missing_skills=[100 Einträge mit XSS]).

    Returns: (score, reasoning, missing_skills, validation_warnings)
    """
    warnings: list[str] = []

    # Score: muss 0..100 sein
    raw_score = data.get("score", 0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
        warnings.append('score_not_number')
    if score < 0 or score > 100:
        warnings.append(f'score_out_of_range:{score}')
        score = max(0.0, min(100.0, score))

    # Reasoning: max 500 Zeichen
    reasoning = str(data.get("reasoning", "") or "")
    if len(reasoning) > 500:
        reasoning = reasoning[:500].rstrip() + "…"
        warnings.append('reasoning_truncated')

    # missing_skills: Liste, max 10 Einträge à max 80 Zeichen, kein Code/HTML
    skills_raw = data.get("missing_skills")
    if not isinstance(skills_raw, list):
        skills_raw = []
        if data.get("missing_skills") is not None:
            warnings.append('missing_skills_not_list')
    skills: list[str] = []
    for s in skills_raw[:10]:
        s_str = str(s)[:80].strip()
        # Tags und Backticks rausschneiden
        s_str = s_str.replace('<', '').replace('>', '').replace('`', '')
        if s_str:
            skills.append(s_str)
    if len(skills_raw) > 10:
        warnings.append('missing_skills_truncated')

    return score, reasoning, skills, warnings


def _parse_match_response(text: str, tokens_in: int, tokens_out: int) -> MatchResult:
    """Parst die JSON-Antwort vom Provider in ein MatchResult.

    Toleriert Freitext um das JSON, Code-Fences und mehrzeilige Antworten.
    Validiert das Schema strikt (Defense-in-Depth gegen Output-Manipulation).
    """
    data = _extract_first_json_object(text or '')
    if data is None:
        # Snippet ins Log damit man später debuggen kann was der Provider lieferte.
        # 2000 chars: typische CV-Match-Antworten sind 300-800 chars,
        # Reasoning-Modelle mit <think> kommen auf 2000+ chars
        snippet = (text or '')[:2000].replace('\n', ' ⏎ ')
        logger.warning(
            f'match-response parse failed (text-len={len(text or "")}, '
            f'first-2000-chars): {snippet!r}'
        )
        return MatchResult(
            score=0,
            reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
            missing_skills=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    try:
        score, reasoning, skills, schema_warnings = _validate_match_schema(data)
        if schema_warnings:
            logger.info(f'match-response schema warnings: {schema_warnings}')
        return MatchResult(
            score=score,
            reasoning=reasoning,
            missing_skills=skills,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception as e:
        logger.warning(f'match-response field-extraction failed: {e}; data={data!r}')
        return MatchResult(
            score=0,
            reasoning="Bewertung fehlgeschlagen (Felder im JSON unerwartet).",
            missing_skills=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


_SUMMARIZE_PROMPT = """Fasse die folgende Stellenausschreibung in maximal 1500 Zeichen zusammen.
Wichtig: Behalte alle technischen Anforderungen, Skills, Aufgaben und Qualifikationen bei.
Lass Marketing-Sprache, Boilerplate, Benefits-Listen und allgemeine Firmenbeschreibungen weg.
Antworte AUSSCHLIESSLICH mit der Zusammenfassung, kein Drumherum, keine Anrede.

STELLENAUSSCHREIBUNG:
{description}
"""


# Modelle mit eingebautem Reasoning-Block (<think>…</think>) brauchen viel mehr
# Output-Tokens, sonst wird der Antwortteil abgeschnitten — done_reason=length.
_REASONING_MODEL_PATTERNS = (
    'qwen3', 'qwen-3', 'deepseek-r1', 'deepseek-reasoner',
    'o1-', 'o3-', 'reasoner', 'reasoning',
)


def _is_reasoning_model(model: str) -> bool:
    if not model:
        return False
    m = model.lower()
    return any(p in m for p in _REASONING_MODEL_PATTERNS)


def _max_tokens_for(model: str, base: int = 2000) -> int:
    """Token-Budget pro Match-Call.

    base=2000 reicht für ein vollständiges JSON mit langem Reasoning (Default).
    Empirisch zeigte sich: 800 ist zu wenig — viele Modelle (Gemma4, Llama3.x)
    schreiben gern 'Hier ist meine Bewertung: …' davor + längere Erklärungen,
    JSON wird mid-output abgeschnitten.

    Reasoning-Modelle (Qwen3, DeepSeek-R1, o1, …) bekommen 4× Budget für ihren
    <think>-Block. Das ist `max_tokens` als Obergrenze — bei normalen Calls
    läuft das Modell nicht aus, also keine Mehrkosten.
    """
    return base * 4 if _is_reasoning_model(model) else base


def _strip_thinking_block(text: str) -> str:
    """Entfernt <think>...</think>-Blöcke (Qwen3, DeepSeek-R1, etc.).

    Auch tolerant gegen verwaiste öffnende Tags: alles vor dem letzten
    </think> wird verworfen, dahinter liegt das eigentliche Antwort-JSON.
    """
    if not text:
        return text
    if '</think>' in text:
        text = text.rsplit('</think>', 1)[1].lstrip()
    return text


def _summarize_description(client, user_id: str, provider: str, model: str,
                            description: str, target_chars: int = 1500) -> str:
    """Fasst eine zu lange Job-Description via KI zusammen.

    Wird als Fallback aufgerufen wenn der erste Match-Call leer/unparsbar war
    (typischerweise wenn das Modell mit dem langen Prompt nicht klarkommt).
    Bei Fehler im Summarize-Call: Hard-Truncate als letzter Fallback.
    """
    if not description or len(description) <= target_chars:
        return description or ''

    summary_prompt = _SUMMARIZE_PROMPT.format(description=description[:8000])
    try:
        response = client.chat(
            user_id=user_id, provider=provider, model=model,
            messages=[{"role": "user", "content": summary_prompt}],
            # Großzügig: Reasoning-Modelle (qwen3, deepseek-r1) brauchen Output-Budget
            # für ihren <think>-Block + die eigentliche Summary.
            max_tokens=_max_tokens_for(model),
        )
        text = response.content[0].text.strip() if response.content else ''
        # <think>...</think>-Blöcke entfernen (Qwen3, DeepSeek-R1)
        text = _strip_thinking_block(text)
        if text and len(text) >= 100:  # plausible summary
            logger.info(f'summarized description: {len(description)} → {len(text)} chars')
            return text
    except Exception as e:
        logger.warning(f'summarize call failed for user={user_id}: {e}')
    return description[:target_chars]


def _run_match_via_service(user: User, match: JobMatch, raw: RawJob, cv_summary: str,
                            provider: str, model: str) -> bool:
    """Match-Pfad via ai-provider-service (Production).

    Sicherheit:
    - Prompt-Härtung: System-Message + untrusted_data Tags (vs. Prompt-Injection)
    - Schema-Validation: strikte Output-Sanitization (vs. injektierte XSS/score=999)
    - Suspicious-Flag: bei Pattern-Match in Description ODER Score-Sprung

    Bei leerem/unparsbarem Output → einmaliger Retry mit von der KI
    vor-zusammengefasster Job-Description.
    """
    client = ai_provider_client.get_client()

    def call_match(description: str):
        # System+User-Message: Anweisungen separiert von unvertrauten Daten.
        # Der ai-provider-service / Anthropic-SDK extrahiert role='system' korrekt.
        user_msg = _build_user_message(cv_summary, {
            "title": raw.title, "description": description, "location": raw.location,
        })
        return client.chat(
            user_id=user.id, provider=provider, model=model,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE_MATCH},
                {"role": "user", "content": user_msg},
            ],
            # Reasoning-Modelle (qwen3, deepseek-r1, o1, …) brauchen mehr Budget
            # für ihren <think>-Block, sonst wird der JSON-Output abgeschnitten.
            max_tokens=_max_tokens_for(model),
        )

    try:
        response = call_match(raw.description)
    except AIProviderQueuedError as e:
        logger.info(f'match queued: queue_id={e.queue_id} user={user.id} provider={provider}')
        return False
    except Exception as e:
        logger.warning(
            "service-match failed for match=%s user=%s provider=%s: %s: %s",
            match.id, user.id, provider, type(e).__name__, e,
        )
        return False

    text = _strip_thinking_block(
        (response.content[0].text if response.content else '').strip()
    )
    parsed = _extract_first_json_object(text)

    # Retry mit Summary wenn erste Antwort leer oder unparsbar
    if not parsed:
        logger.info(
            f'match={match.id} first try unparseable (text-len={len(text)}), '
            f'retrying with summarized description'
        )
        try:
            short_desc = _summarize_description(
                client, user.id, provider, model, raw.description or ''
            )
            if short_desc and short_desc != raw.description:
                response2 = call_match(short_desc)
                text2 = _strip_thinking_block(
                    (response2.content[0].text if response2.content else '').strip()
                )
                parsed2 = _extract_first_json_object(text2)
                if parsed2:
                    # Tokens kumulieren (Summarize-Call + zweiter Match-Call)
                    response.usage.input_tokens += response2.usage.input_tokens
                    response.usage.output_tokens += response2.usage.output_tokens
                    text = text2
        except AIProviderQueuedError as e:
            logger.info(f'summarize-retry queued: queue_id={e.queue_id}')
            return False
        except Exception as e:
            logger.warning(f'summarize-retry failed for match={match.id}: {e}')

    result = _parse_match_response(
        text, response.usage.input_tokens, response.usage.output_tokens,
    )

    match.match_score = result.score
    match.match_reasoning = result.reasoning
    match.missing_skills = result.missing_skills
    raw.crawl_status = 'matched'

    # Heuristische Sicherheits-Flags (Defense-in-Depth)
    suspicious_reasons: list[str] = []
    # 1) Injection-Patterns in Title/Description?
    desc_for_check = (raw.description or '') + ' ' + (raw.title or '')
    injection_hits = detect_injection_patterns(desc_for_check)
    if injection_hits:
        # Prefix damit man im UI lesen kann was getriggert hat
        suspicious_reasons.extend(f'input:{h}' for h in injection_hits)
    # 2) Auffälliger Score-Sprung relativ zum PreFilter?
    if has_suspicious_score_jump(match.prefilter_score, result.score):
        suspicious_reasons.append('score_jump')
    match.suspicious_reasons = ','.join(suspicious_reasons) if suspicious_reasons else None

    if suspicious_reasons:
        logger.info(
            f'match={match.id} flagged suspicious: {suspicious_reasons} '
            f'(score={result.score}, prefilter={match.prefilter_score})'
        )

    # Cost-Tracking nur für kostenpflichtige Provider. Lokale Provider (Ollama,
    # Mammouth, Custom-Endpoint) sind aus User-Sicht gratis — Cost mit Claude-
    # Preisen zu schätzen würde das Tagesbudget falsch verbrauchen.
    if response.via in ('ollama', 'mammouth', 'custom'):
        cost_cents = 0
        key_owner = 'user' if response.via == 'ollama' else 'custom_endpoint'
    else:
        cost_cents = _estimate_cost_cents(result.tokens_in, result.tokens_out)
        key_owner = 'server'

    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_cents / 100.0,
        key_owner=key_owner,
    ))
    db.session.flush()
    return True


def _run_match_via_local_factory(user: User, match: JobMatch, raw: RawJob, cv_summary: str,
                                  provider: str, model: str) -> bool:
    """Legacy-Pfad: lokale ProviderFactory (nur Local-Dev ohne Service)."""
    try:
        user_config = {}
        if provider in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
            config_json = user.ai_provider_config or '{}'
            config_dict = json.loads(config_json)
            user_config = config_dict.get(provider, {})
            if 'api_key_encrypted' in user_config:
                dek = get_key_cache().get(user.id)
                if not dek:
                    logger.warning(f'match failed: DEK cache miss for user={user.id}, provider={provider}')
                    return False
                api_key = EncryptionService.decrypt_data(user_config['api_key_encrypted'], dek)
                user_config = {**user_config, 'api_key': api_key}

        user_client = ProviderFactory.get_client(provider, user_config)
        result = match_job_with_claude(
            client=user_client, model=model, cv_summary=cv_summary,
            job={"title": raw.title, "description": raw.description, "location": raw.location},
        )
    except Exception as e:
        logger.warning(
            "local-match failed for match=%s user=%s provider=%s: %s: %s",
            match.id, user.id, provider, type(e).__name__, e,
        )
        return False

    match.match_score = result.score
    match.match_reasoning = result.reasoning
    match.missing_skills = result.missing_skills
    raw.crawl_status = 'matched'

    cost_cents = _estimate_cost_cents(result.tokens_in, result.tokens_out)
    key_owner = 'server'
    if provider == ProviderConfig.OLLAMA:
        key_owner = 'user'
    elif provider in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        key_owner = 'custom_endpoint'

    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_cents / 100.0,
        key_owner=key_owner,
    ))
    db.session.flush()
    return True


def _is_failed_evaluation(match: JobMatch) -> bool:
    """True wenn der bestehende Match-Score von einem vorherigen Fehlschlag stammt.

    Solche Matches haben score=0 und ein 'Bewertung fehlgeschlagen'-Reasoning —
    sie sollen bei einem manuellen oder Bulk-Re-Run neu bewertet werden statt als
    'schon bewertet' geskippt zu werden.
    """
    if match.match_score is None:
        return False
    if match.match_score > 0:
        return False
    reasoning = (match.match_reasoning or '').strip().lower()
    return reasoning.startswith('bewertung fehlgeschlagen')


def _run_claude_match_for(client, user: User, match: JobMatch) -> bool:
    """Führt AI-Match aus. Bevorzugt ai-provider-service, fallback auf lokale ProviderFactory.

    Der `client`-Parameter ist Legacy (bleibt aus Backward-Compat) — wird nicht mehr genutzt.

    Returns:
        True wenn erfolgreich bewertet (DB-Update gemacht).
        False wenn geskippt (schon bewertet, Budget erschöpft, AI-Error oder gequeued).
    """
    # Bereits erfolgreich bewertet → nicht nochmal. Aber: Failed-Evals ('Bewertung
    # fehlgeschlagen' aus früheren Runs) explizit re-tryen.
    if match.match_score is not None and not _is_failed_evaluation(match):
        return False
    # Failed-Eval → setze Felder zurück, damit eine neue saubere Bewertung möglich ist
    if _is_failed_evaluation(match):
        match.match_score = None
        match.match_reasoning = None
        match.missing_skills = []
        match.suspicious_reasons = None

    if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return False

    raw = RawJob.query.get(match.raw_job_id)
    if raw is None:
        return False

    cv_summary = _build_cv_summary(user.cv_data_json)
    provider = user.ai_provider or ProviderConfig.CLAUDE
    model = user.ai_provider_model or DEFAULT_MODEL

    if ai_provider_client.is_enabled():
        return _run_match_via_service(user, match, raw, cv_summary, provider, model)
    return _run_match_via_local_factory(user, match, raw, cv_summary, provider, model)


@jobs_cron_bp.post('/claude-match')
@require_cron_token
def claude_match():
    started = time.time()
    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key — der Service
    # hat seinen eigenen. Im Local-Dev-Modus weiterhin Pflicht.
    if not ai_provider_client.is_enabled():
        client = _get_anthropic_client()
        if client is None:
            return jsonify({"error": "Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt"}), 503
    else:
        client = None

    matched = 0
    skipped_budget = 0

    users_with_pending = (db.session.query(User)
                          .join(JobMatch, JobMatch.user_id == User.id)
                          .filter(JobMatch.match_score.is_(None),
                                  JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
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
                              JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
                              JobMatch.status == 'new')
                      .order_by(JobMatch.prefilter_score.desc())
                      .limit(user.job_claude_budget_per_tick).all())

        for match in candidates:
            if time.time() - started > HARD_TIME_LIMIT_SEC:
                break
            if _run_claude_match_for(client, user, match):
                matched += 1
            else:
                # Wenn Budget gerade erschöpft wurde mid-loop → weiter zum nächsten User
                if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
                    break

        db.session.commit()

    return jsonify({"matched": matched, "skipped_budget": skipped_budget,
                    "duration_sec": round(time.time() - started, 2)}), 200


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


@jobs_cron_bp.post('/cleanup')
@require_cron_token
def cleanup():
    cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)

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
