# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""User-Profil API: Settings + CV.

Beides liegt als JSON-String in `User.settings_json` / `User.cv_data_json`.
Endpoints sind Pass-Through: Frontend bestimmt Struktur, Backend persistiert.
"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request

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
            'job_reject_filter_enabled': user.job_reject_filter_enabled,
            'job_reject_window_days': user.job_reject_window_days,
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

    if 'job_reject_filter_enabled' in data:
        user.job_reject_filter_enabled = bool(data['job_reject_filter_enabled'])

    if 'job_reject_window_days' in data:
        try:
            d = int(data['job_reject_window_days'])
            if not (0 < d <= 730):  # max 2 Jahre, untere Grenze >0
                raise ValueError
            user.job_reject_window_days = d
        except (TypeError, ValueError):
            return {'error': 'job_reject_window_days muss int 1..730 sein'}, 400

    user.updated_at = datetime.utcnow()
    db.session.commit()

    return {
        'job_region_filter': user.job_region_filter,
        'job_language_filter': user.job_language_filter,
        'job_notification_threshold': user.job_notification_threshold,
        'job_reject_filter_enabled': user.job_reject_filter_enabled,
        'job_reject_window_days': user.job_reject_window_days,
    }, 200


# ─── Pro-Task-Modell-Overrides ───────────────────────────────────────────────
import json as _profile_json

VALID_FEATURES = {'match', 'cover_letter', 'email_analyse', 'cv_summarize'}
VALID_PROVIDERS = {'claude', 'ollama', 'openai', 'mammouth', 'custom'}


@profile_bp.get('/profile/feature-models')
@token_required
def get_feature_models(user):
    """Liefert Standard-Modell + aktuelle Pro-Task-Overrides."""
    try:
        overrides = _profile_json.loads(user.feature_model_overrides or '{}')
    except (ValueError, TypeError):
        overrides = {}
    return jsonify({
        'standard': {
            'provider': user.ai_provider,
            'model': user.ai_provider_model,
        },
        'overrides': overrides,
    }), 200


@profile_bp.patch('/profile/feature-models')
@token_required
def update_feature_models(user):
    """Update Pro-Task-Overrides. Body: {overrides: {feature: {provider, model} | null}}."""
    data = request.get_json() or {}
    overrides = data.get('overrides')

    if not isinstance(overrides, dict):
        return jsonify({'error': 'overrides muss ein Object sein'}), 400

    for feat, cfg in overrides.items():
        if feat not in VALID_FEATURES:
            return jsonify({'error': f'Unbekanntes Feature: {feat}'}), 400
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            return jsonify({'error': f'{feat}: muss Object oder null sein'}), 400
        provider = cfg.get('provider')
        if provider and provider not in VALID_PROVIDERS:
            return jsonify({'error': f'{feat}: unbekannter Provider {provider}'}), 400

    # Normalisierung: null-Werte rausfiltern, leere Provider-Strings rausfiltern
    clean = {}
    for feat, cfg in overrides.items():
        if cfg is None or not isinstance(cfg, dict):
            continue
        if not cfg.get('provider'):
            continue
        clean[feat] = {
            'provider': cfg['provider'],
            'model': cfg.get('model') or None,
        }

    user.feature_model_overrides = _profile_json.dumps(clean, ensure_ascii=False) if clean else None
    db.session.commit()
    return jsonify({'status': 'updated', 'overrides': clean}), 200


# ─── IMAP-Credentials (für Server-side Indeed-Email-Import) ─────────────────
#
# Frontend-Email-Tracking nutzt eigene localStorage-Credentials gegen den
# Mac-IMAP-Proxy (headers-only). DAVON UNABHÄNGIG: hier landen die Credentials
# für Server-side IMAP-Connects (z.B. IndeedEmailAdapter mit full-body fetch).
# Password wird Fernet-encrypted (encryption_service / IMAPCredentialManager).


@profile_bp.get('/profile/imap')
@token_required
def get_imap_status(user):
    """Returns ob IMAP-Credentials für den Server konfiguriert sind.

    NEVER returnt das Passwort — nur ob es gesetzt ist.
    """
    return jsonify({
        "host": user.imap_host or "",
        "user": user.imap_user or "",
        "configured": bool(user.imap_password_encrypted),
    }), 200


@profile_bp.post('/profile/imap')
@token_required
def set_imap_credentials(user):
    """Speichert/aktualisiert IMAP-Credentials für den Server.

    Body: { host, user, password }. Password wird encrypted in DB.
    """
    from auth_service import AuthService
    data = request.get_json() or {}
    host = (data.get('host') or '').strip()
    imap_user = (data.get('user') or '').strip()
    password = data.get('password') or ''

    if not host or not imap_user or not password:
        return jsonify({"error": "host, user, password sind Pflicht"}), 400

    # Light-weight Validation gegen offensichtliche Tippfehler
    if len(host) > 255 or len(imap_user) > 255 or len(password) > 1024:
        return jsonify({"error": "host/user/password zu lang"}), 400

    success, msg = AuthService.register_imap_credentials(user.id, host, imap_user, password)
    if not success:
        return jsonify({"error": msg}), 500

    return jsonify({"status": "ok", "configured": True}), 200


@profile_bp.delete('/profile/imap')
@token_required
def clear_imap_credentials(user):
    """Entfernt IMAP-Credentials komplett (User möchte z.B. wieder Apps-Script)."""
    user.imap_host = None
    user.imap_user = None
    user.imap_password_encrypted = None
    db.session.commit()
    return ('', 204)


@profile_bp.post('/profile/imap/test')
@token_required
def test_imap_connection(user):
    """Testet Login + listet erste Folder.

    Bei Gmail: Foldernamen wie '[Gmail]/All Mail' oder lokalisiert
    '[Google Mail]/Alle Nachrichten' sind nötig um auch archivierte Mails
    zu erreichen. Folder-Liste hilft beim Setup.
    """
    if not user.imap_password_encrypted:
        return jsonify({"ok": False, "error": "IMAP nicht konfiguriert"}), 200

    import imaplib
    import ssl
    folders = []
    try:
        conn = imaplib.IMAP4_SSL(user.imap_host, 993, ssl_context=ssl.create_default_context())
        try:
            conn.login(user.imap_user, user.decrypted_imap_password)
        except imaplib.IMAP4.error as e:
            return jsonify({"ok": False, "error": f"Login fehlgeschlagen: {e}"}), 200

        typ, raw_folders = conn.list()
        if typ == 'OK' and raw_folders:
            for entry in raw_folders[:80]:
                if not entry:
                    continue
                line = entry.decode('utf-8', errors='ignore') if isinstance(entry, bytes) else str(entry)
                # IMAP LIST format: (flags) "delimiter" "folder_name"
                # Wir extrahieren nur den letzten quoted-token.
                m = _imap_list_re.search(line)
                if m:
                    folders.append(m.group(1))
                else:
                    # Fallback: letzte Whitespace-separierte Token nehmen.
                    parts = line.rsplit(' ', 1)
                    if len(parts) == 2:
                        folders.append(parts[1].strip().strip('"'))
        try:
            conn.logout()
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "folder_count": len(folders),
            "folders_sample": folders[:60],
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


# Regex für IMAP-LIST-Response: (flags) "delim" "name"  →  greift den Namen.
import re as _imap_re
_imap_list_re = _imap_re.compile(r'"([^"]*)"\s*$')
