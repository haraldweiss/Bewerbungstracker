# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Shared Claude-Matching utilities extracted from api/jobs_cron.py + api/jobs_user.py.

Erlaubt Import aus services/tasks/handlers/ ohne zirkuläre Imports.
"""
from __future__ import annotations

import concurrent.futures as _futures
import json
import logging
import os
import time
from typing import Callable, Optional

from sqlalchemy import or_

from database import db
from models import User, RawJob, JobMatch, ApiCall
from services import cost_tracker, ai_provider_client
from services.ai_provider_client import AIProviderQueuedError
from services.provider_service import ProviderFactory, ProviderConfig
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from services.job_matching.claude_matcher import (
    match_job_with_claude, MatchResult,
    SYSTEM_MESSAGE_MATCH, _build_user_message,
)
from services.job_matching.injection_detector import (
    detect_injection_patterns, has_suspicious_score_jump,
)

logger = logging.getLogger(__name__)

# Tick-Limits
MAX_PREFILTER_PER_TICK = 100
PREFILTER_DISMISS_THRESHOLD = 5
AUTO_CLAUDE_THRESHOLD = 50
HARD_TIME_LIMIT_SEC = 25
AI_CONFIRM_BUDGET = 50

# Technische-Fehler-Retry (siehe docs/superpowers/specs/2026-06-12-technical-failure-reeval-design.md)
MATCH_MAX_EVAL_ATTEMPTS = int(os.getenv("MATCH_MAX_EVAL_ATTEMPTS", "5"))
MATCH_FALLBACK_ENABLED = os.getenv("MATCH_FALLBACK_ENABLED", "true").lower() in ("1", "true", "yes")
MATCH_OLLAMA_FALLBACK_MODEL = os.getenv("MATCH_OLLAMA_FALLBACK_MODEL", "gemma4:12b")
PERMANENT_FAIL_REASONING = "Technisch nicht bewertbar – bitte manuell prüfen."

# Hinweis, wenn ein Match nicht bewertet werden kann, weil der User noch keinen
# auswertbaren Lebenslauf hinterlegt hat. Wird als match_reasoning gesetzt
# (match_score bleibt NULL), damit der Match in der Bewertungs-Queue bleibt und
# bei CV-Anlage automatisch neu bewertet wird.
NO_CV_REASONING = (
    "Noch kein Lebenslauf hinterlegt – wird automatisch bewertet, sobald du "
    "einen Lebenslauf (CV) anlegst."
)


def _retry_backoff_hours(attempts: int) -> int:
    """Mindest-Wartezeit bis zum nächsten Versuch: 1,2,4,8,12 (gekappt)."""
    return min(2 ** max(attempts - 1, 0), 12)


def _result_is_content_failure(result) -> bool:
    """True bei technischem Inhalts-Fehler (ungültiges JSON), nicht bei echtem Score 0."""
    failed = getattr(result, 'failed', False)
    if isinstance(failed, bool) and failed:
        return True
    # Lokaler Pfad (match_job_with_claude) hat kein failed-Flag — Heuristik:
    return (result.score == 0
            and (result.reasoning or '').strip().lower().startswith('bewertung fehlgeschlagen'))


DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "claude-haiku-4-5-20251001")
COST_USD_PER_1M_TOKENS_IN = 0.80
COST_USD_PER_1M_TOKENS_OUT = 4.00

# Modelle mit eingebautem Reasoning-Block (<think>…</think>) brauchen viel mehr
# Output-Tokens, sonst wird der Antwortteil abgeschnitten — done_reason=length.
_REASONING_MODEL_PATTERNS = (
    'qwen3', 'qwen-3', 'deepseek-r1', 'deepseek-reasoner',
    'o1-', 'o3-', 'reasoner', 'reasoning',
)


def _get_anthropic_client():
    """Liefert einen Anthropic-Client oder None falls API-Key fehlt."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=api_key)


