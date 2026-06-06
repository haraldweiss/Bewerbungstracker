# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from __future__ import annotations
import json
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from functools import wraps

from api.auth import token_required, admin_required
from models import User, Application, EmailConfirmationToken, ApiCall, AIWordsResearchLog, PlatformProfileRow
from database import db
from sqlalchemy import func
from services.email_service import send_approval_notification, send_confirmation_email
from services.encryption_service import EncryptionService
from auth_service import AuthService

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/users', methods=['GET'])
@token_required
@admin_required
def list_users(user):
    """List all users with admin info"""
    users = User.query.all()
    return {
        'users': [
            {
                'id': u.id,
                'email': u.email,
                'created_at': u.created_at.isoformat(),
                'is_admin': u.is_admin,
                'email_confirmed': u.email_confirmed,
                'is_active': u.is_active,
                'applications_count': len(u.applications)
            }
            for u in users
        ]
    }, 200


@admin_bp.route('/users', methods=['POST'])
@token_required
@admin_required
def create_user(user):
    """Admin: Neuen User anlegen + Bestätigungs-Email versenden.

    Flow:
      1. User wird mit is_active=True, email_confirmed=False angelegt.
      2. EmailConfirmationToken (24h gültig) wird generiert.
      3. Bestätigungs-Email mit Aktivierungslink geht raus.
      4. Login bleibt blockiert bis User den Link klickt → email_confirmed=True.

    Body: {email, password, is_admin? (default false)}
    """
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    is_admin = bool(data.get('is_admin', False))

    if not email or '@' not in email:
        return {'error': 'Gültige Email erforderlich'}, 400
    if not password or len(password) < 8:
        return {'error': 'Passwort mit mindestens 8 Zeichen erforderlich'}, 400

    if User.query.filter_by(email=email).first():
        return {'error': 'Email bereits registriert'}, 400

    try:
        # Envelope-Encryption: per-User-Salt + verschlüsselter DEK
        salt, encrypted_dek, _dek = EncryptionService.create_user_keys(password)
        new_user = User(
            email=email,
            password_hash=AuthService.hash_password(password),
            is_admin=is_admin,
            is_active=True,           # Admin hat User legitimiert
            email_confirmed=False,    # Confirmation-Link blockt Login bis dahin
            encryption_salt=salt,
            encrypted_data_key=encrypted_dek,
        )
        db.session.add(new_user)
        db.session.flush()  # damit user.id gesetzt ist für FK

        # Token + Email
        confirmation_token = secrets.token_urlsafe(32)
        token_record = EmailConfirmationToken(
            token=confirmation_token,
            user_id=new_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(token_record)
        db.session.commit()

        app_url = current_app.config.get('APP_URL', 'https://bewerbungen.wolfinisoftware.de')
        confirmation_link = f"{app_url}/api/auth/confirm-email?token={confirmation_token}"
        email_sent = send_confirmation_email(new_user.email, confirmation_link)

        return {
            'id': new_user.id,
            'email': new_user.email,
            'is_admin': new_user.is_admin,
            'is_active': new_user.is_active,
            'email_confirmed': new_user.email_confirmed,
            'email_sent': email_sent,
            'created_at': new_user.created_at.isoformat(),
            'message': (
                'User angelegt + Bestätigungs-Email versendet.'
                if email_sent
                else 'User angelegt, aber Bestätigungs-Email konnte NICHT versendet werden.'
                     ' Bitte SMTP-Konfiguration prüfen.'
            ),
        }, 201
    except Exception as e:
        db.session.rollback()
        return {'error': f'User-Anlage fehlgeschlagen: {e}'}, 500


@admin_bp.route('/users/<user_id>/approve', methods=['POST'])
@token_required
@admin_required
def approve_user(user, user_id):
    """Approve a user account (activate after email confirmation)"""
    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    if not target_user.email_confirmed:
        return {'error': 'User has not confirmed their email yet'}, 400

    target_user.is_active = True
    db.session.commit()

    # Send approval notification
    send_approval_notification(target_user.email)

    return {
        'message': f'User {target_user.email} approved successfully',
        'email': target_user.email,
        'is_active': target_user.is_active
    }, 200


# ─── Job-Discovery Approval ──────────────────────────────────────────────

@admin_bp.route('/job-discovery-requests', methods=['GET'])
@token_required
@admin_required
def list_job_discovery_requests(user):
    """Liste aller User mit ausstehender Job-Discovery-Aktivierungs-Anfrage.

    Filtert auf: requested_at IS NOT NULL UND noch nicht enabled. Sortiert
    nach requested_at ASC (älteste zuerst).
    """
    pending = (
        User.query
        .filter(User.job_discovery_requested_at.isnot(None))
        .filter(User.job_discovery_enabled.is_(False))
        .order_by(User.job_discovery_requested_at.asc())
        .all()
    )
    return {
        'requests': [
            {
                'user_id': u.id,
                'email': u.email,
                'requested_at': u.job_discovery_requested_at.isoformat(),
                'has_cv': bool(u.cv_data_json),
                'is_active': u.is_active,
                'email_confirmed': u.email_confirmed,
            }
            for u in pending
        ],
        'count': len(pending),
    }, 200


@admin_bp.route('/users/<user_id>/approve-job-discovery', methods=['POST'])
@token_required
@admin_required
def approve_job_discovery(user, user_id):
    """Aktiviert Job-Discovery für einen User (setzt enabled=True).

    Erfordert dass der User die Aktivierung angefragt hat (requested_at gesetzt).
    Idempotent: bereits aktivierte User bekommen 200 zurück.
    """
    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    if not target_user.job_discovery_requested_at:
        return {'error': 'User has not requested Job-Discovery activation'}, 400

    if not target_user.cv_data_json:
        return {'error': 'User hat keinen Lebenslauf hinterlegt — Job-Discovery ohne CV nicht sinnvoll'}, 400

    target_user.job_discovery_enabled = True
    db.session.commit()

    return {
        'message': f'Job-Discovery für {target_user.email} aktiviert',
        'email': target_user.email,
        'job_discovery_enabled': target_user.job_discovery_enabled,
    }, 200


@admin_bp.route('/users/<user_id>/deny-job-discovery', methods=['POST'])
@token_required
@admin_required
def deny_job_discovery(user, user_id):
    """Lehnt eine Aktivierungs-Anfrage ab (setzt requested_at zurück auf NULL).

    User kann später erneut anfragen. Bestehende job_discovery_enabled-Werte
    werden NICHT verändert — Disable-Aktion ist separat.
    """
    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    target_user.job_discovery_requested_at = None
    db.session.commit()

    return {
        'message': f'Job-Discovery-Anfrage von {target_user.email} abgelehnt',
        'email': target_user.email,
    }, 200


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(user, user_id):
    """Delete a user and all their data"""
    if user.id == user_id:
        return {'error': 'Cannot delete yourself'}, 400

    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    db.session.delete(target_user)
    db.session.commit()

    return {'message': f'User {target_user.email} deleted successfully'}, 200


@admin_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@token_required
@admin_required
def reset_password(user, user_id):
    """Generate a temporary password for user"""
    from auth_service import AuthService
    import secrets

    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    # Generate temporary password
    temp_password = secrets.token_urlsafe(16)
    target_user.password_hash = AuthService.hash_password(temp_password)
    db.session.commit()

    return {
        'message': f'Password reset for {target_user.email}',
        'temporary_password': temp_password,
        'note': 'Share this password securely. User should change it on first login.'
    }, 200


@admin_bp.route('/users/<user_id>/applications', methods=['GET'])
@token_required
@admin_required
def get_user_applications(user, user_id):
    """Get all applications for a user"""
    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    applications = Application.query.filter_by(user_id=user_id).all()

    return {
        'email': target_user.email,
        'applications': [
            {
                'id': app.id,
                'company': app.company,
                'position': app.position,
                'status': app.status,
                'applied_date': app.applied_date.isoformat() if app.applied_date else None,
                'created_at': app.created_at.isoformat()
            }
            for app in applications
        ]
    }, 200


@admin_bp.route('/users/<user_id>/promote', methods=['PATCH'])
@token_required
@admin_required
def promote_user(user, user_id):
    """Toggle admin status for a user"""
    if str(user.id) == str(user_id):
        return {'error': 'Cannot change your own admin status'}, 400

    target_user = User.query.get(user_id)
    if not target_user:
        return {'error': 'User not found'}, 404

    # Toggle admin status
    target_user.is_admin = not target_user.is_admin
    db.session.commit()

    action = 'promoted to admin' if target_user.is_admin else 'demoted from admin'
    return {
        'message': f'User {target_user.email} {action}',
        'email': target_user.email,
        'is_admin': target_user.is_admin
    }, 200


@admin_bp.route('/usage-stats', methods=['GET'])
@token_required
@admin_required
def usage_stats(user):
    """Aggregierte AI-Nutzungs-Statistik pro User × Model.

    Query-Param `days`: Zeitraum in Tagen (default 30, max 365). 0 = all-time.

    Response:
      {
        "days": 30,
        "since": "...iso...",
        "rows": [
          {
            "user_id": "...", "email": "...",
            "model": "claude-haiku-4-5", "key_owner": "server",
            "calls": 42, "tokens_in": 12345, "tokens_out": 6789,
            "cost_eur": 0.05, "last_used": "..."
          }, ...
        ],
        "totals_per_user": [
          {"user_id":"...", "email":"...", "calls": 100, "cost_eur": 0.12}
        ]
      }
    """
    try:
        days = int(request.args.get('days', '30'))
    except ValueError:
        days = 30
    days = max(0, min(365, days))

    q = (db.session.query(
            ApiCall.user_id,
            ApiCall.model,
            ApiCall.key_owner,
            func.count(ApiCall.id).label('calls'),
            func.coalesce(func.sum(ApiCall.tokens_in), 0).label('t_in'),
            func.coalesce(func.sum(ApiCall.tokens_out), 0).label('t_out'),
            func.coalesce(func.sum(ApiCall.cost), 0).label('cost'),
            func.max(ApiCall.timestamp).label('last_used'),
        )
        .group_by(ApiCall.user_id, ApiCall.model, ApiCall.key_owner)
    )

    since = None
    if days > 0:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(ApiCall.timestamp >= since)

    rows = q.order_by(func.sum(ApiCall.cost).desc(), func.count(ApiCall.id).desc()).all()

    # Email-Lookup, damit Frontend nicht pro Zeile noch User abfragen muss
    user_ids = list({r.user_id for r in rows})
    emails = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            emails[u.id] = u.email

    detailed = [{
        'user_id': r.user_id,
        'email': emails.get(r.user_id, '?'),
        'model': r.model or '(unbekannt)',
        'key_owner': r.key_owner,
        'calls': int(r.calls),
        'tokens_in': int(r.t_in),
        'tokens_out': int(r.t_out),
        'cost_eur': round(float(r.cost), 4),
        'last_used': r.last_used.isoformat() if r.last_used else None,
    } for r in rows]

    # Summen pro User (für Dashboard-Header)
    per_user = {}
    for d in detailed:
        u = per_user.setdefault(d['user_id'], {
            'user_id': d['user_id'], 'email': d['email'],
            'calls': 0, 'cost_eur': 0.0,
        })
        u['calls'] += d['calls']
        u['cost_eur'] = round(u['cost_eur'] + d['cost_eur'], 4)
    totals = sorted(per_user.values(), key=lambda x: x['cost_eur'], reverse=True)

    return {
        'days': days,
        'since': since.isoformat() if since else None,
        'rows': detailed,
        'totals_per_user': totals,
    }, 200


@admin_bp.get('/ai-words-research/history')
@token_required
@admin_required
def get_research_history(user):
    """List last 10 research runs (admin only)."""
    logs = AIWordsResearchLog.query.order_by(
        AIWordsResearchLog.timestamp.desc()
    ).limit(10).all()

    return jsonify({
        'research_history': [
            {
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'found_total': log.found_total,
                'new_count': log.new_count,
                'new_words': log.new_words or [],
                'sources_checked': log.sources_checked or {},
                'error_message': log.error_message,
            }
            for log in logs
        ]
    }), 200


@admin_bp.get('/ai-words-research/latest')
@token_required
@admin_required
def get_latest_research(user):
    """Get most recent research run (admin only)."""
    log = AIWordsResearchLog.query.order_by(
        AIWordsResearchLog.timestamp.desc()
    ).first()

    if not log:
        return jsonify({'research_run': None}), 200

    return jsonify({
        'research_run': {
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'found_total': log.found_total,
            'new_count': log.new_count,
            'new_words': log.new_words or [],
            'sources_checked': log.sources_checked or {},
            'error_message': log.error_message,
        }
    }), 200


# ---------------------------------------------------------------------------
# URL-Cleanup Admin-Endpoints (Task 5 vom URL-Health-Check-Feature)
# ---------------------------------------------------------------------------
# Workflow:
#   1. /api/jobs/url-health-check (Cron) markiert RawJobs als
#      crawl_status='marked_for_deletion' bei 404/410 oder 3-Strike-Failure.
#   2. Admin reviewed die Kandidaten via list_url_cleanup_candidates und
#      entscheidet pro Job: delete (hard-delete + cascade) oder keep
#      (reset failures + zurueck zu 'active').
#   3. bulk-delete fuer Mass-Cleanup. Filtert intern auf
#      crawl_status='marked_for_deletion', sodass versehentlich
#      uebergebene aktive IDs ignoriert werden.

@admin_bp.get('/url-cleanup-candidates')
@token_required
@admin_required
def list_url_cleanup_candidates(user):
    """Listet alle RawJobs mit crawl_status='marked_for_deletion'.

    Response: {candidates: [{id, url, title, company, location,
                             url_check_status, url_check_failures,
                             url_last_checked_at, source_id,
                             source_name, source_type}, ...]}
    """
    from models import RawJob

    rows = (
        RawJob.query
        .filter(RawJob.crawl_status == 'marked_for_deletion')
        .order_by(RawJob.url_last_checked_at.desc().nullslast())
        .all()
    )
    candidates = []
    for rj in rows:
        src = rj.source  # backref aus JobSource.raw_jobs
        candidates.append({
            'id': rj.id,
            'url': rj.url,
            'title': rj.title,
            'company': rj.company,
            'location': rj.location,
            'url_check_status': rj.url_check_status,
            'url_check_failures': rj.url_check_failures,
            'url_last_checked_at': (
                rj.url_last_checked_at.isoformat()
                if rj.url_last_checked_at else None
            ),
            'source_id': rj.source_id,
            'source_name': src.name if src else None,
            'source_type': src.type if src else None,
        })
    return jsonify({'candidates': candidates}), 200


def _cascade_delete_raw_jobs(raw_job_ids):
    """Loescht JobEmbedding + JobMatch + RawJob fuer eine Liste von IDs.

    SQLAlchemy-FKs auf raw_jobs.id haben kein ON DELETE CASCADE
    (siehe models.py: JobMatch.raw_job_id, JobEmbedding.raw_job_id), darum
    muessen wir explizit cascaden. Reihenfolge: erst Children, dann Parent.
    """
    from models import RawJob, JobMatch, JobEmbedding

    if not raw_job_ids:
        return 0

    # JobEmbedding: ORM-Delete (Model existiert, sauberer als raw SQL)
    JobEmbedding.query.filter(
        JobEmbedding.raw_job_id.in_(raw_job_ids)
    ).delete(synchronize_session=False)

    # JobMatches
    JobMatch.query.filter(
        JobMatch.raw_job_id.in_(raw_job_ids)
    ).delete(synchronize_session=False)

    # RawJob selbst
    deleted = RawJob.query.filter(
        RawJob.id.in_(raw_job_ids)
    ).delete(synchronize_session=False)
    return deleted


@admin_bp.post('/url-cleanup/<int:raw_job_id>/delete')
@token_required
@admin_required
def delete_url_cleanup_candidate(user, raw_job_id):
    """Hard-Delete RawJob + Cascade JobMatch + JobEmbedding.

    Nur erlaubt fuer RawJobs mit crawl_status='marked_for_deletion'.
    """
    from models import RawJob

    rj = RawJob.query.get(raw_job_id)
    if not rj:
        return jsonify({'error': 'RawJob nicht gefunden'}), 404
    if rj.crawl_status != 'marked_for_deletion':
        return jsonify({
            'error': "RawJob nicht marked_for_deletion — bitte zuerst markieren"
        }), 400

    _cascade_delete_raw_jobs([raw_job_id])
    db.session.commit()
    return jsonify({'ok': True, 'deleted_raw_job_id': raw_job_id}), 200


@admin_bp.post('/url-cleanup/<int:raw_job_id>/keep')
@token_required
@admin_required
def keep_url_cleanup_candidate(user, raw_job_id):
    """Un-mark + Reset failures.

    Setzt crawl_status zurueck auf 'raw' (Default) und nullt die
    Failure-Counter, sodass der Job beim naechsten Crawl-Lauf wieder
    normal verarbeitet wird.
    """
    from models import RawJob

    rj = RawJob.query.get(raw_job_id)
    if not rj:
        return jsonify({'error': 'RawJob nicht gefunden'}), 404

    rj.crawl_status = 'raw'
    rj.url_check_failures = 0
    rj.url_check_status = None
    db.session.commit()
    return jsonify({'ok': True, 'raw_job_id': raw_job_id}), 200


@admin_bp.post('/url-cleanup/bulk-delete')
@token_required
@admin_required
def bulk_delete_url_cleanup(user):
    """Mass-Delete fuer eine Liste von raw_job_ids.

    Body: {ids: [int, ...]}

    Es werden NUR Eintraege geloescht, deren crawl_status aktuell
    'marked_for_deletion' ist — versehentlich uebergebene aktive IDs
    werden stillschweigend gefiltert.
    """
    from models import RawJob

    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return jsonify({'error': 'ids muss eine Liste von ints sein'}), 400
    if not ids:
        return jsonify({'ok': True, 'deleted': 0}), 200

    valid_ids = [
        row.id for row in (
            RawJob.query
            .filter(RawJob.id.in_(ids))
            .filter(RawJob.crawl_status == 'marked_for_deletion')
            .all()
        )
    ]
    if not valid_ids:
        return jsonify({'ok': True, 'deleted': 0}), 200

    _cascade_delete_raw_jobs(valid_ids)
    db.session.commit()
    return jsonify({'ok': True, 'deleted': len(valid_ids)}), 200


# ── Platform Profiles ──────────────────────────────────────────────────────

# Slug-Limit: 26 Zeichen (JobSource.type ist String(32), wir reservieren 6 für "_email")
_SLUG_RE = re.compile(r"^[a-z0-9_-]{2,26}$")
_DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.IGNORECASE)


