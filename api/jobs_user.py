# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""User-facing Job-Discovery Endpoints (JWT-geschützt)."""

from __future__ import annotations
from __future__ import annotations
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

from database import db
from models import JobSource, RawJob, JobMatch, Application
from api.auth import token_required
from services.ssrf_guard import is_url_safe_for_rss
from services import ai_provider_client
from services.ai_provider_client import AIProviderQueuedError
from api.jobs_cron import _run_claude_match_for, _is_failed_evaluation
from services.job_matching.claude_utils import _get_anthropic_client
from services import cost_tracker


jobs_user_bp = Blueprint('jobs_user', __name__, url_prefix='/api/jobs')


# Statische Non-Email-Types (RSS, API-basiert). Email-Types werden
# dynamisch via get_profile aufgelöst (hardcoded PROFILES + DB-Plattformen).
_NON_EMAIL_TYPES = {"rss", "adzuna", "bundesagentur", "arbeitnow"}


def _is_valid_source_type(source_type: str) -> bool:
    """True wenn source_type ein bekannter Adapter-Type ist.

    Für *_email-Types wird via get_profile geprüft — deckt hardcoded
    PROFILES + DB-Tabelle platform_profiles ab.
    """
    if source_type in _NON_EMAIL_TYPES:
        return True
    if source_type.endswith("_email"):
        from services.job_sources.email_jobs import get_profile
        slug = source_type[:-len("_email")]
        try:
            get_profile(slug)
            return True
        except KeyError:
            return False
    return False


def _is_email_source_type(source_type: str) -> bool:
    """True wenn source_type ein Email-Adapter ist (egal ob hardcoded oder DB)."""
    if not source_type.endswith("_email"):
        return False
    from services.job_sources.email_jobs import get_profile
    slug = source_type[:-len("_email")]
    try:
        get_profile(slug)
        return True
    except KeyError:
        return False


def _email_default_folder(source_type: str) -> str:
    """Default-Folder pro Email-Source-Type. INBOX als Fallback.

    Hardcoded defaults für historische Sources (für UX-Konsistenz mit
    bestehenden Setups — der User hat möglicherweise diese Folder schon
    in seinem Mail-Account angelegt).
    """
    defaults = {
        "indeed_email": "Indeed",
        "linkedin_email": "[Google Mail]/Alle Nachrichten",
        "xing_email": "[Google Mail]/Alle Nachrichten",
    }
    return defaults.get(source_type, "INBOX")

# Indeed-Email-Folder-Validation: erlaubt alle druckbaren ASCII-Zeichen
# inkl. Brackets [...] (Gmail-Sonderfolder wie '[Google Mail]/Alle Nachrichten').
# Verbietet: Control-Chars (CR/LF/NULL → IMAP-Injection-Schutz),
# doppelte Anführungszeichen und Backslashes.
_INDEED_FOLDER_RE = re.compile(r'^[^\x00-\x1f\x7f"\\]{1,100}$')

from services.email_import_utils import (
    fetch_apps_script_emails,
    get_rejected_companies_lower,
    create_raw_job_and_match,
    normalize_company,
)


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
    elif _is_email_source_type(source_type):
        default_folder = _email_default_folder(source_type)
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
    if not _is_valid_source_type(data.get("type", "")):
        return jsonify({"error": f"type '{data.get('type')}' ist nicht zugelassen"}), 400
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
    from services.job_sources.email_jobs import PROFILES, get_profile

    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        return jsonify({"error": "platforms muss eine nicht-leere Liste sein"}), 400
    unknown = []
    for p in platforms:
        try:
            get_profile(p)
        except KeyError:
            unknown.append(p)
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
            name=f"{get_profile(platform).source_label} Email",
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

