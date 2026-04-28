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
    }, 200