def _validate_payload(payload: dict, partial: bool = False) -> tuple[dict, str | None]:
    """Validate platform-profile payload. Returns (cleaned, error_msg)."""
    from services.job_sources.email_jobs import PROFILES

    cleaned: dict = {}

    if "slug" in payload or not partial:
        slug = (payload.get("slug") or "").strip().lower()
        if not _SLUG_RE.match(slug):
            return {}, "slug muss [a-z0-9_-]{2,26} sein"
        if slug in PROFILES:
            return {}, f"Slug '{slug}' ist reserviert (hardcoded Plattform)"
        cleaned["slug"] = slug

    if "display_name" in payload or not partial:
        name = (payload.get("display_name") or "").strip()
        if not name or len(name) > 120:
            return {}, "display_name muss 1-120 Zeichen sein"
        cleaned["display_name"] = name

    if "domain" in payload or not partial:
        domain = (payload.get("domain") or "").strip().lower()
        if not _DOMAIN_RE.match(domain):
            return {}, "domain muss ein gültiger Hostname sein"
        cleaned["domain"] = domain

    if "subject_must_contain" in payload or not partial:
        smc = payload.get("subject_must_contain") or []
        if not isinstance(smc, list) or not (1 <= len(smc) <= 20):
            return {}, "subject_must_contain muss 1-20 Strings enthalten"
        if any(not isinstance(s, str) or len(s) > 80 for s in smc):
            return {}, "subject_must_contain: Strings ≤80 Zeichen"
        cleaned["subject_must_contain"] = json.dumps(smc)

    if "ai_schema_hint" in payload:
        hint = (payload.get("ai_schema_hint") or "").strip()
        if len(hint) > 2000:
            return {}, "ai_schema_hint ≤2000 Zeichen"
        cleaned["ai_schema_hint"] = hint or None

    if "digest_threshold" in payload:
        try:
            dt = int(payload["digest_threshold"])
            if not (1 <= dt <= 20):
                raise ValueError()
        except (TypeError, ValueError):
            return {}, "digest_threshold muss 1-20 sein"
        cleaned["digest_threshold"] = dt

    if "url_pattern_override" in payload:
        v = (payload.get("url_pattern_override") or "").strip()
        if v:
            if len(v) > 500:
                return {}, "url_pattern_override ≤500 Zeichen"
            try:
                re.compile(v)
            except re.error as exc:
                return {}, f"url_pattern_override ungültig: {exc}"
            cleaned["url_pattern_override"] = v
        else:
            cleaned["url_pattern_override"] = None

    if "from_whitelist_override" in payload:
        v = (payload.get("from_whitelist_override") or "").strip()
        if v:
            if len(v) > 500:
                return {}, "from_whitelist_override ≤500 Zeichen"
            try:
                re.compile(v)
            except re.error as exc:
                return {}, f"from_whitelist_override ungültig: {exc}"
            cleaned["from_whitelist_override"] = v
        else:
            cleaned["from_whitelist_override"] = None

    return cleaned, None


