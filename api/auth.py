from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
from config import Config
from auth_service import AuthService
from models import User

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


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return {'error': 'Email and password required'}, 400

    success, user, message = AuthService.register_user(
        data['email'],
        data['password']
    )

    if not success:
        return {'error': message}, 400

    return {
        'id': user.id,
        'email': user.email,
        'message': message
    }, 201


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
        'created_at': user.created_at.isoformat()
    }, 200
