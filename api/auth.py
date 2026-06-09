# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import secrets
from datetime import datetime, timedelta
from config import Config
from auth_service import AuthService
from models import User, EmailConfirmationToken
from services.email_service import send_confirmation_email, send_admin_new_user_notification
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from database import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def token_required(f):
    """Decorator to require JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return {'error': 'Invalid token format'}, 401

        if not token:
            return {'error': 'Missing token'}, 401

        payload = AuthService.verify_token(token)
        if not payload:
            return {'error': 'Invalid or expired token'}, 401

        user = User.query.get(payload['user_id'])
        if not user:
            return {'error': 'User not found'}, 401

        return f(user, *args, **kwargs)

    return decorated


def admin_required(f):
    """Decorator to require admin user"""
    @wraps(f)
    def decorated(user, *args, **kwargs):
        if not user.is_admin:
            return {'error': 'Admin access required'}, 403
        return f(user, *args, **kwargs)
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user - creates inactive user and sends confirmation email.

    Gated by env AUTH_ALLOW_REGISTRATION (default: 'false'). Bei deaktivierter
    Public-Registrierung legt der Admin User über /api/admin/users an
    (siehe api/admin.py).
    """
    import os
    if os.getenv('AUTH_ALLOW_REGISTRATION', 'false').lower() not in ('true', '1', 'yes'):
        return {'error': 'Registrierung ist deaktiviert. Bitte den Admin kontaktieren.'}, 403

    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return {'error': 'Email and password required'}, 400

    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return {'error': 'Email already registered'}, 400

    try:
        password_hash = AuthService.hash_password(data['password'])

        # Envelope-Encryption: per-User-Salt + DEK generieren, DEK mit
        # KEK aus Passwort wrappen.
        salt, encrypted_dek, _dek = EncryptionService.create_user_keys(data['password'])

        user = User(
            email=data['email'],
            password_hash=password_hash,
            email_confirmed=False,
            is_active=False,
            encryption_salt=salt,
            encrypted_data_key=encrypted_dek,
        )
        db.session.add(user)
        db.session.flush()  # Get user ID

        # Create confirmation token
        confirmation_token = secrets.token_urlsafe(32)
        token_record = EmailConfirmationToken(
            token=confirmation_token,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.session.add(token_record)
        db.session.commit()

        # Send confirmation email
        from flask import current_app
        confirmation_link = f"{current_app.config['APP_URL']}/api/auth/confirm-email?token={confirmation_token}"
        send_confirmation_email(user.email, confirmation_link)

        # Admin-Notification (no-op wenn ADMIN_NOTIFICATION_EMAIL nicht gesetzt).
        # Fehler hier dürfen nicht den User-Flow brechen.
        try:
            send_admin_new_user_notification(
                user.email,
                ip=request.headers.get('X-Forwarded-For', request.remote_addr or ''),
                user_agent=request.headers.get('User-Agent', ''),
            )
        except Exception:
            pass

        return {
            'id': user.id,
            'email': user.email,
            'message': 'Registration successful! Please confirm your email to activate your account.'
        }, 201
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 400


@auth_bp.route('/confirm-email', methods=['GET'])
def confirm_email():
    """Confirm email with token. Liefert eine HTML-Response, weil dieser
    Endpoint typischerweise direkt vom Email-Client geöffnet wird."""
    from flask import current_app, make_response

    token = request.args.get('token')
    app_url = current_app.config.get('APP_URL', 'https://bewerbungen.wolfinisoftware.de')

    def _html(title: str, msg: str, kind: str = 'success') -> tuple:
        color = {'success': '#10B981', 'error': '#DC2626'}.get(kind, '#4F46E5')
        body = f"""
        <!doctype html><html lang="de"><head><meta charset="utf-8">
        <title>{title}</title>
        <style>body{{font-family:Arial,sans-serif;max-width:560px;margin:60px auto;color:#333;text-align:center}}
        h1{{color:{color}}} a{{display:inline-block;margin-top:24px;padding:10px 20px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px}}</style>
        </head><body><h1>{title}</h1><p>{msg}</p>
        <a href="{app_url}">Zur App</a></body></html>
        """
        return body, 200 if kind == 'success' else 400

    if not token:
        return _html('Fehler', 'Bestätigungs-Token fehlt.', 'error')

    token_record = EmailConfirmationToken.query.filter_by(token=token).first()
    if not token_record:
        return _html('Ungültiger Link', 'Der Bestätigungs-Link ist ungültig oder bereits eingelöst.', 'error')

    if token_record.expires_at < datetime.utcnow():
        db.session.delete(token_record)
        db.session.commit()
        return _html('Link abgelaufen', 'Dieser Link ist abgelaufen. Bitte einen neuen anfordern.', 'error')

    user = User.query.get(token_record.user_id)
    if not user:
        return _html('Fehler', 'Zugehöriger Account existiert nicht mehr.', 'error')

    user.email_confirmed = True
    db.session.delete(token_record)
    db.session.commit()

    return _html(
        '✅ Konto aktiviert',
        f'Email <strong>{user.email}</strong> bestätigt. Du kannst dich jetzt einloggen.',
        'success',
    )


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return {'error': 'Email and password required'}, 400

    success, user, message = AuthService.login_user(
        data['email'],
        data['password']
    )

    if not success:
        return {'error': message}, 401

    # Check if email is confirmed
    if not user.email_confirmed:
        return {'error': 'Please confirm your email before logging in'}, 401

    # Check if account is approved
    if not user.is_active:
        return {'error': 'Your account is pending admin approval'}, 401

    # Envelope-Encryption: DEK mit Passwort entsperren und in KeyCache legen.
    # Backup-Operationen (auto-Backup auf CRUD) holen den DEK von dort, ohne
    # dass das Passwort über JWT übertragen werden muss.
    if user.encryption_salt and user.encrypted_data_key:
        try:
            dek = EncryptionService.unlock_dek(
                data['password'], user.encryption_salt, user.encrypted_data_key
            )
            get_key_cache().put(user.id, dek)
        except Exception:
            # Crypto-Fehler hier wäre ein DB-Korruptions-Indikator – Login lässt
            # sich nicht fortsetzen, ohne Backups unbrauchbar zu machen.
            return {'error': 'Encryption key unlock failed'}, 500

    access_token = AuthService.create_access_token(user.id)
    refresh_token = AuthService.create_refresh_token(user.id)

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': int(Config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    }, 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    data = request.get_json()

    if not data or not data.get('refresh_token'):
        return {'error': 'Refresh token required'}, 400

    payload = AuthService.verify_token(data['refresh_token'])

    # WICHTIG: payload kann None sein bei expired/invalid token
    if not payload:
        return {'error': 'Invalid or expired refresh token'}, 401

    # WICHTIG: Überprüfe token type NACH payload check
    if payload.get('type') != 'refresh':
        return {'error': 'Invalid token type - not a refresh token'}, 401

    new_access_token = AuthService.create_access_token(payload['user_id'])

    return {
        'access_token': new_access_token,
        'token_type': 'Bearer',
        'expires_in': int(Config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    }, 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Passwort-Reset-Link per E-Mail senden."""
    from models import EmailConfirmationToken
    from services.email_service import send_password_reset_email

    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email:
        return {'error': 'Gültige Email erforderlich'}, 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return {'message': 'Wenn die Email existiert, wurde ein Reset-Link versendet.'}, 200

    EmailConfirmationToken.query.filter_by(user_id=user.id).delete()
    db.session.flush()

    import secrets
    from datetime import datetime, timedelta

    token = secrets.token_urlsafe(32)
    reset_token = EmailConfirmationToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.session.add(reset_token)
    db.session.commit()

    app_url = current_app.config.get('APP_URL', 'https://bewerbungen.wolfinisoftware.de')
    reset_link = f"{app_url}/reset-password?token={token}"
    send_password_reset_email(user.email, reset_link)

    return {'message': 'Wenn die Email existiert, wurde ein Reset-Link versendet.'}, 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password_token():
    """Passwort mit Token zurücksetzen."""
    from models import EmailConfirmationToken

    data = request.get_json(silent=True) or {}
    token_str = data.get('token') or ''
    new_pw = data.get('new_password') or ''

    if not token_str or not new_pw:
        return {'error': 'Token und neues Passwort erforderlich'}, 400
    if len(new_pw) < 8:
        return {'error': 'Passwort mindestens 8 Zeichen'}, 400

    from datetime import datetime
    record = EmailConfirmationToken.query.filter_by(token=token_str).first()
    if not record:
        return {'error': 'Ungültiger oder abgelaufener Token'}, 404
    if record.expires_at < datetime.utcnow():
        db.session.delete(record)
        db.session.commit()
        return {'error': 'Token abgelaufen — bitte neuen Reset anfordern'}, 410

    user = User.query.get(record.user_id)
    if not user:
        return {'error': 'User nicht gefunden'}, 404

    from services.encryption_service import EncryptionService
    user.password_hash = AuthService.hash_password(new_pw)
    try:
        salt, encrypted_dek, _ = EncryptionService.create_user_keys(new_pw)
        user.encryption_salt = salt
        user.encrypted_data_key = encrypted_dek
    except Exception:
        pass

    db.session.delete(record)
    db.session.commit()

    return {'message': 'Passwort erfolgreich zurückgesetzt'}, 200


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(user):
    """Logout user (token invalidation handled client-side)"""
    # DEK aus dem In-Memory-Cache entfernen – kein Klartext-Schlüssel im RAM
    # nach Logout.
    get_key_cache().evict(user.id)
    return {'message': 'Logout successful'}, 200


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(user):
    """Get current authenticated user"""
    return {
        'id': user.id,
        'email': user.email,
        'is_admin': user.is_admin,
        'created_at': user.created_at.isoformat()
    }, 200


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(user):
    """Eigenes Passwort ändern (alter + neuer PW erforderlich)."""
    from services.encryption_service import EncryptionService

    data = request.get_json(silent=True) or {}
    old_pw = data.get('old_password') or ''
    new_pw = data.get('new_password') or ''

    if not old_pw or not new_pw:
        return {'error': 'old_password und new_password erforderlich'}, 400
    if len(new_pw) < 8:
        return {'error': 'Neues Passwort mindestens 8 Zeichen'}, 400

    if not AuthService.verify_password(old_pw, user.password_hash):
        return {'error': 'Altes Passwort ist falsch'}, 403

    user.password_hash = AuthService.hash_password(new_pw)
    # DEK neu verschlüsseln mit neuem Passwort
    try:
        salt, encrypted_dek, _ = EncryptionService.create_user_keys(new_pw)
        user.encryption_salt = salt
        user.encrypted_data_key = encrypted_dek
    except Exception:
        pass  # non-fatal — PW-Änderung klappt auch ohne DEK-Re-Encryption

    db.session.commit()
    return {'message': 'Passwort geändert'}, 200
