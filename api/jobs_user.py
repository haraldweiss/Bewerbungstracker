# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""User-facing Job-Discovery Endpoints (JWT-geschützt)."""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

from database import db
from models import JobSource, RawJob, JobMatch, Application
from api.auth import token_required
from services.ssrf_guard import is_url_safe_for_rss
from services import ai_provider_client
from api.jobs_cron import _run_claude_match_for, _user_today_cost_cents, _is_failed_evaluation


jobs_user_bp = Blueprint('jobs_user', __name__, url_prefix='/api/jobs')


def _get_anthropic_client():
    """Liefert einen Anthropic-Client oder None falls API-Key fehlt.

    Eigene Kopie statt Reuse aus jobs_cron — sonst circular-import-Risiko
    bei Test-Mocks via patch("api.jobs_user._get_anthropic_client").
    """
    import os
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic  # lazy import — nicht im venv bei Tests
    return Anthropic(api_key=api_key)


_VALID_TYPES = {
    "rss", "adzuna", "bundesagentur", "arbeitnow",
    "indeed_email", "linkedin_email", "xing_email",
}

# Email-Source-Types, die dieselbe Folder-/Lookback-Validation brauchen
# wie indeed_email — alle nutzen den gleichen IMAP/Apps-Script-Fetch-Pfad
# in services.job_sources.email_jobs.
_EMAIL_SOURCE_TYPES = {"indeed_email", "linkedin_email", "xing_email"}

# Default-Folder pro Email-Source-Type (für leere Configs).
_EMAIL_DEFAULT_FOLDER = {
    "indeed_email": "Indeed",
    "linkedin_email": "[Google Mail]/Alle Nachrichten",
    "xing_email": "[Google Mail]/Alle Nachrichten",
}

# Indeed-Email-Folder-Validation: erlaubt alle druckbaren ASCII-Zeichen
# inkl. Brackets [...] (Gmail-Sonderfolder wie '[Google Mail]/Alle Nachrichten').
# Verbietet: Control-Chars (CR/LF/NULL → IMAP-Injection-Schutz),
# doppelte Anführungszeichen und Backslashes.
_INDEED_FOLDER_RE = re.compile(r'^[^\x00-\x1f\x7f"\\]{1,100}$')


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
        pass
    elif source_type in _EMAIL_SOURCE_TYPES:
        default_folder = _EMAIL_DEFAULT_FOLDER.get(source_type, "INBOX")
        folder = (config or {}).get("folder", default_folder)
        if not isinstance(folder, str) or not _INDEED_FOLDER_RE.match(folder):
            return f"{source_type}-Config: 'folder' fehlt oder enthält ungültige Zeichen"
        lookback = (config or {}).get("lookback_days", 30)
        if not isinstance(lookback, int) or not (1 <= lookback <= 365):
            return f"{source_type}-Config: 'lookback_days' muss 1-365 sein"
    return None


def _serialize_source(s: JobSource, current_user_id: str) -> dict:
    return {
        "id": s.id, "name": s.name, "type": s.type, "config": s.config,
        "enabled": s.enabled, "crawl_interval_min": s.crawl_interval_min,
        "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
        "last_error": s.last_error, "consecutive_failures": s.consecutive_failures,
        "is_global": s.user_id is None,
        "is_own": s.user_id == current_user_id,
    }


@jobs_user_bp.get('/sources')
@token_required
def list_sources(user):
    sources = JobSource.query.filter(
        (JobSource.user_id.is_(None)) | (JobSource.user_id == user.id)
    ).order_by(JobSource.name).all()
    return jsonify({"sources": [_serialize_source(s, user.id) for s in sources]}), 200


@jobs_user_bp.post('/sources')
@token_required
def create_source(user):
    data = request.get_json() or {}
    if data.get("type") not in _VALID_TYPES:
        return jsonify({"error": f"type muss eines von {_VALID_TYPES} sein"}), 400
    if not data.get("name"):
        return jsonify({"error": "name fehlt"}), 400

    err = _validate_config(data["type"], data.get("config") or {})
    if err:
        return jsonify({"error": err}), 400

    src = JobSource(
        user_id=user.id,
        name=data["name"],
        type=data["type"],
        enabled=data.get("enabled", True),
        crawl_interval_min=data.get("crawl_interval_min", 60),
    )
    src.config = data.get("config") or {}
    db.session.add(src)
    db.session.commit()
    return jsonify({"source": _serialize_source(src, user.id)}), 201


@jobs_user_bp.post('/sources/bulk-email')
@token_required
def bulk_email_sources(user):
    """Legt 1–3 Email-Job-Sources auf einen Schlag an.

    Body:
      platforms     (list)  required, ≥1, subset of {indeed, linkedin, xing}
      folder        (str)   default "[Google Mail]/Alle Nachrichten"
      lookback_days (int)   default 30
      limit         (int)   default 100

    Idempotent: existiert für (user, type) bereits eine Source, wird sie
    übersprungen — kein Fehler, kein Duplikat. Antwort enthält nur die
    neu angelegten Sources (`sources` kann leer sein).
    """
    from services.job_sources.email_jobs import PROFILES

    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        return jsonify({"error": "platforms muss eine nicht-leere Liste sein"}), 400
    unknown = [p for p in platforms if p not in PROFILES]
    if unknown:
        return jsonify({"error": f"Unbekannte Plattform(en): {unknown}"}), 400

    folder = data.get("folder") or "[Google Mail]/Alle Nachrichten"
    try:
        lookback_days = int(data.get("lookback_days") or 30)
        limit = int(data.get("limit") or 100)
    except (TypeError, ValueError):
        return jsonify({"error": "lookback_days/limit müssen Integer sein"}), 400

    config = {"folder": folder, "lookback_days": lookback_days, "limit": limit}

    # Validation einmalig — Folder/Lookback gelten für alle drei Email-Typen gleich.
    err = _validate_config("indeed_email", config)
    if err:
        return jsonify({"error": err}), 400

    created: list[JobSource] = []
    for platform in platforms:
        source_type = f"{platform}_email"
        existing = JobSource.query.filter_by(
            user_id=user.id, type=source_type
        ).first()
        if existing is not None:
            continue
        src = JobSource(
            user_id=user.id,
            type=source_type,
            name=f"{PROFILES[platform].source_label} Email",
            enabled=True,
        )
        src.config = config
        db.session.add(src)
        db.session.flush()
        created.append(src)
    db.session.commit()
    return jsonify({
        "sources": [_serialize_source(s, user.id) for s in created],
    }), 201