@admin_bp.get('/platforms')
@token_required
@admin_required
def list_platforms(user):
    rows = PlatformProfileRow.query.order_by(PlatformProfileRow.slug).all()
    return jsonify({"platforms": [r.to_dict() for r in rows]}), 200


@admin_bp.post('/platforms')
@token_required
@admin_required
def create_platform(user):
    payload = request.get_json() or {}
    cleaned, err = _validate_payload(payload, partial=False)
    if err:
        return jsonify({"error": err}), 400
    if PlatformProfileRow.query.filter_by(slug=cleaned["slug"]).first():
        return jsonify({"error": f"Slug '{cleaned['slug']}' existiert bereits"}), 400
    dt = cleaned.pop("digest_threshold", 3)
    row = PlatformProfileRow(
        **cleaned,
        digest_threshold=dt,
        created_by_user_id=user.id,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@admin_bp.patch('/platforms/<string:slug>')
@token_required
@admin_required
def update_platform(user, slug):
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if not row:
        return jsonify({"error": "Plattform nicht gefunden"}), 404
    payload = request.get_json() or {}
    if "slug" in payload and payload["slug"] != slug:
        return jsonify({"error": "Slug nicht änderbar"}), 400
    payload.pop("slug", None)
    cleaned, err = _validate_payload(payload, partial=True)
    if err:
        return jsonify({"error": err}), 400
    for k, v in cleaned.items():
        setattr(row, k, v)
    db.session.commit()
    return jsonify(row.to_dict()), 200


@admin_bp.delete('/platforms/<string:slug>')
@token_required
@admin_required
def delete_platform(user, slug):
    from models import JobSource
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if not row:
        return jsonify({"error": "Plattform nicht gefunden"}), 404
    ref_count = JobSource.query.filter_by(type=f"{slug}_email").count()
    if ref_count > 0:
        return jsonify({
            "error": f"Plattform wird von {ref_count} JobSource(s) genutzt"
        }), 409
    db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": slug}), 200
