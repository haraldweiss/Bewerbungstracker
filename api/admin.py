import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from functools import wraps

from api.auth import token_required, admin_required
from models import User, Application, EmailConfirmationToken
from database import db
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