@jobs_user_bp.patch('/sources/<int:source_id>')
@token_required
def update_source(user, source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
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
    return jsonify({"source": _serialize_source(src, user.id)}), 200


@jobs_user_bp.delete('/sources/<int:source_id>')
@token_required
def delete_source(user, source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(src)
    db.session.commit()
    return ('', 204)


@jobs_user_bp.post('/sources/<int:source_id>/test-crawl')
@token_required
def test_crawl_source(user, source_id: int):
    """Manueller Test-Crawl für eine Quelle."""
    from services.job_sources import get_adapter
    src = JobSource.query.get_or_404(source_id)
    if src.user_id is not None and src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        adapter = get_adapter(src.type, src.config, user=user)
        jobs = adapter.fetch()
        return jsonify({"ok": True, "found_jobs": len(jobs),
                        "sample_titles": [j.title for j in jobs[:5]]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


# ---------------------------------------------------------------------------
# Match-Endpoints
# ---------------------------------------------------------------------------

def _classify_match_origin(m: JobMatch) -> str:
    """Bei dismissed Matches: 'auto' (KI/System) oder 'manual' (User).

    Heuristik:
      - feedback_text starts with 'auto_'  → auto  (z.B. auto_blocked_by_rejection)
      - feedback_text/feedback_reasons set → manual (User hat begründet)
      - prefilter_score < 5 AND kein Feedback → auto (Pre-Filter Score zu niedrig)
      - sonst → manual (User klickte "Verwerfen" ohne Begründung)

    Für status != 'dismissed' returnt '' (uninteressant).
    """
    if m.status != 'dismissed':
        return ''
    txt = (m.feedback_text or '').strip()
    if txt.startswith('auto_'):
        return 'auto'
    has_feedback_reasons = m.feedback_reasons and m.feedback_reasons not in ('', '[]')
    if txt or has_feedback_reasons:
        return 'manual'
    if m.prefilter_score is not None and m.prefilter_score < 5:
        return 'auto'
    return 'manual'


def _serialize_match(m: JobMatch, raw: RawJob, src: JobSource) -> dict:
    # suspicious_reasons ist comma-separated im DB-Feld; Frontend bekommt Liste.
    suspicious_list = []
    if getattr(m, 'suspicious_reasons', None):
        suspicious_list = [r.strip() for r in m.suspicious_reasons.split(',') if r.strip()]
    # feedback_reasons ist JSON-Array (Adaptive-Learning); Frontend bekommt Liste.
    feedback_reasons_list = []
    if getattr(m, 'feedback_reasons', None):
        try:
            import json as _json2
            feedback_reasons_list = _json2.loads(m.feedback_reasons)
            if not isinstance(feedback_reasons_list, list):
                feedback_reasons_list = []
        except (TypeError, ValueError):
            feedback_reasons_list = []
    return {
        "id": m.id,
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
        "prefilter_score": m.prefilter_score,
        "status": m.status,
        "notified_at": m.notified_at.isoformat() if m.notified_at else None,
        "imported_application_id": m.imported_application_id,
        "suspicious_reasons": suspicious_list,
        "feedback_reasons": feedback_reasons_list,
        "feedback_text": m.feedback_text or None,
        "origin": _classify_match_origin(m),  # '', 'manual', oder 'auto'
        "raw_job": {
            "id": raw.id, "title": raw.title, "company": raw.company,
            "location": raw.location, "url": raw.url, "description": raw.description,
            "posted_at": raw.posted_at.isoformat() if raw.posted_at else None,
            "source_name": src.name, "source_id": src.id,
        },
    }


@jobs_user_bp.get('/matches')
@token_required
def list_matches(user):
    min_score = request.args.get('min_score', type=float, default=0)
    min_prefilter_score = request.args.get('min_prefilter_score', type=float, default=0)
    status_filter = request.args.getlist('status') or ['new', 'unbewertet']
    source_id = request.args.get('source_id', type=int)
    q_text = (request.args.get('q') or '').strip().lower()
    limit = min(request.args.get('limit', type=int, default=50), 200)
    offset = request.args.get('offset', type=int, default=0)
    # ?with_feedback=true → nur Matches die einen Grund/Begründung haben
    # (feedback_text gesetzt ODER feedback_reasons-JSON ist nicht leer).
    # Nützlich beim Status='dismissed': sieht nur die mit erklärtem Grund.
    with_feedback = request.args.get('with_feedback', '').lower() in ('1', 'true', 'yes')
    # ?origin=manual|auto: filtert dismissed Matches nach User-Entscheidung
    # vs. System/KI. Heuristik in _classify_match_origin(). '' = alle.
    origin_filter = request.args.get('origin', '').strip().lower()
    # Default: bereits beworbene Stellen (Treffer in Applications-Tabelle)
    # ausblenden. ?include_applied=true zeigt sie wieder an.
    include_applied = (request.args.get('include_applied', '').lower() in ('1', 'true', 'yes'))
    # Reject-Filter: per-User konfigurierbar (Settings → Job-Vorschläge Filter).
    # Query-Param ?include_rejected=true überschreibt für ad-hoc-Debug.
    include_rejected_param = request.args.get('include_rejected', '').lower()
    if include_rejected_param in ('1', 'true', 'yes'):
        include_rejected = True
    elif include_rejected_param in ('0', 'false', 'no'):
        include_rejected = False
    else:
        include_rejected = not user.job_reject_filter_enabled
    rejection_window_days = int(request.args.get(
        'rejection_window_days', user.job_reject_window_days or 180,
    ))

    # 'unbewertet' ist ein Pseudo-Status, kein DB-Wert. Bedeutet:
    # JobMatch ist 'new' aber Claude hat noch keinen match_score vergeben
    # (Pre-Filter hat ggf. prefilter_score gesetzt, Claude-Bewertung steht aus).
    # Echte DB-Statuses sind 'new', 'seen', 'imported', 'dismissed'.
    real_status_filter = [s for s in status_filter if s != 'unbewertet']
    unbewertet_requested = 'unbewertet' in status_filter

    query = (db.session.query(JobMatch, RawJob, JobSource)
             .join(RawJob, RawJob.id == JobMatch.raw_job_id)
             .join(JobSource, JobSource.id == RawJob.source_id)
             .filter(JobMatch.user_id == user.id))

    if unbewertet_requested and real_status_filter:
        # Beide: 'unbewertet' OR andere echte Statuses
        query = query.filter(db.or_(
            JobMatch.status.in_(real_status_filter),
            db.and_(JobMatch.status == 'new', JobMatch.match_score.is_(None)),
        ))
    elif unbewertet_requested:
        # Nur 'unbewertet'
        query = query.filter(JobMatch.status == 'new',
                             JobMatch.match_score.is_(None))
    else:
        query = query.filter(JobMatch.status.in_(real_status_filter or ['new']))

    if min_score > 0:
        query = query.filter(JobMatch.match_score >= min_score)
    if min_prefilter_score > 0:
        query = query.filter(JobMatch.prefilter_score >= min_prefilter_score)
    if source_id:
        query = query.filter(JobSource.id == source_id)
    if q_text:
        query = query.filter(db.or_(
            db.func.lower(RawJob.title).contains(q_text),
            db.func.lower(RawJob.company).contains(q_text),
        ))
    if with_feedback:
        # Nur Matches mit hinterlegtem Grund — feedback_text oder
        # feedback_reasons (JSON-Array, also nicht leer/null).
        query = query.filter(db.or_(
            db.and_(JobMatch.feedback_text.isnot(None), JobMatch.feedback_text != ''),
            db.and_(JobMatch.feedback_reasons.isnot(None), JobMatch.feedback_reasons != '',
                    JobMatch.feedback_reasons != '[]'),
        ))

    if origin_filter in ('auto', 'manual'):
        # 'auto'-Signal (SQL-Spiegel von _classify_match_origin):
        #   feedback_text LIKE 'auto_%'  ODER
        #   (kein Feedback UND prefilter_score < 5)
        auto_signal = db.or_(
            db.and_(JobMatch.feedback_text.isnot(None),
                    JobMatch.feedback_text.like('auto_%')),
            db.and_(
                db.or_(JobMatch.feedback_text.is_(None), JobMatch.feedback_text == ''),
                db.or_(JobMatch.feedback_reasons.is_(None),
                       JobMatch.feedback_reasons == '',
                       JobMatch.feedback_reasons == '[]'),
                JobMatch.prefilter_score.isnot(None),
                JobMatch.prefilter_score < 5,
            ),
        )
        query = query.filter(auto_signal if origin_filter == 'auto' else db.not_(auto_signal))

    # Cross-Check gegen Applications: schon beworben?
    # Match-Heuristik (in dieser Reihenfolge):
    #   (a) RawJob.url == Application.link
    #   (b) lower(company) == lower(Application.company) AND lower(title) == lower(Application.position)
    # Gelöschte Applications zählen nicht — wenn der User eine Bewerbung
    # zurückzieht, taucht der Vorschlag wieder auf.
    if not include_applied:
        applied = (db.session.query(Application.link, Application.company, Application.position)
                   .filter(Application.user_id == user.id, Application.deleted == False)  # noqa: E712
                   .all())
        applied_urls = {a.link for a in applied if a.link}
        applied_pairs = {
            ((a.company or '').strip().lower(), (a.position or '').strip().lower())
            for a in applied if a.company and a.position
        }
        if applied_urls:
            query = query.filter(~RawJob.url.in_(applied_urls))
        if applied_pairs:
            from sqlalchemy import and_, or_, not_
            pair_conds = [
                and_(
                    db.func.lower(db.func.coalesce(RawJob.company, '')) == c,
                    db.func.lower(RawJob.title) == p,
                )
                for (c, p) in applied_pairs
            ]
            query = query.filter(not_(or_(*pair_conds)))

    # Firmen, die in den letzten N Tagen abgelehnt haben, ausblenden.
    # Verwendet status='absage' (deutsche UI) und 'rejected' (englische Aliase).
    # Cutoff bevorzugt applied_date; bei NULL fällt es auf created_at zurück.
    if not include_rejected:
        cutoff_dt = datetime.utcnow() - timedelta(days=rejection_window_days)
        cutoff_date = cutoff_dt.date()
        rejected_companies_q = (
            db.session.query(db.func.lower(Application.company))
            .filter(
                Application.user_id == user.id,
                Application.deleted == False,  # noqa: E712
                Application.status.in_(['absage', 'rejected']),
                Application.company.isnot(None),
                db.or_(
                    Application.applied_date >= cutoff_date,
                    db.and_(Application.applied_date.is_(None),
                            Application.created_at >= cutoff_dt),
                ),
            )
            .distinct()
        )
        rejected_companies = {row[0] for row in rejected_companies_q.all() if row[0]}
        if rejected_companies:
            query = query.filter(
                ~db.func.lower(db.func.coalesce(RawJob.company, '')).in_(rejected_companies)
            )

    total = query.count()
    rows = (query.order_by(JobMatch.match_score.desc().nullslast(),
                           JobMatch.created_at.desc())
                 .offset(offset).limit(limit).all())

    return jsonify({
        "matches": [_serialize_match(m, r, s) for (m, r, s) in rows],
        "total": total, "limit": limit, "offset": offset,
    }), 200


@jobs_user_bp.patch('/matches/<int:match_id>')
@token_required
def update_match(user, match_id: int):
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    new_status = data.get("status")
    if new_status not in ('unbewertet', 'dismissed', 'new'):
        return jsonify({"error": "status muss 'unbewertet'|'dismissed'|'new' sein"}), 400
    m.status = new_status

    # Feedback-Felder (optional) — Adaptive Learning
    from services.job_matching.feedback import (
        validate_reasons, MAX_FEEDBACK_TEXT_CHARS
    )
    import json as _json

    reasons_raw = data.get('feedback_reasons')
    if reasons_raw is not None:
        if not isinstance(reasons_raw, list):
            return jsonify({"error": "feedback_reasons muss eine Liste sein"}), 400
        valid = validate_reasons(reasons_raw)
        m.feedback_reasons = _json.dumps(valid) if valid else None

    text = data.get('feedback_text')
    if text is not None:
        if not isinstance(text, str):
            return jsonify({"error": "feedback_text muss string sein"}), 400
        if len(text) > MAX_FEEDBACK_TEXT_CHARS:
            return jsonify({"error": f"feedback_text max {MAX_FEEDBACK_TEXT_CHARS} Zeichen"}), 400
        m.feedback_text = text.strip() or None

    db.session.commit()

    # Adaptive Learning: Centroid update nach commit
    if new_status in ('dismissed', 'imported'):
        from services.job_matching.learner import update_centroid_for_feedback
        try:
            update_centroid_for_feedback(user, m)
        except Exception as e:
            current_app.logger.warning('Centroid update failed: %s', e)

    return jsonify({"id": m.id, "status": m.status}), 200


@jobs_user_bp.get('/learn-profile')
@token_required
def get_learn_profile(user):
    """Returns Adaptive-Learning Stats des User: samples, top reasons, active status."""
    from services.job_matching.learner import get_learn_profile_stats
    return jsonify(get_learn_profile_stats(user)), 200


@jobs_user_bp.post('/matches/<int:match_id>/import')
@token_required
def import_match(user, match_id: int):
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    raw = RawJob.query.get(m.raw_job_id)
    src = JobSource.query.get(raw.source_id)

    # NEU: Wenn noch nicht bewertet, Claude versuchen (mit Budget-Check)
    budget_skipped = False
    if m.match_score is None:
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            budget_skipped = True
        else:
            client = _get_anthropic_client()
            if client is not None:
                _run_claude_match_for(client, user, m)
                # Wenn Helper False zurückgibt (Claude-Error), bleibt match_score None.
                # Application wird trotzdem angelegt — kein Hard-Fail beim Import.

    score_str = f"{m.match_score:.0f}" if m.match_score is not None else "–"
    if budget_skipped:
        reasoning = "Bewertung übersprungen — Tagesbudget erschöpft"
        missing_str = "–"
    else:
        reasoning = m.match_reasoning or "–"
        missing_str = ', '.join(m.missing_skills) if m.missing_skills else '–'

    note_text = (
        f"Aus Job-Vorschlag importiert (Match-Score {score_str}).\n\n"
        f"Begruendung: {reasoning}\n\n"
        f"Fehlende Skills: {missing_str}\n\n"
        f"Original-Link: {raw.url}"
    )

    # Übertrage alle verfügbaren Felder vom RawJob.
    # applied_date semantisch: Tag an dem der User sich BEWORBEN hat — also
    # heute, wenn er den Vorschlag jetzt importiert. NICHT das Job-Posting-
    # Datum (raw.posted_at), das verwirrt und fehlt bei Email-Imports eh oft.
    application = Application(
        user_id=user.id,
        company=raw.company or "Unbekannt",
        position=raw.title,
        status='beworben',
        applied_date=datetime.utcnow().date(),
        location=raw.location,
        source=src.name if src else None,
        link=raw.url,
        notes=note_text,
    )
    db.session.add(application)
    db.session.flush()

    m.status = 'imported'
    m.imported_application_id = application.id
    db.session.commit()

    # Adaptive Learning: Centroid update nach commit (analog zum PATCH-Endpoint).
    # Lässt den Lern-Mechanismus auch beim regulären Import-Flow greifen.
    from services.job_matching.learner import update_centroid_for_feedback
    try:
        update_centroid_for_feedback(user, m)
    except Exception as e:
        current_app.logger.warning('Centroid update failed: %s', e)

    return jsonify({"application_id": application.id}), 201


@jobs_user_bp.post('/matches/<int:match_id>/score')
@token_required
def score_match(user, match_id: int):
    """Triggert Claude-Match für einen einzelnen Match. Budget-aware.

    Returns:
        200 + {match_score, match_reasoning, missing_skills} bei Erfolg
        200 + existing data, falls match_score schon gesetzt war
        402 wenn Tagesbudget erschöpft
        403 wenn nicht Owner
        404 wenn nicht gefunden
        503 wenn ANTHROPIC_API_KEY fehlt
    """
    m = JobMatch.query.get_or_404(match_id)
    if m.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403

    # Bereits bewertet → existing data zurückgeben (kein Claude-Call).
    # Ausnahme: Failed-Evals aus früheren Runs werden re-evaluiert.
    if m.match_score is not None and not _is_failed_evaluation(m):
        return jsonify({
            "match_score": m.match_score,
            "match_reasoning": m.match_reasoning,
            "missing_skills": m.missing_skills,
        }), 200

    # Budget-Check vor Anthropic-Client-Init
    if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return jsonify({"error": "Tagesbudget für Claude-Bewertungen erschöpft"}), 402

    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key — der ai-provider-service
    # routet selbst zu Claude/Ollama/etc. nach User-Preference.
    if ai_provider_client.is_enabled():
        client = None
    else:
        client = _get_anthropic_client()
        if client is None:
            return jsonify({"error": "Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt"}), 503

    success = _run_claude_match_for(client, user, m)
    if not success:
        db.session.rollback()
        # Nochmal Budget prüfen — kann sich gerade in der Helper-Schleife geändert haben
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            return jsonify({"error": "Tagesbudget für Claude-Bewertungen erschöpft"}), 402
        return jsonify({"error": "Bewertung fehlgeschlagen"}), 500

    db.session.commit()
    # Pro-Task-Override für 'match' liefert das *tatsächlich* genutzte Modell.
    # Fallback auf user.ai_provider/_model nur wenn kein Override gesetzt.
    match_provider, match_model = user.get_model_for('match')
    return jsonify({
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
        # Transient-Info aus _run_match_via_service: tatsächlich genutzter
        # Provider (kann durch Service-Fallback vom Default abweichen) und
        # Model. Frontend zeigt das in der Bulk-Progress-Anzeige.
        "provider_used": getattr(m, '_last_via', None) or match_provider or user.ai_provider,
        "model_used": match_model or user.ai_provider_model,
        "fallback_used": getattr(m, '_last_fallback_used', False),
    }), 200


@jobs_user_bp.post('/matches/score-bulk')
@token_required
def score_match_bulk(user):
    """Bulk-Claude-Match. Stoppt bei Budget-Erschoepfung, returnt Status pro Match.

    Body: {"match_ids": [1, 2, 3]}
    Returns 200 with:
        scored: [{id, match_score}, ...]
        skipped_budget: [id, ...]
        errors: [{id, error}, ...]
        forbidden: [id, ...] (matches, die anderen Usern gehoeren)
        not_found: [id, ...]
    """
    data = request.get_json() or {}
    ids = data.get("match_ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "match_ids muss nicht-leere Liste sein"}), 400

    matches = JobMatch.query.filter(JobMatch.id.in_(ids)).all()
    found_ids = {m.id for m in matches}
    not_found = [i for i in ids if i not in found_ids]

    forbidden = [m.id for m in matches if m.user_id != user.id]
    own = [m for m in matches if m.user_id == user.id]

    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key.
    if ai_provider_client.is_enabled():
        client = None
    else:
        client = _get_anthropic_client()
        if client is None:
            return jsonify({"error": "Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt"}), 503

    scored = []
    skipped_budget = []
    errors = []

    for m in own:
        # Budget-Check vor jedem Match (kann sich mid-loop aendern durch flush in Helper)
        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget.append(m.id)
            continue
        try:
            success = _run_claude_match_for(client, user, m)
            if success:
                scored.append({"id": m.id, "match_score": m.match_score})
            else:
                # Helper returnt False bei drei Gruenden — disambiguieren:
                if m.match_score is not None:
                    # Schon bewertet (idempotent path)
                    scored.append({"id": m.id, "match_score": m.match_score})
                elif _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
                    # Budget mid-call erschoepft
                    skipped_budget.append(m.id)
                else:
                    # Claude-Error (Helper hat schon geloggt)
                    errors.append({"id": m.id, "error": "Claude-Bewertung fehlgeschlagen"})
        except Exception as e:
            errors.append({"id": m.id, "error": str(e)})

    db.session.commit()

    return jsonify({
        "scored": scored,
        "skipped_budget": skipped_budget,
        "errors": errors,
        "forbidden": forbidden,
        "not_found": not_found,
    }), 200


@jobs_user_bp.patch('/matches/bulk')
@token_required
def update_match_bulk(user):
    """Bulk-Statuswechsel (kein Claude). Akzeptiert nur 'seen' und 'dismissed'.

    Body: {"match_ids": [...], "status": "seen" | "dismissed"}
    Returns 200 with: updated, forbidden, not_found
    """
    data = request.get_json() or {}
    ids = data.get("match_ids")
    new_status = data.get("status")

    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "match_ids muss nicht-leere Liste sein"}), 400
    if new_status not in ('unbewertet', 'dismissed'):
        return jsonify({"error": "status muss 'unbewertet' oder 'dismissed' sein"}), 400

    matches = JobMatch.query.filter(JobMatch.id.in_(ids)).all()
    found_ids = {m.id for m in matches}
    not_found = [i for i in ids if i not in found_ids]
    forbidden = []
    updated = 0

    for m in matches:
        if m.user_id != user.id:
            forbidden.append(m.id)
            continue
        m.status = new_status
        updated += 1

    db.session.commit()
    return jsonify({
        "updated": updated,
        "forbidden": forbidden,
        "not_found": not_found,
    }), 200


# ---------------------------------------------------------------------------
# Indeed-Email Import (manueller User-Action)
# ---------------------------------------------------------------------------

_INDEED_AUTO_DISABLE_THRESHOLD = 5

# Apps-Script-Proxy: nur https://script.google.com/macros/s/{id}/(exec|dev) zulassen
# (SSRF-Schutz — kein arbiträrer URL-Fetch durchs Backend).
_APPS_SCRIPT_URL_RE = re.compile(
    r'^https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/[a-z]+(?:\?[^\s]*)?$'
)

# Gmail-API hat ein hartes Tages-Limit (~250 search/Tag bei Consumer-Accounts).
# Cache pro (user_id, url) für 1h, damit Mehrfach-Klicks / Retries die Quota
# nicht killen. In-Memory pro Worker — bei Restart geleert (OK, Cache-Miss
# kostet nur einen Apps-Script-Call).
_APPS_SCRIPT_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_APPS_SCRIPT_CACHE_TTL = 3600.0  # 1 Stunde


def _fetch_apps_script_emails(url: str, user_id: str | None = None,
                              use_cache: bool = True) -> tuple[list[dict], bool]:
    """Server-side GET eines Apps-Script-Web-Endpoints (umgeht Browser-CORS).

    URL-Validation gegen Whitelist (script.google.com/macros/s/…/exec) blockt
    SSRF gegen interne Dienste. Google macht 30x-redirects nach
    googleusercontent.com → wir folgen mit allow_redirects=True.

    Cache: pro (user_id, url) für _APPS_SCRIPT_CACHE_TTL Sekunden. Spart
    Gmail-API-Quota bei wiederholten Imports im selben Zeitfenster.
    Setze use_cache=False für Force-Refresh.

    Returns: (emails_list, cache_hit)
    """
    if not _APPS_SCRIPT_URL_RE.match(url or ''):
        raise ValueError(
            "Apps-Script-URL muss auf https://script.google.com/macros/s/.../exec passen"
        )

    import time
    cache_key = (user_id or '', url)
    now = time.time()

    if use_cache:
        entry = _APPS_SCRIPT_CACHE.get(cache_key)
        if entry and (now - entry[0]) < _APPS_SCRIPT_CACHE_TTL:
            return entry[1], True

    import requests
    try:
        r = requests.get(url, timeout=60, allow_redirects=True)
    except requests.RequestException as exc:
        raise RuntimeError(f"Apps-Script nicht erreichbar: {exc}") from exc

    if r.status_code != 200:
        raise RuntimeError(f"Apps-Script HTTP {r.status_code}")

    ctype = (r.headers.get('Content-Type') or '').lower()
    text = r.text
    if 'json' not in ctype and not text.lstrip().startswith('{'):
        snippet = text[:120].replace('\n', ' ')
        raise RuntimeError(
            f"Apps-Script gibt HTML statt JSON zurück — Deploy-Access falsch? "
            f"(Beginn: {snippet!r})"
        )

    try:
        data = r.json()
    except ValueError as exc:
        raise RuntimeError(f"Apps-Script JSON-Parse-Fehler: {exc}") from exc

    if data.get('status') and data['status'] != 'ok':
        raise RuntimeError(f"Apps-Script-Error: {data.get('error') or data['status']}")

    emails = data.get('emails') if isinstance(data.get('emails'), list) else []
    _APPS_SCRIPT_CACHE[cache_key] = (now, emails)
    return emails, False


def _get_rejected_companies_lower(user_id: str, window_days: int) -> set[str]:
    """Liefert lowercase company-Namen mit Status 'absage' im Reject-Fenster.

    Spiegelt die Filter-Logik von list_matches (Zeile ~258), damit beim Import
    dieselben Companies als "blocked" gekennzeichnet werden wie sie im
    Vorschläge-Listing ausgeblendet wären.
    """
    cutoff_dt = datetime.utcnow() - timedelta(days=window_days)
    cutoff_date = cutoff_dt.date()
    q = (
        db.session.query(db.func.lower(Application.company))
        .filter(
            Application.user_id == user_id,
            Application.deleted == False,  # noqa: E712
            Application.status.in_(['absage', 'rejected']),
            Application.company.isnot(None),
            db.or_(
                Application.applied_date >= cutoff_date,
                db.and_(Application.applied_date.is_(None),
                        Application.created_at >= cutoff_dt),
            ),
        )
        .distinct()
    )
    return {row[0] for row in q.all() if row[0]}


def _create_raw_job_and_match(
    src: JobSource,
    user_id: str,
    job_data: dict,
    match_status: str,
    feedback_text: str | None = None,
) -> tuple[RawJob, JobMatch]:
    """Erstellt RawJob + JobMatch in einer Transaktion. Caller commit()et."""
    url = (job_data.get('url') or '').strip()
    external_id = (job_data.get('external_id') or url or '')[:512]
    raw = RawJob(
        source_id=src.id,
        external_id=external_id,
        title=(job_data.get('title') or '')[:512],
        company=(job_data.get('company') or '')[:255] or None,
        location=(job_data.get('location') or '')[:255] or None,
        url=url[:1024],
        description=(job_data.get('description') or '')[:2000] or None,
        crawl_status='raw',
    )
    raw.raw_payload = job_data.get('raw') or {}
    db.session.add(raw)
    db.session.flush()  # raw.id verfügbar machen

    match = JobMatch(
        raw_job_id=raw.id,
        user_id=user_id,
        status=match_status,
        feedback_text=feedback_text,
    )
    db.session.add(match)
    return raw, match


@jobs_user_bp.post('/sources/<int:source_id>/import-from-email')
@token_required
def import_from_email(user, source_id: int):
    """Fetcht neue Indeed-Job-Empfehlungen aus dem User-IMAP-Folder.

    Ablauf:
    1. Source laden, Ownership prüfen
    2. Adapter fetch() → list[FetchedJob]
    3. URL-Dedup gegen RawJob + Application
    4. Rejection-Window: Companies mit Status='absage' werden als 'blocked'
       markiert (nicht direkt importiert)
    5. Non-blocked → RawJob + JobMatch(status='new') sofort
    6. Blocked → temp zurück an Frontend (User entscheidet via /approve)

    Returns:
        {
          "imported": int,        # direkt erstellte JobMatches
          "blocked": [job_data],  # Companies mit aktiver Absage
          "duplicates": int,      # bereits in DB
          "total_emails": int,    # gefetchte Emails
          "errors": [str]         # parse errors (best-effort)
        }
    """
    from services.job_sources import get_adapter
    from services.job_sources import dedup as _dedup

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if src.type not in _EMAIL_SOURCE_TYPES:
        return jsonify({"error": f"Source ist kein Email-Typ (ist '{src.type}', erwartet einer von {sorted(_EMAIL_SOURCE_TYPES)})"}), 400

    # Modus-Wahl (3-fach):
    #   1) Body {emails:[...]}     → Apps-Script-Mode (Browser hat schon gefetcht)
    #   2) Body {script_url:"..."} → Apps-Script-Proxy-Mode (VPS fetcht, umgeht CORS)
    #   3) Leerer Body             → IMAP-Mode (VPS verbindet direkt zu IMAP)
    payload = request.get_json(silent=True) or {}
    provided_emails = payload.get('emails')
    script_url = payload.get('script_url')
    force_refresh = bool(payload.get('force_refresh'))

    cache_hit = False
    try:
        adapter = get_adapter(src.type, src.config, user=user)
        adapter._source_id_for_tracking = src.id
        if isinstance(provided_emails, list):
            fetched = adapter.parse_emails(provided_emails)
            fetch_mode = 'apps_script'
        elif isinstance(script_url, str) and script_url:
            emails, cache_hit = _fetch_apps_script_emails(
                script_url,
                user_id=user.id,
                use_cache=not force_refresh,
            )
            fetched = adapter.parse_emails(emails)
            fetch_mode = 'apps_script_proxy'
        else:
            fetched = adapter.fetch()
            fetch_mode = 'imap'
    except Exception as e:
        src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
        src.consecutive_failures = (src.consecutive_failures or 0) + 1
        if src.consecutive_failures >= _INDEED_AUTO_DISABLE_THRESHOLD:
            src.enabled = False
        db.session.commit()
        status_code = 503 if src.consecutive_failures < _INDEED_AUTO_DISABLE_THRESHOLD else 502
        return jsonify({
            "error": src.last_error,
            "consecutive_failures": src.consecutive_failures,
            "auto_disabled": not src.enabled,
        }), status_code

    # Erfolg: Counter zurücksetzen
    src.consecutive_failures = 0
    src.last_error = None

    # URL-Dedup
    existing_urls = _dedup.get_existing_job_urls()
    fresh = _dedup.deduplicate(fetched, existing_urls)
    duplicates_count = len(fetched) - len(fresh)

    # Rejection-Window
    window_days = int(user.job_reject_window_days or 180)
    reject_enabled = bool(user.job_reject_filter_enabled)
    rejected_companies = (
        _get_rejected_companies_lower(user.id, window_days) if reject_enabled else set()
    )

    new_for_dialog: list[dict] = []
    blocked_for_dialog: list[dict] = []

    for fjob in fresh:
        company_lower = (fjob.company or '').strip().lower()
        is_blocked = bool(company_lower) and company_lower in rejected_companies
        payload = {
            'title': fjob.title,
            'company': fjob.company,
            'location': fjob.location,
            'url': fjob.url,
            'external_id': fjob.external_id,
            'description': fjob.description,
            'raw': fjob.raw or {},
        }
        if is_blocked:
            blocked_for_dialog.append(payload)
        else:
            new_for_dialog.append(payload)

    # Non-blocked: sofort als RawJob + JobMatch erstellen
    imported_count = 0
    for payload in new_for_dialog:
        _create_raw_job_and_match(src, user.id, payload, match_status='new')
        imported_count += 1

    src.last_crawled_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "imported": imported_count,
        "blocked": blocked_for_dialog,
        "duplicates": duplicates_count,
        "total_emails": len(fetched),
        "rejection_window_days": window_days,
        "reject_filter_enabled": reject_enabled,
        "fetch_mode": fetch_mode,
        "cache_hit": cache_hit,
    }), 200


@jobs_user_bp.post('/sources/<int:source_id>/import-from-email/approve')
@token_required
def approve_email_import(user, source_id: int):
    """Verarbeitet User-Entscheidungen für blocked Jobs.

    Body: { "decisions": [{ "action": "import_as_new"|"skip", "job": {...} }] }

    - "import_as_new": RawJob + JobMatch(status='new') → erscheint in Vorschlägen
    - "skip":          RawJob + JobMatch(status='dismissed',
                       feedback_text='rejection_blocked_skip') → wird beim
                       nächsten Import als URL-Duplicate erkannt und nicht
                       erneut zur Entscheidung vorgelegt.

    Returns: {"imported": N, "skipped": N, "ignored": N}
    """
    from services.job_sources import dedup as _dedup

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if src.type not in _EMAIL_SOURCE_TYPES:
        return jsonify({"error": f"Source ist kein Email-Typ (ist '{src.type}', erwartet einer von {sorted(_EMAIL_SOURCE_TYPES)})"}), 400

    data = request.get_json() or {}
    decisions = data.get('decisions') or []
    if not isinstance(decisions, list):
        return jsonify({"error": "decisions muss eine Liste sein"}), 400

    existing_urls = _dedup.get_existing_job_urls()

    imported = 0
    skipped = 0
    ignored = 0  # malformed entries oder URL-Duplikate

    for d in decisions:
        if not isinstance(d, dict):
            ignored += 1
            continue
        action = d.get('action')
        job = d.get('job') or {}
        url = (job.get('url') or '').strip()
        if not url or not job.get('title'):
            ignored += 1
            continue
        if url in existing_urls:
            ignored += 1
            continue

        if action == 'import_as_new':
            _create_raw_job_and_match(src, user.id, job, match_status='new')
            imported += 1
            existing_urls.add(url)
        elif action == 'skip':
            _create_raw_job_and_match(
                src, user.id, job,
                match_status='dismissed',
                feedback_text='rejection_blocked_skip',
            )
            skipped += 1
            existing_urls.add(url)
        else:
            ignored += 1

    db.session.commit()
    return jsonify({
        "imported": imported,
        "skipped": skipped,
        "ignored": ignored,
    }), 200


@jobs_user_bp.post('/sources/<int:source_id>/train-pattern')
@token_required
def train_pattern(user, source_id):
    """AI-Pattern-Train fuer Email-Source.

    Body (optional):
      sample_size   (int, default 30)
      train_size    (int, default 5)
      min_hit_rate  (float, default 0.40)

    Pipeline: fetch -> ai-train -> compile -> validate -> persist.
    Rate-Limit: 1 Train pro Plattform pro Stunde.
    """
    from services.job_sources import pattern_learner as pl
    from models import LearnedEmailPattern
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

    # Rate-Limit: 1 Train pro Plattform pro Stunde.
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
            user,
            platform=platform,
            folder=src.config.get("folder", "INBOX"),
            lookback_days=int(src.config.get("lookback_days", 30)),
            n=sample_size,
        )
    except RuntimeError as exc:
        return jsonify({"error": f"IMAP-Fetch fehlgeschlagen: {exc}"}), 400
    if len(mails) < train_size + 1:
        return jsonify({
            "error": (
                f"Zu wenig Mails ({len(mails)}) fuer Training "
                f"(mind. {train_size + 1} noetig)."
            )
        }), 400

    train = mails[:train_size]
    test = mails[train_size:]

    try:
        pattern = pl.ai_learn_pattern(user, train_samples=train, platform=platform)
    except RuntimeError as exc:
        return jsonify({"error": f"AI-Train fehlgeschlagen: {exc}"}), 502

    try:
        # Plattform-URL-Pattern (hardcoded) als Constraint einflechten —
        # verhindert dass AI-gelernte url_labels Marketing-Links matchen.
        from services.job_sources.email_jobs import PROFILES
        url_pattern_str = PROFILES[platform].url_pattern.pattern
        compiled = pl.compile_pattern(pattern, url_pattern_str=url_pattern_str)
    except (ValueError, _re.error) as exc:
        return jsonify({"error": f"Pattern-Compile fehlgeschlagen: {exc}"}), 502

    hit_rate, diagnostics = pl.validate_pattern(
        compiled, test, url_check_re=PROFILES[platform].url_pattern,
    )
    if hit_rate < min_hit_rate:
        return jsonify({
            "error": "Hit-Rate unter Schwelle - Pattern nicht aktiviert.",
            "hit_rate": hit_rate,
            "min_hit_rate": min_hit_rate,
            "sample_count": len(test),
            "diagnostics": diagnostics[:10],
        }), 422

    # Persist: alte Patterns deaktivieren + neue als active speichern.
    LearnedEmailPattern.query.filter_by(
        platform=platform, is_active=True
    ).update({"is_active": False})
    new_row = LearnedEmailPattern(
        platform=platform,
        pattern_json=_json.dumps(pattern),
        sample_count=len(test),
        hit_rate=hit_rate,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id,
        is_active=True,
    )
    db.session.add(new_row)
    db.session.commit()

    return jsonify({
        "ok": True,
        "hit_rate": hit_rate,
        "sample_count": len(test),
        "pattern": pattern,
        "example_matches": [d for d in diagnostics if d["matched"]][:3],
    }), 200


