from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import Email, Application
from database import db
from datetime import datetime

emails_bp = Blueprint('emails', __name__, url_prefix='/api/emails')


@emails_bp.route('', methods=['GET'])
@token_required
def list_emails(user):
    """List emails for user, optionally filtered by application"""
    app_id = request.args.get('application_id')

    query = Email.query.filter_by(user_id=user.id)

    if app_id:
        query = query.filter_by(matched_application_id=app_id)

    emails = query.order_by(Email.timestamp.desc()).all()

    return {
        'count': len(emails),
        'emails': [
            {
                'id': email.id,
                'subject': email.subject,
                'from': email.from_address,
                'matched_application_id': email.matched_application_id,
                'timestamp': email.timestamp.isoformat() if email.timestamp else None
            }
            for email in emails
        ]
    }, 200


@emails_bp.route('/<email_id>', methods=['GET'])
@token_required
def get_email(user, email_id):
    """Get full email"""
    email = Email.query.filter_by(id=email_id, user_id=user.id).first()

    if not email:
        return {'error': 'Email not found'}, 404

    return {
        'id': email.id,
        'subject': email.subject,
        'from': email.from_address,
        'body': email.body,
        'matched_application_id': email.matched_application_id,
        'timestamp': email.timestamp.isoformat() if email.timestamp else None
    }, 200


@emails_bp.route('/<email_id>/match', methods=['POST'])
@token_required
def match_email(user, email_id):
    """Match email to application"""
    email = Email.query.filter_by(id=email_id, user_id=user.id).first()

    if not email:
        return {'error': 'Email not found'}, 404

    data = request.get_json()
    app_id = data.get('application_id')

    if app_id:
        app = Application.query.filter_by(id=app_id, user_id=user.id).first()
        if not app:
            return {'error': 'Application not found'}, 404

    email.matched_application_id = app_id
    db.session.commit()

    return {
        'id': email.id,
        'matched_application_id': email.matched_application_id
    }, 200


@emails_bp.route('/sync', methods=['POST'])
@token_required
def sync_emails(user):
    """Trigger IMAP sync (placeholder)"""
    # This will be implemented to fetch from IMAP proxy
    # For now, just return success
    return {
        'message': 'Sync initiated',
        'emails_synced': 0
    }, 200


@emails_bp.route('/sync/status', methods=['GET'])
@token_required
def sync_status(user):
    """Get sync status for user"""
    return {
        'last_sync': None,
        'is_syncing': False
    }, 200
