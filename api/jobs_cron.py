# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cron-Endpoints für Job-Discovery Pipeline (Token-geschützt)."""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from flask import Blueprint, jsonify

from database import db
from models import User, JobSource, RawJob, JobMatch, ApiCall, Application
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
from services.job_matching.embedder import embed_raw_job
from services.provider_service import ProviderFactory, ProviderConfig
from services.job_matching.notifier import send_match_notification
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from services import ai_provider_client
from services.ai_provider_client import AIProviderQueuedError

logger = logging.getLogger(__name__)


jobs_cron_bp = Blueprint('jobs_cron', __name__, url_prefix='/api/jobs')

# Email-basierte Source-Typen werden NICHT vom generischen /crawl-source
# Round-Robin verarbeitet, sondern ausschließlich vom dedizierten
# /indeed-email-import-all (Cron) bzw. User-triggered /import-from-email.
# Grund: sie brauchen User-IMAP-Credentials und sind manuell/per-User.
EMAIL_SOURCE_TYPES = ("indeed_email", "linkedin_email", "xing_email")


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


def _estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    """Echte USD-Kosten als float — kein Rounding auf cents.

    Vorher returnte diese Funktion `int` cents via round() — bei Haiku-Pricing
    (Input $1/M, Output $5/M) sind typische Match-Calls (~2500 in / 250 out)
    nur ~0.4 cent wert und wurden fälschlich auf 0 gerundet. Über 100+ Calls
    pro Tag verschwand der Kostenanteil komplett aus `api_calls.cost`, obwohl
    Anthropic real berechnete. Float-USD löst das Reporting-Problem.
    """
    usd = (tokens_in / 1_000_000 * COST_USD_PER_1M_TOKENS_IN
           + tokens_out / 1_000_000 * COST_USD_PER_1M_TOKENS_OUT)
    return max(0.0, usd)


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


# Wieviele AI-Confirm-Calls maximal pro Pre-Filter-Tick. Schuetzt vor
# Cron-Timeout + Kosten-Explosion bei vielen Niedrig-Score-Items.
AI_CONFIRM_BUDGET = 50


