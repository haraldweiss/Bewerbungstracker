from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import Application, ApplicationStatus
from database import db
from datetime import datetime

apps_bp = Blueprint('applications', __name__, url_prefix='/api/applications')


@apps_bp.route('', methods=['GET'])
@token_required
def list_applications(user):
    """List all applications for user"""
    apps = Application.query.filter_by(user_id=user.id).all()

    return {
        'count': len(apps),
        'applications': [
            {
                'id': app.id,
                'company': app.company,
                'position': app.position,
                'status': app.status,
                'applied_date': app.applied_date.isoformat() if app.applied_date else None,
                'created_at': app.created_at.isoformat()
            }
            for app in apps
        ]
    }, 200


@apps_bp.route('', methods=['POST'])
@token_required
def create_application(user):
    """Create new application"""
    data = request.get_json()

    if not data or not data.get('company') or not data.get('position'):
        return {'error': 'Company and position required'}, 400

    app = Application(
        user_id=user.id,
        company=data['company'],
        position=data['position'],
        status=data.get('status', ApplicationStatus.APPLIED.value),
        applied_date=datetime.fromisoformat(data['applied_date']).date() if data.get('applied_date') else None
    )

    db.session.add(app)
    db.session.commit()

    return {
        'id': app.id,
        'company': app.company,
        'position': app.position,
        'status': app.status,
        'created_at': app.created_at.isoformat()
    }, 201


@apps_bp.route('/<app_id>', methods=['GET'])
@token_required
def get_application(user, app_id):
    """Get single application"""
    app = Application.query.filter_by(id=app_id, user_id=user.id).first()

    if not app:
        return {'error': 'Application not found'}, 404

    return {
        'id': app.id,
        'company': app.company,
        'position': app.position,
        'status': app.status,
        'applied_date': app.applied_date.isoformat() if app.applied_date else None,
        'created_at': app.created_at.isoformat(),
        'updated_at': app.updated_at.isoformat()
    }, 200


@apps_bp.route('/<app_id>', methods=['PATCH'])
@token_required
def update_application(user, app_id):
    """Update application"""
    app = Application.query.filter_by(id=app_id, user_id=user.id).first()

    if not app:
        return {'error': 'Application not found'}, 404

    data = request.get_json()

    if 'company' in data:
        app.company = data['company']
    if 'position' in data:
        app.position = data['position']
    if 'status' in data:
        app.status = data['status']
    if 'applied_date' in data:
        app.applied_date = datetime.fromisoformat(data['applied_date']).date()

    app.updated_at = datetime.utcnow()
    db.session.commit()

    return {
        'id': app.id,
        'company': app.company,
        'position': app.position,
        'status': app.status,
        'updated_at': app.updated_at.isoformat()
    }, 200


@apps_bp.route('/<app_id>', methods=['DELETE'])
@token_required
def delete_application(user, app_id):
    """Delete application"""
    app = Application.query.filter_by(id=app_id, user_id=user.id).first()

    if not app:
        return {'error': 'Application not found'}, 404

    db.session.delete(app)
    db.session.commit()

    return {'message': 'Application deleted'}, 200
