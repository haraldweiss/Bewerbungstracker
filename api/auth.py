from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import secrets
from datetime import datetime, timedelta
from config import Config
from auth_service import AuthService
from models import User, EmailConfirmationToken
from services.email_service import send_confirmation_email
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
    """Register new user - creates inactive user and sends confirmation email"""
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
