"""User-Profil API: Settings + CV.

Beides liegt als JSON-String in `User.settings_json` / `User.cv_data_json`.
Endpoints sind Pass-Through: Frontend bestimmt Struktur, Backend persistiert.
"""
import json
from datetime import datetime

from flask import Blueprint, request

from api.auth import token_required
from database import db


profile_bp = Blueprint('profile', __name__, url_prefix='/api')


def _parse_or_default(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


# ─── Settings ─────────────────────────────────────────────────────────────

@profile_bp.route('/settings', methods=['GET'])
@token_required
def get_settings(user):
    """Liefert die User-Settings als Objekt (leeres Objekt wenn noch nichts gesetzt)."""
    return {'settings': _parse_or_default(user.settings_json, {})}, 200


@profile_bp.route('/settings', methods=['PUT'])
@token_required
def update_settings(user):
    """Komplettes Settings-Objekt überschreiben.

    Body: beliebiges JSON-Objekt – wird as-is persistiert. Frontend kennt
    die Struktur (keywords, ghostingDays, emailImport*, push-Notifications,
    notify-Filter etc.).
    """
    data = request.get_json()
    if data is None:
        return {'error': 'JSON-Body erforderlich'}, 400
    if not isinstance(data, dict):
        return {'error': 'Body muss ein JSON-Objekt sein'}, 400

    user.settings_json = json.dumps(data)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    return {'settings': data, 'updated_at': user.updated_at.isoformat()}, 200


@profile_bp.route('/settings', methods=['PATCH'])
@token_required
def patch_settings(user):
    """Settings partial-update: nur die übergebenen Keys werden überschrieben."""
    data = request.get_json()
    if not isinstance(data, dict):
        return {'error': 'Body muss ein JSON-Objekt sein'}, 400

    current = _parse_or_default(user.settings_json, {})
    current.update(data)
    user.settings_json = json.dumps(current)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    return {'settings': current, 'updated_at': user.updated_at.isoformat()}, 200


# ─── CV (Lebenslauf) ──────────────────────────────────────────────────────

@profile_bp.route('/profile/cv', methods=['GET'])
@token_required
def get_cv(user):
    """Liefert die CV-Daten als Objekt (leeres Objekt wenn noch nichts gesetzt)."""
    return {'cv': _parse_or_default(user.cv_data_json, {})}, 200


@profile_bp.route('/profile/cv', methods=['PUT'])
@token_required
def update_cv(user):
    """CV-Objekt komplett überschreiben.

    Body: {cv: {...}, comparisons: [...]} (oder beliebiges JSON-Objekt –
    Frontend bestimmt Schema).

    Im Response-Feld `is_first_cv_upload` informiert das Backend das Frontend,
    ob der Job-Discovery-Aktivierungs-Modal angezeigt werden soll (true wenn
    der User bislang keine CV-Daten hatte UND noch nicht nach Aktivierung
    gefragt hat UND nicht schon aktiviert ist).
    """
    data = request.get_json()
    if data is None:
        return {'error': 'JSON-Body erforderlich'}, 400
    if not isinstance(data, dict):
        return {'error': 'Body muss ein JSON-Objekt sein'}, 400

    is_first_cv_upload = (
        not user.cv_data_json
        and not user.job_discovery_requested_at
        and not user.job_discovery_enabled
    )

    user.cv_data_json = json.dumps(data)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    return {
        'cv': data,
        'updated_at': user.updated_at.isoformat(),
        'is_first_cv_upload': is_first_cv_upload,
    }, 200


# ─── Job-Discovery Aktivierungs-Anfrage ───────────────────────────────────

@profile_bp.route('/profile/job-discovery/request', methods=['POST'])
@token_required
def request_job_discovery(user):
    """User fragt Aktivierung der automatischen Job-Suche an.

    Idempotent: bereits gestellte Anfragen werden nicht überschrieben (das
    erste requested_at bleibt erhalten — relevant für Audit/Statistik).
    Bereits aktivierte User bekommen 200 mit Status zurück.
    """
    if not user.job_discovery_enabled and not user.job_discovery_requested_at:
        user.job_discovery_requested_at = datetime.utcnow()
        db.session.commit()

    return {
        'enabled': user.job_discovery_enabled,
        'requested_at': user.job_discovery_requested_at.isoformat() if user.job_discovery_requested_at else None,
        'status': (
            'enabled' if user.job_discovery_enabled
            else ('pending_approval' if user.job_discovery_requested_at else 'not_requested')
        ),
    }, 200


@profile_bp.route('/profile/job-discovery/status', methods=['GET'])
@token_required
def get_job_discovery_status(user):
    """Liefert den aktuellen Aktivierungs-Status für das Frontend."""
    return {
        'enabled': user.job_discovery_enabled,
        'requested_at': user.job_discovery_requested_at.isoformat() if user.job_discovery_requested_at else None,
        'status': (
            'enabled' if user.job_discovery_enabled
            else ('pending_approval' if user.job_discovery_requested_at else 'not_requested')
        ),
        # Aktuelle Filter zurückgeben damit Settings-UI sie laden kann.
        'filters': {
            'job_region_filter': user.job_region_filter,
            'job_language_filter': user.job_language_filter,
            'job_notification_threshold': user.job_notification_threshold,
        },
    }, 200


@profile_bp.route('/profile/job-discovery/filters', methods=['PATCH'])
@token_required
def update_job_discovery_filters(user):
    """User-Filter für Job-Vorschläge aktualisieren.

    Akzeptierte Felder (alle optional, partial-update):
        - job_region_filter: dict | null
            { plz_prefixes: ["44","97"], remote_ok: bool, employment_types: [...] }
            oder null = alle Standorte/Anstellungsarten akzeptieren.
        - job_language_filter: ["de", "en"]
        - job_notification_threshold: int (50-95)
    """
    data = request.get_json() or {}

    if 'job_region_filter' in data:
        rf = data['job_region_filter']
        if rf is not None and not isinstance(rf, dict):
            return {'error': 'job_region_filter muss dict oder null sein'}, 400
        # PLZ-Prefixe sanity-check (3-stellige Strings vermeiden Spam)
        if isinstance(rf, dict):
            prefixes = rf.get('plz_prefixes') or []
            if not isinstance(prefixes, list) or any(not isinstance(p, str) for p in prefixes):
                return {'error': 'plz_prefixes muss list of strings sein'}, 400
        user.job_region_filter = rf

    if 'job_language_filter' in data:
        lf = data['job_language_filter']
        if not isinstance(lf, list) or any(not isinstance(l, str) for l in lf):
            return {'error': 'job_language_filter muss list of strings sein'}, 400
        user.job_language_filter = lf

    if 'job_notification_threshold' in data:
        try:
            t = int(data['job_notification_threshold'])
            if not (0 <= t <= 100):
                raise ValueError
            user.job_notification_threshold = t
        except (TypeError, ValueError):
            return {'error': 'job_notification_threshold muss int 0-100 sein'}, 400

    user.updated_at = datetime.utcnow()
    db.session.commit()

    return {
        'job_region_filter': user.job_region_filter,
        'job_language_filter': user.job_language_filter,
        'job_notification_threshold': user.job_notification_threshold,
    }, 200