def _build_cv_summary(cv_data_json: str) -> str:
    """CV-Zusammenfassung für Claude-Prompt."""
    if not cv_data_json:
        return ""
    data = json.loads(cv_data_json)
    parts = []

    cv = data.get("cv") or {}
    if isinstance(cv, dict):
        if cv.get("summary"):
            parts.append(f"Zusammenfassung: {cv['summary']}")
        if cv.get("skills"):
            parts.append(f"Skills: {', '.join(cv['skills'])}")
        if cv.get("experiences"):
            titles = [e.get("title", "") for e in cv["experiences"][:5]]
            parts.append(f"Letzte Positionen: {' | '.join(titles)}")

    blob = data.get("cvData") or {}
    if isinstance(blob, dict):
        text = blob.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(f"CV-Volltext:\n{text}")

    return "\n".join(parts)


# Lokales Set fuer _has_user_judgment.
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


def _has_user_judgment(match) -> bool:
    """True wenn der User bereits eine eigene Bewertung hinterlegt hat."""
    reasons = (match.feedback_reasons or '').strip()
    if reasons and reasons not in ('[]', ''):
        return True
    txt = (match.feedback_text or '').strip()
    if txt and txt not in _AUTO_FEEDBACK_CODES_CRON:
        return True
    return False


def _is_reasoning_model(model: str) -> bool:
    if not model:
        return False
    m = model.lower()
    return any(p in m for p in _REASONING_MODEL_PATTERNS)


def _max_tokens_for(model: str, base: int = 2000) -> int:
    return base * 4 if _is_reasoning_model(model) else base


def _strip_thinking_block(text: str) -> str:
    if not text:
        return text
    if '</think>' in text:
        text = text.rsplit('</think>', 1)[1].lstrip()
    return text


def _extract_first_json_object(text: str) -> dict | None:
    """Extrahiert das erste balanciert geschlossene JSON-Objekt aus dem Text."""
    if not text:
        return None

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
    """Strikte Schema-Validierung. Schützt gegen kompromittierte Provider-Antworten."""
    warnings: list[str] = []

    raw_score = data.get("score", 0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
        warnings.append('score_not_number')
    if score < 0 or score > 100:
        warnings.append(f'score_out_of_range:{score}')
        score = max(0.0, min(100.0, score))

    reasoning = str(data.get("reasoning", "") or "")
    if len(reasoning) > 500:
        reasoning = reasoning[:500].rstrip() + "…"
        warnings.append('reasoning_truncated')

    skills_raw = data.get("missing_skills")
    if not isinstance(skills_raw, list):
        skills_raw = []
        if data.get("missing_skills") is not None:
            warnings.append('missing_skills_not_list')
    skills: list[str] = []
    for s in skills_raw[:10]:
        s_str = str(s)[:80].strip()
        s_str = s_str.replace('<', '').replace('>', '').replace('`', '')
        if s_str:
            skills.append(s_str)
    if len(skills_raw) > 10:
        warnings.append('missing_skills_truncated')

    return score, reasoning, skills, warnings


def _parse_match_response(text: str, tokens_in: int, tokens_out: int) -> MatchResult:
    """Parst die JSON-Antwort vom Provider in ein MatchResult."""
    data = _extract_first_json_object(text or '')
    if data is None:
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
            failed=True,
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
            failed=True,
        )


_SUMMARIZE_PROMPT = """Fasse die folgende Stellenausschreibung in maximal 1500 Zeichen zusammen.
Wichtig: Behalte alle technischen Anforderungen, Skills, Aufgaben und Qualifikationen bei.
Lass Marketing-Sprache, Boilerplate, Benefits-Listen und allgemeine Firmenbeschreibungen weg.
Antworte AUSSCHLIESSLICH mit der Zusammenfassung, kein Drumherum, keine Anrede.

STELLENAUSSCHREIBUNG:
{description}
"""