def _ai_confirm_prefilter_dismiss(user, raw, cv_summary: str):
    """Schneller AI-Check vor dem Auto-Dismiss: passt der Job DOCH zum CV?

    Pre-Filter ist eine Keyword-Heuristik — uebersieht z.B. ungewoehnlich
    formulierte Job-Beschreibungen. Diese Funktion fragt das LLM nach
    einem groben Ja/Nein bevor wir endgueltig dismissen.

    Returns:
        (fits: bool, reason: str)  — fits=True heisst Pre-Filter hat sich
            geirrt, Item nicht dismissen.
        None — kein AI-Provider verfuegbar / Parse-Error / Timeout. Caller
            soll auf altes Verhalten fallen (sofort dismissen mit
            'prefilter_low_score'-Marker).
    """
    if not getattr(user, 'ai_provider', None) or not getattr(user, 'ai_provider_model', None):
        return None
    from services import ai_provider_client as _aip
    client = _aip.get_client()
    if client is None:
        return None

    title = (raw.title or '(ohne Titel)')[:200]
    description = (raw.description or '')[:1500]
    cv_text = (cv_summary or '')[:1500]
    prompt = (
        "Du bist ein Recruiting-Assistent. Bewertet wird grob, ob ein Job "
        "zum CV-Profil grundsaetzlich passt. Sei tolerant — auch wenn nicht "
        "100% perfekt, aber das CV-Profil in die richtige Richtung geht, "
        "antworte mit fits=true.\n\n"
        f"CV-Profil:\n{cv_text}\n\n"
        f"Job-Titel: {title}\n"
        f"Job-Beschreibung:\n{description}\n\n"
        'Antworte NUR mit JSON: {"fits": true|false, "reason": "<1 Satz, deutsch, max 150 Zeichen>"}'
    )

    try:
        resp = client.chat(
            user_id=user.id,
            provider=user.ai_provider,
            model=user.ai_provider_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
    except Exception as exc:
        logger.warning("ai_confirm_prefilter failed for match=%s: %s", raw.id, exc)
        return None

    # ChatResponse-Dataclass oder dict (Tests mocken dict)
    content = ""
    if hasattr(resp, 'content'):
        contents = getattr(resp, 'content', None) or []
        if contents and hasattr(contents[0], 'text'):
            content = contents[0].text
    elif isinstance(resp, dict):
        content = resp.get('content', '') or ''
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rstrip("`").strip()
    try:
        data = json.loads(content)
        fits = bool(data.get('fits'))
        reason = str(data.get('reason') or '')[:200]
        return (fits, reason)
    except (json.JSONDecodeError, ValueError, TypeError):
        # Text-Fallback fuer LLMs die nicht-strikte JSON liefern
        c_lower = content.lower()
        if '"fits": true' in c_lower or 'fits:true' in c_lower or 'fits: true' in c_lower:
            return (True, content[:200])
        if '"fits": false' in c_lower or 'fits:false' in c_lower or 'fits: false' in c_lower:
            return (False, content[:200])
        return None


def _has_user_judgment(match) -> bool:
    """True wenn der User bereits eine eigene Bewertung hinterlegt hat.

    Schuetzt vor Auto-Updates die User-Reasons ueberschreiben — Backfills
    und Pre-Filter-Cron muessen das vor jedem feedback_text-Write pruefen.

    User-Bewertung erkennen wir an:
      - feedback_reasons (JSON-Array mit Tags wie 'wrong_location') oder
      - feedback_text das KEIN Auto-Code ist (also User-Freitext)
    """
    reasons = (match.feedback_reasons or '').strip()
    if reasons and reasons not in ('[]', ''):
        return True
    txt = (match.feedback_text or '').strip()
    if txt and txt not in _AUTO_FEEDBACK_CODES_CRON:
        return True
    return False


# Lokales Set fuer _has_user_judgment (gespiegelt von api.jobs_user.AUTO_FEEDBACK_CODES).
# Wenn neue Auto-Codes hinzukommen → an BEIDEN Stellen ergaenzen.
_AUTO_FEEDBACK_CODES_CRON = frozenset({
    'auto_blocked_by_rejection',
    'rejection_blocked_skip',
    'company_already_rejected',
    'prefilter_low_score',
    'prefilter_low_score_ai_confirmed',
    'claude_low_score',
    'learned',
    'duplicate_of_other',
    'title_blacklisted',
    'url_pattern_mismatch',
})


def _select_due_source() -> JobSource | None:
    # Email-basierte Sources (indeed_email, linkedin_email, xing_email)
    # werden NUR vom dedizierten /indeed-email-import-all-Cron verarbeitet,
    # nicht vom generischen Round-Robin: sie brauchen User-IMAP-Credentials
    # und sind pro-User konfiguriert.
    candidates = JobSource.query.filter(
        JobSource.enabled == True,
        JobSource.type.notin_(_email_source_types()),
    ).all()
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
    cv_summary_cache: dict = {}  # user_id → cv_summary string (für AI-Confirm)
    user_cache: dict = {}
    ctx_cache: dict = {}
    rejected_companies_cache: dict = {}  # user_id → set(lower(company))
    scored = 0
    dismissed = 0
    ai_confirm_used = 0       # Budget-Counter pro Run
    ai_confirm_overruled = 0  # Items die AI "passt doch" gerettet hat
    rejected_company_dismissed = 0  # Items wegen Company im Rejection-Fenster

    def _rejected_companies_for(user_id: str, window_days: int) -> set:
        """Lädt + cached die rejected-companies fuer einen User."""
        if user_id not in rejected_companies_cache:
            cutoff_dt = datetime.utcnow() - timedelta(days=window_days)
            rows = (
                db.session.query(db.func.lower(Application.company))
                .filter(
                    Application.user_id == user_id,
                    Application.deleted == False,  # noqa: E712
                    Application.status.in_(['absage', 'rejected']),
                    Application.company.isnot(None),
                    db.or_(
                        Application.applied_date >= cutoff_dt.date(),
                        db.and_(Application.applied_date.is_(None),
                                Application.created_at >= cutoff_dt),
                    ),
                )
                .distinct()
                .all()
            )
            rejected_companies_cache[user_id] = {r[0] for r in rows if r[0]}
        return rejected_companies_cache[user_id]

    for match in pending:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if match.user_id not in cv_cache:
            user = User.query.get(match.user_id)
            user_cache[match.user_id] = user
            cv_data = json.loads(user.cv_data_json) if user.cv_data_json else {}
            cv_cache[match.user_id] = tokenize_cv(cv_data)
            cv_summary_cache[match.user_id] = _build_cv_summary(user.cv_data_json)
            ctx_cache[match.user_id] = PrefilterContext(
                language_filter=user.job_language_filter,
                region_filter=user.job_region_filter,
            )

        raw = RawJob.query.get(match.raw_job_id)

        # Duplikat-Check zuerst: gleiche Title+Company beim selben User
        # bereits angesehen (imported/dismissed)? Crawl-Source-Cron findet
        # denselben Job oft ueber verschiedene URLs (RSS/Adzuna/Arbeitnow
        # geben unterschiedliche URLs fuer gleichen Job zurueck).
        is_duplicate = False
        if raw.title and raw.company:
            dup_exists = (
                JobMatch.query
                .join(RawJob, JobMatch.raw_job_id == RawJob.id)
                .filter(
                    JobMatch.user_id == match.user_id,
                    JobMatch.id != match.id,
                    JobMatch.status.in_(['imported', 'dismissed']),
                    RawJob.title == raw.title,
                    RawJob.company == raw.company,
                )
                .first()
            )
            is_duplicate = dup_exists is not None

        score = score_job(
            cv_cache[match.user_id],
            {"title": raw.title, "description": raw.description, "location": raw.location},
            ctx_cache[match.user_id],
        )
        match.prefilter_score = score
        # Best-Effort Embedding (Ollama up → JobEmbedding wird befüllt)
        try:
            embed_raw_job(raw)
        except Exception:
            pass  # Embedding ist optional, prefilter funktioniert auch ohne

        # Pruefe ob Firma in den letzten N Tagen abgelehnt hat — wenn ja,
        # sofort dismissen (egal welcher Score). Spiegelt das UI-Listen-Filter,
        # aber persistent statt nur view-side. Dominiert ueber alle anderen
        # Auto-Dismiss-Reasons (Duplikat, Score, AI).
        is_rejected_company = False
        if raw.company:
            user_obj = user_cache.get(match.user_id)
            if user_obj:
                window = user_obj.job_reject_window_days or 180
                rejected_set = _rejected_companies_for(match.user_id, window)
                if raw.company.lower().strip() in rejected_set:
                    is_rejected_company = True

        # User-Judgment NIE ueberschreiben — wenn User schon eigene Reasons
        # (feedback_reasons-Tags ODER Freitext) hinterlegt hat, bleibt das.
        user_has_judgment = _has_user_judgment(match)

        if is_rejected_company:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'company_already_rejected'
            dismissed += 1
            rejected_company_dismissed += 1
        elif is_duplicate:
            # Duplikat dominiert ueber Score — zeigt dem User klar warum
            # das Item dismissed wurde, auch wenn Score eigentlich OK gewesen
            # waere.
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'duplicate_of_other'
            dismissed += 1
        elif score < PREFILTER_DISMISS_THRESHOLD:
            # AI-Confirm vor dem endgueltigen Dismiss — Pre-Filter ist
            # eine Keyword-Heuristik und uebersieht ungewoehnlich formulierte
            # Job-Beschreibungen. Budget: 50 AI-Calls/Tick.
            ai_result = None
            if ai_confirm_used < AI_CONFIRM_BUDGET:
                user_obj = user_cache.get(match.user_id)
                cv_sum = cv_summary_cache.get(match.user_id, '')
                if user_obj and cv_sum:
                    ai_result = _ai_confirm_prefilter_dismiss(user_obj, raw, cv_sum)
                    if ai_result is not None:
                        ai_confirm_used += 1

            if ai_result is None:
                # Kein AI-Provider / Budget aufgebraucht / Parse-Error →
                # altes Verhalten (sofort dismissen, ohne AI-Bestaetigung).
                match.status = 'dismissed'
                if not user_has_judgment:
                    match.feedback_text = 'prefilter_low_score'
                dismissed += 1
            elif ai_result[0]:
                # AI sagt "passt doch" → Item NICHT dismissen, durchlaeuft
                # weiter den normalen Claude-Match-Pfad (Stage 3).
                ai_confirm_overruled += 1
                # Begründung im match_reasoning konservieren fuer Audit.
                if ai_result[1]:
                    match.match_reasoning = f"[AI-Overrule] {ai_result[1]}"
            else:
                # AI bestaetigt: passt wirklich nicht.
                match.status = 'dismissed'
                if not user_has_judgment:
                    match.feedback_text = 'prefilter_low_score_ai_confirmed'
                if ai_result[1]:
                    match.match_reasoning = f"[AI-Confirm-Dismiss] {ai_result[1]}"
                dismissed += 1
        scored += 1

    db.session.commit()
    return jsonify({
        "scored": scored, "dismissed": dismissed,
        "rejected_company_dismissed": rejected_company_dismissed,
        "ai_confirm_used": ai_confirm_used,
        "ai_confirm_overruled": ai_confirm_overruled,
        "duration_sec": round(time.time() - started, 2),
    }), 200


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
                            description: str, target_chars: int = 1500,
                            fallback_kwargs: Optional[dict] = None) -> str:
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
            **(fallback_kwargs or {}),
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
    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='match')

    # Phase B: User-Feedback-Historie einmalig laden, im closure
    # `call_match` mehrfach wiederverwendet (Match + ggf. Summary-Retry).
    from services.job_matching.feedback_context import get_user_feedback_context
    feedback_context = get_user_feedback_context(user.id)

    def call_match(description: str):
        # System+User-Message: Anweisungen separiert von unvertrauten Daten.
        # Der ai-provider-service / Anthropic-SDK extrahiert role='system' korrekt.
        user_msg = _build_user_message(cv_summary, {
            "title": raw.title, "description": description, "location": raw.location,
        }, feedback_context=feedback_context)
        return client.chat(
            user_id=user.id, provider=provider, model=model,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE_MATCH},
                {"role": "user", "content": user_msg},
            ],
            # Reasoning-Modelle (qwen3, deepseek-r1, o1, …) brauchen mehr Budget
            # für ihren <think>-Block, sonst wird der JSON-Output abgeschnitten.
            max_tokens=_max_tokens_for(model),
            **fallback_kwargs,
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

    # Transient-Attribute für die Aufrufer-API (score_match liest sie aus
    # und liefert sie ans Frontend für die Bulk-Progress-Anzeige).
    match._last_via = response.via
    match._last_fallback_used = response.fallback_used

    # Retry mit Summary wenn erste Antwort leer oder unparsbar
    if not parsed:
        logger.info(
            f'match={match.id} first try unparseable (text-len={len(text)}), '
            f'retrying with summarized description'
        )
        try:
            # CV-Summarize hat eigenen Pro-Task-Override (sonst: match-Modell)
            sum_provider, sum_model = user.get_model_for('cv_summarize')
            short_desc = _summarize_description(
                client, user.id,
                sum_provider or provider,
                sum_model or model,
                raw.description or '',
                fallback_kwargs=fallback_kwargs,
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
        cost_usd = 0.0
        key_owner = 'user' if response.via == 'ollama' else 'custom_endpoint'
    else:
        cost_usd = _estimate_cost_usd(result.tokens_in, result.tokens_out)
        key_owner = 'server'

    # Bei Fallback echten Modellnamen loggen (ai-provider-service liefert
    # ChatResponse.model seit 2026-05-19). Bei Primary-Path = Wunschmodell.
    # Backward-compat: response.model leer falls Service alt → falle auf
    # Wunschmodell zurueck.
    logged_model = response.model if (response.fallback_used and response.model) else model

    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=logged_model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_usd,
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
        # Phase B: User-Feedback-Historie als Prompt-Kontext injecten.
        # Bei leerer History (Neu-User): get_user_feedback_context()=='' →
        # match_job_with_claude fällt auf legacy single-prompt zurück.
        from services.job_matching.feedback_context import get_user_feedback_context
        feedback_context = get_user_feedback_context(user.id)
        result = match_job_with_claude(
            client=user_client, model=model, cv_summary=cv_summary,
            job={"title": raw.title, "description": raw.description, "location": raw.location},
            feedback_context=feedback_context,
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

    cost_usd = _estimate_cost_usd(result.tokens_in, result.tokens_out)
    key_owner = 'server'
    if provider == ProviderConfig.OLLAMA:
        key_owner = 'user'
        cost_usd = 0.0  # Lokaler Provider, kein API-Bill
    elif provider in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        key_owner = 'custom_endpoint'
        cost_usd = 0.0  # User bezahlt direkt beim Provider, kein Server-Cost

    db.session.add(ApiCall(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost=cost_usd,
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
    # Pro-Task-Override für 'match' (fallback auf user.ai_provider/_model)
    feat_provider, feat_model = user.get_model_for('match')
    provider = feat_provider or ProviderConfig.CLAUDE
    model = feat_model or DEFAULT_MODEL

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


# ---------------------------------------------------------------------------
# URL-Health-Check (Cron)
# ---------------------------------------------------------------------------

URL_HEALTH_BATCH_SIZE = 100
URL_HEALTH_RECHECK_INTERVAL_HOURS = 24
# Nur Jobs juenger als X Tage pruefen — alte werden bereits durch
# cleanup() archiviert.
URL_HEALTH_MAX_AGE_DAYS = 30
# Per-Domain-Throttle: nach jedem HEAD-Request 2s warten BEVOR der
# naechste fuer dieselbe Domain rausgeht. Vermeidet IP-Block durch
# indeed/linkedin bei vielen Checks hintereinander.
URL_HEALTH_PER_DOMAIN_DELAY_S = 2.0


@jobs_cron_bp.post('/url-health-check')
@require_cron_token
def url_health_check():
    """Batch-URL-Check fuer RawJobs. Markiert nicht-erreichbare als
    'marked_for_deletion' (3-Strike-Logik oder 404/410 sofort).

    Aelteste-zuletzt-gepruefte zuerst (NULL = nie geprueft kommt vor).
    Max URL_HEALTH_BATCH_SIZE pro Run, nur RawJobs juenger als
    URL_HEALTH_MAX_AGE_DAYS, nur Status != 'archived'/'marked_for_deletion'.

    Returns: {checked: int, marked: int, ok: int, skipped_no_url: int}
    """
    from services import url_health_check as _url_health_check_mod
    from urllib.parse import urlparse
    import time as _time

    now = datetime.utcnow()
    age_cutoff = now - timedelta(days=URL_HEALTH_MAX_AGE_DAYS)
    recheck_cutoff = now - timedelta(hours=URL_HEALTH_RECHECK_INTERVAL_HOURS)

    # Aelteste-zuletzt-gepruefte zuerst (NULL = nie geprueft kommt vor).
    candidates = (
        RawJob.query
        .filter(
            RawJob.crawl_status.notin_(['archived', 'marked_for_deletion']),
            RawJob.created_at >= age_cutoff,
            db.or_(
                RawJob.url_last_checked_at.is_(None),
                RawJob.url_last_checked_at < recheck_cutoff,
            ),
        )
        .order_by(
            db.case(
                (RawJob.url_last_checked_at.is_(None), 0),
                else_=1,
            ),
            RawJob.url_last_checked_at.asc(),
        )
        .limit(URL_HEALTH_BATCH_SIZE)
        .all()
    )

    checked = 0
    marked = 0
    ok = 0
    skipped_no_url = 0
    last_call_per_domain: dict[str, float] = {}
    # Hard-Cap auf Total-Run-Time: gunicorn-Timeout ist 180s, wir cappen
    # konservativ bei 150s. Wer noch nicht durch ist, kommt im naechsten
    # Cron-Run dran (Sortierung: aelteste-zuletzt-gepruefte zuerst).
    run_deadline = _time.time() + 150.0

    for raw in candidates:
        if _time.time() > run_deadline:
            logger.info("url-health-check: deadline reached at %d/%d, deferring rest",
                        checked, len(candidates))
            break
        url = (raw.url or '').strip()
        if not url:
            skipped_no_url += 1
            continue

        # Per-Domain-Throttle
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ''
        if domain:
            last = last_call_per_domain.get(domain, 0.0)
            wait = URL_HEALTH_PER_DOMAIN_DELAY_S - (_time.time() - last)
            if wait > 0:
                _time.sleep(wait)
            last_call_per_domain[domain] = _time.time()

        status_label, http_code = _url_health_check_mod.check_url(url)
        was_marked = _url_health_check_mod.update_raw_job_health(
            raw, status_label, http_code,
        )
        checked += 1
        if was_marked:
            marked += 1
            logger.info(
                'url-health-check: raw_id=%s marked_for_deletion (%s code=%s url=%s)',
                raw.id, status_label, http_code, url[:80],
            )
        if status_label == 'ok':
            ok += 1

    db.session.commit()
    return jsonify({
        'checked': checked, 'marked': marked, 'ok': ok,
        'skipped_no_url': skipped_no_url,
    }), 200


# ---------------------------------------------------------------------------
# Indeed-Email Auto-Import (Cron)
# ---------------------------------------------------------------------------

@jobs_cron_bp.post('/indeed-email-import-all')
@require_cron_token
def indeed_email_import_all():
    """Auto-Import für ALLE eligible Email-Sources (indeed/linkedin/xing).

    Trotz des historischen URL-Pfads ``indeed-email-import-all`` verarbeitet
    dieser Endpoint alle drei Email-Plattform-Typen (``indeed_email``,
    ``linkedin_email``, ``xing_email``) in einem Lauf. Pfad ist stabil, damit
    die VPS-Cron-Zeile unverändert bleibt.

    Eligibility:
    - type in _email_source_types() (hardcoded PROFILES + DB-PlatformProfiles)
    - enabled = True
    - last_crawled_at NULL oder älter als crawl_interval_min
    - Owner-User hat User.imap_password_encrypted ODER state.settings.indeedScriptUrl

    Blocked Jobs (Firma im Reject-Window) werden NICHT als 'new' JobMatch
    angelegt — sie kommen als 'dismissed' mit feedback_text='auto_blocked_by_rejection'
    in die DB. So tauchen sie nicht in den Vorschlägen auf, sind aber als
    Audit-Trail vorhanden (URL-Dedup verhindert auch erneutes Auto-Import).

    Returns: Summary mit pro-Source-Counts und gesamt-imported/skipped.
    """
    from services.job_sources import get_adapter as _get_adapter
    from services.job_sources import dedup as _dedup
    from api.jobs_user import (
        _get_rejected_companies_lower,
        _create_raw_job_and_match,
        _fetch_apps_script_emails,
    )

    now = datetime.utcnow()
    eligible = JobSource.query.filter(
        JobSource.type.in_(_email_source_types()),
        JobSource.enabled == True,  # noqa: E712
    ).all()

    runs = []
    total_imported = 0
    total_blocked_auto = 0

    for src in eligible:
        # Interval-Check
        if src.last_crawled_at is not None:
            next_due = src.last_crawled_at + timedelta(minutes=src.crawl_interval_min or 60)
            if next_due > now:
                continue  # noch nicht fällig

        user = User.query.get(src.user_id) if src.user_id else None
        if user is None:
            runs.append({"source_id": src.id, "status": "skipped_no_owner"})
            continue

        # Modus bestimmen: indeedScriptUrl in user.settings oder IMAP-Creds?
        settings = {}
        if user.settings_json:
            try:
                settings = json.loads(user.settings_json) or {}
            except (TypeError, ValueError):
                settings = {}
        script_url = (settings.get('indeedScriptUrl') or '').strip()
        has_imap = bool(user.imap_password_encrypted)

        try:
            adapter = _get_adapter(src.type, src.config, user=user)
            if script_url:
                emails, _cache_hit = _fetch_apps_script_emails(
                    script_url, user_id=user.id, use_cache=False,  # Cron: immer frisch
                )
                fetched = adapter.parse_emails(emails)
                mode = 'apps_script_proxy'
            elif has_imap:
                fetched = adapter.fetch()
                mode = 'imap'
            else:
                runs.append({"source_id": src.id, "status": "skipped_no_credentials"})
                continue
        except Exception as e:
            src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
            src.consecutive_failures = (src.consecutive_failures or 0) + 1
            if src.consecutive_failures >= 5:
                src.enabled = False
            db.session.commit()
            runs.append({
                "source_id": src.id, "status": "error",
                "error": src.last_error,
                "auto_disabled": not src.enabled,
            })
            continue

        # Erfolg: counter reset
        src.consecutive_failures = 0
        src.last_error = None

        # Dedup + Rejection
        existing_urls = _dedup.get_existing_job_urls()
        fresh = _dedup.deduplicate(fetched, existing_urls)
        duplicates_count = len(fetched) - len(fresh)

        window_days = int(user.job_reject_window_days or 180)
        rejected_companies = (
            _get_rejected_companies_lower(user.id, window_days)
            if user.job_reject_filter_enabled else set()
        )

        imported_count = 0
        blocked_auto_count = 0
        for fjob in fresh:
            company_lower = (fjob.company or '').strip().lower()
            is_blocked = bool(company_lower) and company_lower in rejected_companies
            payload = {
                'title': fjob.title, 'company': fjob.company,
                'location': fjob.location, 'url': fjob.url,
                'external_id': fjob.external_id, 'description': fjob.description,
                'raw': fjob.raw or {},
            }
            if is_blocked:
                # Cron kann nicht interaktiv fragen → silent dismissed.
                # User sieht nichts in der Liste, aber kein Re-Import durch URL-Dedup.
                _create_raw_job_and_match(
                    src, user.id, payload,
                    match_status='dismissed',
                    feedback_text='auto_blocked_by_rejection',
                )
                blocked_auto_count += 1
            else:
                _create_raw_job_and_match(src, user.id, payload, match_status='new')
                imported_count += 1

        src.last_crawled_at = now
        total_imported += imported_count
        total_blocked_auto += blocked_auto_count
        runs.append({
            "source_id": src.id, "status": "ok", "mode": mode,
            "total_emails": len(fetched), "duplicates": duplicates_count,
            "imported": imported_count, "blocked_auto": blocked_auto_count,
        })

    db.session.commit()
    return jsonify({
        "ran_at": now.isoformat(),
        "total_sources": len(eligible),
        "processed_runs": len(runs),
        "total_imported": total_imported,
        "total_blocked_auto": total_blocked_auto,
        "runs": runs,
    }), 200
