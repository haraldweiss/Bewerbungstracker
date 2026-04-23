from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import secrets
from datetime import datetime, timedelta
from config import Config
from auth_service import AuthService
from models import User, EmailConfirmationToken
from services.email_service import send_confirmation_email
from extensions import db

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
        user = User(
            email=data['email'],
            password_hash=password_hash,
            email_confirmed=False,
            is_active=False
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
    """Confirm email with token"""
    token = request.args.get('token')

    if not token:
        return {'error': 'Confirmation token required'}, 400

    token_record = EmailConfirmationToken.query.filter_by(token=token).first()

    if not token_record:
        return {'error': 'Invalid or expired confirmation token'}, 400

    if token_record.expires_at < datetime.utcnow():
        db.session.delete(token_record)
        db.session.commit()
        return {'error': 'Confirmation token has expired'}, 400

    user = User.query.get(token_record.user_id)
    user.email_confirmed = True
    db.session.delete(token_record)
    db.session.commit()

    return {
        'message': 'Email confirmed! Your account is pending admin approval.',
        'email': user.email
    }, 200


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