# Bekannte System-/KI-feedback_text-Codes — alle Auto-Dismisses landen hier.
# Wird sowohl von _classify_match_origin() als auch vom SQL-Origin-Filter
# weiter unten genutzt. Wenn neue Auto-Codes hinzukommen → hier ergänzen.
AUTO_FEEDBACK_CODES = frozenset({
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


def _classify_match_origin(m: JobMatch) -> str:
    """Bei dismissed Matches: 'auto' (KI/System) oder 'manual' (User).

    Heuristik:
      - feedback_text in AUTO_FEEDBACK_CODES   → auto (System-Marker)
      - feedback_text starts with 'auto_'      → auto (legacy + zukünftige)
      - feedback_text/feedback_reasons sonst   → manual (User hat begründet)
      - prefilter_score < 5 AND kein Feedback  → auto (Pre-Filter Score zu niedrig)
      - sonst → manual (User klickte "Verwerfen" ohne Begründung)

    Für status != 'dismissed' returnt '' (uninteressant).
    """
    if m.status != 'dismissed':
        return ''
    txt = (m.feedback_text or '').strip()
    if txt in AUTO_FEEDBACK_CODES or txt.startswith('auto_'):
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
    # Application-Status auflösen wenn JobMatch übernommen wurde — sonst
    # weiss das Frontend nicht ob die Bewerbung laeuft / Antwort / Absage.
    application_status = None
    if m.imported_application_id:
        try:
            app_row = Application.query.get(m.imported_application_id)
            if app_row and not app_row.deleted:
                application_status = app_row.status
        except Exception:
            application_status = None
    return {
        "id": m.id,
        "match_score": m.match_score,
        "match_reasoning": m.match_reasoning,
        "missing_skills": m.missing_skills,
        "prefilter_score": m.prefilter_score,
        "status": m.status,
        "notified_at": m.notified_at.isoformat() if m.notified_at else None,
        "imported_application_id": m.imported_application_id,
        "application_status": application_status,
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
    # Ausnahme: wenn 'imported' im status_filter → implizit True, sonst
    # waere Status='Uebernommen' immer leer (imported = hat Application,
    # also wird normalerweise vom Filter ausgeschlossen).
    include_applied = (request.args.get('include_applied', '').lower() in ('1', 'true', 'yes'))
    if 'imported' in status_filter:
        include_applied = True
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
        #   feedback_text in AUTO_FEEDBACK_CODES ODER
        #   feedback_text LIKE 'auto_%' (legacy/future) ODER
        #   (kein Feedback UND prefilter_score < 5)
        auto_signal = db.or_(
            JobMatch.feedback_text.in_(AUTO_FEEDBACK_CODES),
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
    # Reject-Set ist via normalize_company() normalisiert (Rechtsformen-Strip),
    # damit "Signal Iduna" auch "Signal Iduna Group AG" matcht.
    # SQL-Filter fängt die exact-lower-Matches ab (z.B. wenn beide ohne Suffix),
    # damit `total` und Pagination stimmen. Python-Post-Filter fängt die
    # Suffix-Varianten ab — SQLite kann den Strip nicht im Filter.
    rejected_companies_normalized: set[str] = set()
    if not include_rejected:
        rejected_companies_normalized = get_rejected_companies_lower(
            user.id, rejection_window_days,
        )
        if rejected_companies_normalized:
            query = query.filter(
                ~db.func.lower(db.func.coalesce(RawJob.company, '')).in_(
                    rejected_companies_normalized
                )
            )

    total = query.count()
    rows = (query.order_by(JobMatch.match_score.desc().nullslast(),
                           JobMatch.created_at.desc())
                 .offset(offset).limit(limit).all())
    if rejected_companies_normalized:
        rows = [
            row for row in rows
            if normalize_company(row[1].company) not in rejected_companies_normalized
        ]

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

    # Quick-Action (Phase 1): triggert Folgeaktionen + setzt status='dismissed'
    quick_action = data.get('quick_action')
    if quick_action is not None:
        from services.job_matching.quick_actions import (
            apply_quick_action, FEEDBACK_TEXT_BY_ACTION, QuickActionError,
        )
        raw = RawJob.query.get(m.raw_job_id)
        if raw is None:
            return jsonify({"error": "RawJob nicht gefunden"}), 500
        try:
            apply_quick_action(
                user=user, match=m, raw=raw,
                action=quick_action,
                job_type=data.get('job_type'),
            )
        except QuickActionError as exc:
            return jsonify({"error": str(exc)}), 400
        m.status = 'dismissed'
        m.feedback_text = FEEDBACK_TEXT_BY_ACTION[quick_action]
        db.session.commit()
        return jsonify({"id": m.id, "status": m.status}), 200

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
        if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
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

    # raw.url ist bei Email-Quellen oft ein Tracking-/Redirect-Link
    # (click.stepstone.de, linkedin.com/comm/..., cts.indeed.com). Für die
    # Bewerbung wollen wir den ECHTEN Stellenlink. Best-effort, Fallback = raw.url.
    from services.job_sources.url_resolver import resolve_original_url
    original_link = resolve_original_url(raw.url)

    note_text = (
        f"Aus Job-Vorschlag importiert (Match-Score {score_str}).\n\n"
        f"Begruendung: {reasoning}\n\n"
        f"Fehlende Skills: {missing_str}\n\n"
        f"Original-Link: {original_link}"
    )

    # Duplikat-Prüfung: gleiche Firma + Position (case-insensitive)
    existing_app = db.session.query(Application.id).filter(
        Application.user_id == user.id,
        Application.deleted == False,
        db.func.lower(Application.company) == db.func.lower(raw.company or ''),
        db.func.lower(Application.position) == db.func.lower(raw.title or ''),
    ).first()
    if existing_app:
        return jsonify({'error': 'Bewerbung existiert bereits', 'existing_id': existing_app[0]}), 409

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
        link=original_link,
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
    if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
        return jsonify({"error": "Tagesbudget für Claude-Bewertungen erschöpft"}), 402

    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key — der ai-provider-service
    # routet selbst zu Claude/Ollama/etc. nach User-Preference.
    if ai_provider_client.is_enabled():
        client = None
    else:
        client = _get_anthropic_client()
        if client is None:
            return jsonify({"error": "Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt"}), 503

    try:
        success = _run_claude_match_for(client, user, m)
    except AIProviderQueuedError:
        db.session.rollback()
        return jsonify({"queued": True, "message": "Bewertung in Warteschlange — wird automatisch verarbeitet"}), 202

    if not success:
        db.session.rollback()
        # Nochmal Budget prüfen — kann sich gerade in der Helper-Schleife geändert haben
        if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
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
    """Enqueued einen claude_match_bulk-Task. Frontend pollt GET /api/tasks/<id>.

    Body: {"match_ids": [1, 2, 3]}
    Returns 202 + {"task_id", "status"}.

    Hintergrund: Bulk-Loop iteriert N Matches, jeder feuert einen Claude-Call (~5-10s).
    Bei N=30 sind das 150-300s — überschreitet den 240s gunicorn-Timeout und erzeugt
    502-Fehler. Daher asynchron via Task-Queue (analog P2 import-from-email).
    """
    from services.tasks.queue import enqueue_task

    data = request.get_json() or {}
    ids = data.get("match_ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "match_ids muss nicht-leere Liste sein"}), 400

    task_id = enqueue_task('claude_match_bulk', user.id, {
        'user_id': user.id,
        'match_ids': ids,
    })
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


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




@jobs_user_bp.post('/sources/<int:source_id>/import-from-email')
@token_required
def import_from_email(user, source_id: int):
    """Enqueued einen email_import-Task und returnt 202 + task_id.

    Frontend pollt anschließend GET /api/tasks/<id>. Die eigentliche
    Logik lebt in services/tasks/handlers/email_import.py.
    """
    from services.tasks.queue import enqueue_task

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if not _is_email_source_type(src.type):
        return jsonify({"error": f"Source ist kein Email-Typ (ist '{src.type}')"}), 400

    payload = request.get_json(silent=True) or {}
    task_payload = {
        'user_id': user.id,
        'source_id': src.id,
        'emails': payload.get('emails'),
        'script_url': payload.get('script_url'),
        'force_refresh': bool(payload.get('force_refresh')),
    }
    task_id = enqueue_task('email_import', user.id, task_payload)
    return jsonify({
        'task_id': task_id,
        'status': 'queued',
    }), 202


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
    if not _is_email_source_type(src.type):
        return jsonify({"error": f"Source ist kein Email-Typ (ist '{src.type}')"}), 400

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
            create_raw_job_and_match(src, user.id, job, match_status='new')
            imported += 1
            existing_urls.add(url)
        elif action == 'skip':
            create_raw_job_and_match(
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
    """AI-Pattern-Train fuer Email-Source (async via Task-Queue).

    Body (optional):
      sample_size   (int, default 30)
      train_size    (int, default 5)
      min_hit_rate  (float, default 0.40)

    Frueh-Checks (403/400/429) bleiben synchron. Der langsame Teil
    (IMAP-Fetch + AI-Train + Validate + Persist) laeuft im Task-Worker.
    Rate-Limit: 1 Train pro Plattform pro Stunde.
    """
    from models import LearnedEmailPattern
    from services.tasks.queue import enqueue_task

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if not _is_email_source_type(src.type):
        return jsonify({"error": "Source ist kein Email-Typ"}), 400

    platform = src.type.removesuffix("_email")
    data = request.get_json(silent=True) or {}
    sample_size = int(data.get("sample_size") or 30)
    train_size = int(data.get("train_size") or 5)
    min_hit_rate = float(data.get("min_hit_rate") or 0.40)

    # Rate-Limit: 1 erfolgreicher Train pro Plattform pro Stunde.
    # Fehlerhafte Trainings zaehlen NICHT zum Rate-Limit.
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent = LearnedEmailPattern.query.filter(
        LearnedEmailPattern.platform == platform,
        LearnedEmailPattern.trained_at > one_hour_ago,
        LearnedEmailPattern.is_active == True,  # Only count successful trainings
    ).first()
    if recent is not None:
        return jsonify({
            "error": "Rate-Limit: max 1 Pattern-Train pro Plattform pro Stunde.",
            "last_trained_at": recent.trained_at.isoformat(),
        }), 429

    task_id = enqueue_task('pattern_learner_train', user.id, {
        'user_id': user.id,
        'source_id': src.id,
        'sample_size': sample_size,
        'train_size': train_size,
        'min_hit_rate': min_hit_rate,
    })
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


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