def _summarize_description(client, user_id: str, provider: str, model: str,
                            description: str, target_chars: int = 1500,
                            fallback_kwargs: Optional[dict] = None) -> str:
    if not description or len(description) <= target_chars:
        return description or ''

    summary_prompt = _SUMMARIZE_PROMPT.format(description=description[:8000])
    try:
        response = client.chat(
            user_id=user_id, provider=provider, model=model,
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=_max_tokens_for(model),
            **(fallback_kwargs or {}),
        )
        text = response.content[0].text.strip() if response.content else ''
        text = _strip_thinking_block(text)
        if text and len(text) >= 100:
            logger.info(f'summarized description: {len(description)} → {len(text)} chars')
            return text
    except Exception as e:
        logger.warning(f'summarize call failed for user={user_id}: {e}')
    return description[:target_chars]


def _run_match_via_service(user: User, match: JobMatch, raw: RawJob, cv_summary: str,
                            provider: str, model: str) -> bool:
    """Match-Pfad via ai-provider-service (Production) mit Ollama-Fallback-Kette."""
    client = ai_provider_client.get_client()
    if MATCH_FALLBACK_ENABLED:
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

    result = _parse_match_response(
        text, response.usage.input_tokens, response.usage.output_tokens,
    )

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

    if _result_is_content_failure(result):
        match.eval_attempts = (match.eval_attempts or 0) + 1
        match.match_score = None
        match.missing_skills = []
        match.match_reasoning = (
            PERMANENT_FAIL_REASONING
            if match.eval_attempts >= MATCH_MAX_EVAL_ATTEMPTS else None
        )
        return False

    match.match_score = result.score
    match.match_reasoning = result.reasoning
    match.missing_skills = result.missing_skills
    match.eval_attempts = 0
    raw.crawl_status = 'matched'

    cost_usd = cost_tracker.estimate_cost_usd(model, result.tokens_in, result.tokens_out)
    key_owner = 'server'
    if provider == ProviderConfig.OLLAMA:
        key_owner = 'user'
        cost_usd = 0.0
    elif provider in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        key_owner = 'custom_endpoint'
        cost_usd = 0.0

    cost_tracker.record_call(
        user_id=user.id, endpoint='/api/jobs/match',
        model=model, tokens_in=result.tokens_in,
        tokens_out=result.tokens_out, cost_usd=cost_usd,
        key_owner=key_owner,
    )
    return True


def _is_failed_evaluation(match: JobMatch) -> bool:
    """True wenn der bestehende Match-Score von einem vorherigen Fehlschlag stammt."""
    if match.match_score is None:
        return False
    if match.match_score > 0:
        return False
    reasoning = (match.match_reasoning or '').strip().lower()
    return reasoning.startswith('bewertung fehlgeschlagen')


def _run_claude_match_for(client, user: User, match: JobMatch) -> bool:
    """Führt AI-Match aus. Bevorzugt ai-provider-service, fallback auf lokale ProviderFactory.

    Returns:
        True wenn erfolgreich bewertet (DB-Update gemacht).
        False wenn geskippt.
    """
    if (match.eval_attempts or 0) >= MATCH_MAX_EVAL_ATTEMPTS:
        return False  # permanent technisch fehlgeschlagen — nicht weiter auto-bewerten
    if match.match_score is not None and not _is_failed_evaluation(match):
        return False
    if _is_failed_evaluation(match):
        match.match_score = None
        match.match_reasoning = None
        match.missing_skills = []
        match.suspicious_reasons = None

    if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return False

    raw = RawJob.query.get(match.raw_job_id)
    if raw is None:
        return False

    cv_summary = _build_cv_summary(user.cv_data_json)

    if not cv_summary.strip():
        # Kein auswertbarer CV → kein LLM-Call. Ohne diese Guard antwortet das
        # Modell bei leerem CV mit Metatext (z.B. "CV empty - cannot assess
        # required skills"), der als "fehlender Skill" persistiert und im UI
        # als solcher angezeigt wird (Vorfall 2026-06-26). Match bleibt
        # verfügbar (match_score=NULL) und wird automatisch neu bewertet, sobald
        # der User einen Lebenslauf anlegt (reset_empty_cv_matches reaktiviert
        # etwaige Alt-Einträge beim CV-Upload).
        # eval_attempts bewusst NICHT erhöhen – sonst fiele der Match nach
        # MATCH_MAX_EVAL_ATTEMPTS aus der Queue und käme selbst mit späterem
        # CV nie wieder zur Bewertung.
        if match.match_reasoning != NO_CV_REASONING:
            match.match_reasoning = NO_CV_REASONING
            match.missing_skills = []
        return False

    feat_provider, feat_model = user.get_model_for('match')
    provider = feat_provider or ProviderConfig.CLAUDE
    model = feat_model or DEFAULT_MODEL

    if ai_provider_client.is_enabled():
        return _run_match_via_service(user, match, raw, cv_summary, provider, model)
    return _run_match_via_local_factory(user, match, raw, cv_summary, provider, model)


