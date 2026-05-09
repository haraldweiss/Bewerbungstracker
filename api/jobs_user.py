# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""User-facing Job-Discovery Endpoints (JWT-geschützt)."""

from __future__ import annotations
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

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
        pass
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
        adapter = get_adapter(src.type, src.config)
        jobs = adapter.fetch()
        return jsonify({"ok": True, "found_jobs": len(jobs),
                        "sample_titles": [j.title for j in jobs[:5]]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


# ---------------------------------------------------------------------------
# Match-Endpoints
# ---------------------------------------------------------------------------

def _serialize_match(m: JobMatch, raw: RawJob, src: JobSource) -> dict:
    # suspicious_reasons ist comma-separated im DB-Feld; Frontend bekommt Liste.
    suspicious_list = []
    if getattr(m, 'suspicious_reasons', None):
        suspicious_list = [r.strip() for r in m.suspicious_reasons.split(',') if r.strip()]
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
    status_filter = request.args.getlist('status') or ['new']
    source_id = request.args.get('source_id', type=int)
    q_text = (request.args.get('q') or '').strip().lower()
    limit = min(request.args.get('limit', type=int, default=50), 200)
    offset = request.args.get('offset', type=int, default=0)
    # Default: bereits beworbene Stellen (Treffer in Applications-Tabelle)
    # ausblenden. ?include_applied=true zeigt sie wieder an.
    include_applied = (request.args.get('include_applied', '').lower() in ('1', 'true', 'yes'))
    # Default: Firmen die in den letzten 6 Monaten abgelehnt haben werden auch
    # ausgeblendet — keine Mehrfach-Bewerbung kurz nach Absage.
    include_rejected = (request.args.get('include_rejected', '').lower() in ('1', 'true', 'yes'))
    rejection_window_days = int(request.args.get('rejection_window_days', '180'))

    query = (db.session.query(JobMatch, RawJob, JobSource)
             .join(RawJob, RawJob.id == JobMatch.raw_job_id)
             .join(JobSource, JobSource.id == RawJob.source_id)
             .filter(JobMatch.user_id == user.id,
                     JobMatch.status.in_(status_filter)))

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
    if new_status not in ('seen', 'dismissed', 'new'):
        return jsonify({"error": "status muss 'seen'|'dismissed'|'new' sein"}), 400
    m.status = new_status
    db.session.commit()
    return jsonify({"id": m.id, "status": m.status}), 200


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

    # Übertrage alle verfügbaren Felder vom RawJob
    application = Application(
        user_id=user.id,
        company=raw.company or "Unbekannt",
        position=raw.title,
        status='beworben',
        applied_date=raw.posted_at.date() if raw.posted_at else None,
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
    return jsonify({
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
        # Transient-Info aus _run_match_via_service: tatsächlich genutzter
        # Provider (kann durch Service-Fallback vom Default abweichen) und
        # Model. Frontend zeigt das in der Bulk-Progress-Anzeige.
        "provider_used": getattr(m, '_last_via', None) or user.ai_provider,
        "model_used": user.ai_provider_model,
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
    if new_status not in ('seen', 'dismissed'):
        return jsonify({"error": "status muss 'seen' oder 'dismissed' sein"}), 400

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