@jobs_user_bp.get('/learned-patterns')
@token_required
def list_learned_patterns(user):
    """Listet aktive gelernte Pattern + History-Counts pro Plattform.

    Response: { "patterns": [<row>.to_dict() + {history_count: int}, ...] }
    """
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


@jobs_user_bp.post('/learned-patterns/<string:platform>/rollback')
@token_required
def rollback_pattern(user, platform):
    """Rollback zur naechst-juengeren Pattern-Version fuer die Plattform.

    Idempotent NICHT — jeder Aufruf rotiert eine Generation zurueck.
    Audit-Log via rolled_back_at + rolled_back_by_user_id auf der
    deaktivierten Row.
    """
    from models import LearnedEmailPattern

    current = LearnedEmailPattern.query.filter_by(
        platform=platform, is_active=True,
    ).first()
    if current is None:
        return jsonify({
            "error": "Keine aktive Pattern-Version fuer diese Plattform"
        }), 400
    prev = LearnedEmailPattern.query.filter(
        LearnedEmailPattern.platform == platform,
        LearnedEmailPattern.trained_at < current.trained_at,
    ).order_by(LearnedEmailPattern.trained_at.desc()).first()
    if prev is None:
        return jsonify({
            "error": "Keine aeltere Version vorhanden — kann nicht rollback."
        }), 400

    current.is_active = False
    current.rolled_back_at = datetime.utcnow()
    current.rolled_back_by_user_id = user.id
    # Flush vor dem Re-Activate, sonst kollidiert die partial-unique-index
    # (platform WHERE is_active=1) — beide Rows waeren transient aktiv.
    db.session.flush()
    prev.is_active = True
    db.session.commit()
    return jsonify({
        "ok": True,
        "rolled_back_from": current.to_dict(),
        "restored_pattern": prev.to_dict(),
    }), 200