def reset_empty_cv_matches(user_id: str) -> int:
    """Reaktiviert Matches, die mit leerem/fehlerhaftem CV bewertet wurden.

    Erkennt das Symptom an der LLM-Signatur in ``missing_skills`` (z.B.
    "CV empty - cannot assess required skills"): das Modell liefert bei
    fehlendem CV gültiges JSON mit Score + diesem Metatext als "Skill".
    Diese Matches haben bereits ``match_score != None`` und tauchen daher
    nicht mehr in der Bewertungs-Queue auf (die Cron-Query filtert
    ``match_score IS NULL``). Setzt sie auf NULL zurück, damit der nächste
    Cron-Lauf sie mit vorhandenem CV sauber bewertet.

    Aufgerufen beim CV-Upload (``api/profile.py:update_cv``).

    Returns:
        Anzahl reaktivierter Matches (0 = keine betroffen).
    """
    stale = (JobMatch.query
             .filter(JobMatch.user_id == user_id,
                     JobMatch.match_score.isnot(None),
                     or_(JobMatch._missing_skills.ilike('%cv empty%'),
                         JobMatch._missing_skills.ilike('%cannot assess%')))
             .all())
    for m in stale:
        m.match_score = None
        m.match_reasoning = None
        m.missing_skills = []
        m.suspicious_reasons = None
        # eval_attempts zurücksetzen, falls der Match vorher als permanent
        # fehlgeschlagen markiert war – er soll vollständige Retry-Chancen haben.
        if (m.eval_attempts or 0) >= MATCH_MAX_EVAL_ATTEMPTS:
            m.eval_attempts = 0
    return len(stale)


def _ai_confirm_prefilter_dismiss(user, raw, cv_summary: str):
    """Schneller AI-Check vor dem Auto-Dismiss: passt der Job DOCH zum CV?

    Returns:
        (fits: bool, reason: str)  — fits=True heisst Pre-Filter hat sich geirrt.
        None — kein AI-Provider verfuegbar / Parse-Error / Timeout.
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

    _HARD_TIMEOUT = 55

    def _do_chat():
        return client.chat(
            user_id=user.id,
            provider=user.ai_provider,
            model=user.ai_provider_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )

    try:
        with _futures.ThreadPoolExecutor(max_workers=1) as _ex:
            _f = _ex.submit(_do_chat)
            try:
                resp = _f.result(timeout=_HARD_TIMEOUT)
            except _futures.TimeoutError:
                logger.warning(
                    "ai_confirm_prefilter hard-timeout (%ss) for match=%s",
                    _HARD_TIMEOUT, raw.id,
                )
                return None
    except Exception as exc:
        logger.warning("ai_confirm_prefilter failed for match=%s: %s", raw.id, exc)
        return None

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
        c_lower = content.lower()
        if '"fits": true' in c_lower or 'fits:true' in c_lower or 'fits: true' in c_lower:
            return (True, content[:200])
        if '"fits": false' in c_lower or 'fits:false' in c_lower or 'fits: false' in c_lower:
            return (False, content[:200])
        return None
