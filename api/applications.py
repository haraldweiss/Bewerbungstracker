from flask import Blueprint, request, current_app
from api.auth import token_required
from models import Application, ApplicationStatus
from database import db
from datetime import datetime
from services.backup_service import BackupService, BackupKeyUnavailable

apps_bp = Blueprint('applications', __name__, url_prefix='/api/applications')


# Felder, die durch POST/PATCH zu setzen sind. Datum/Status separat behandelt,
# da sie eigene Parsing-Regeln haben.
WRITABLE_FIELDS = {
    'company', 'position', 'salary', 'location',
    'contact_email', 'source', 'link', 'notes',
}


def _safe_auto_backup(user) -> None:
    """Best-effort auto-Backup. Bei KeyCache-Miss (z.B. nach Worker-Neustart)
    wird das Backup übersprungen, statt den CRUD-Request zu blockieren.
    """
    try:
        BackupService.create_backup(user, backup_type='automatic')
    except BackupKeyUnavailable:
        current_app.logger.warning(
            "Auto-Backup übersprungen für user=%s – DEK nicht gecached", user.id
        )


def _serialize(app: Application) -> dict:
    """Volle Serialisierung einer Application (auch für GET/Backup)."""
    return {
        'id': app.id,
        'company': app.company,
        'position': app.position,
        'status': app.status,
        'applied_date': app.applied_date.isoformat() if app.applied_date else None,
        'salary': app.salary,
        'location': app.location,
        'contact_email': app.contact_email,
        'source': app.source,
        'link': app.link,
        'notes': app.notes,
        'deleted': app.deleted,
        'deleted_at': app.deleted_at.isoformat() if app.deleted_at else None,
        'created_at': app.created_at.isoformat() if app.created_at else None,
        'updated_at': app.updated_at.isoformat() if app.updated_at else None,
    }


def _parse_date(value):
    """ISO-Date oder None. Akzeptiert auch leeren String aus dem Frontend."""
    if not value:
        return None
    return datetime.fromisoformat(value).date()


@apps_bp.route('', methods=['GET'])
@token_required
def list_applications(user):
    """Liste aller aktiven (nicht gelöschten) Bewerbungen."""
    apps = (
        Application.query
        .filter_by(user_id=user.id, deleted=False)
        .order_by(Application.created_at.desc())
        .all()
    )
    return {
        'count': len(apps),
        'applications': [_serialize(a) for a in apps],
    }, 200


@apps_bp.route('', methods=['POST'])
@token_required
def create_application(user):
    """Bewerbung anlegen."""
    data = request.get_json() or {}

    if not data.get('company') or not data.get('position'):
        return {'error': 'Company and position required'}, 400

    app = Application(
        user_id=user.id,
        company=data['company'],
        position=data['position'],
        status=data.get('status', ApplicationStatus.BEWORBEN.value),
        applied_date=_parse_date(data.get('applied_date')),
        salary=data.get('salary'),
        location=data.get('location'),
        contact_email=data.get('contact_email'),
        source=data.get('source'),
        link=data.get('link'),
        notes=data.get('notes'),
    )
    db.session.add(app)
    db.session.commit()

    _safe_auto_backup(user)
    return _serialize(app), 201


@apps_bp.route('/deleted', methods=['GET'])
@token_required
def list_deleted_applications(user):
    """Liste aller soft-gelöschten Bewerbungen (Frontend-Trash)."""
    apps = (
        Application.query
        .filter_by(user_id=user.id, deleted=True)
        .order_by(Application.deleted_at.desc())
        .all()
    )
    return {
        'count': len(apps),
        'applications': [_serialize(a) for a in apps],
    }, 200


@apps_bp.route('/<app_id>', methods=['GET'])
@token_required
def get_application(user, app_id):
    app = Application.query.filter_by(id=app_id, user_id=user.id, deleted=False).first()
    if not app:
        return {'error': 'Application not found'}, 404
    return _serialize(app), 200


@apps_bp.route('/<app_id>', methods=['PATCH'])
@token_required
def update_application(user, app_id):
    app = Application.query.filter_by(id=app_id, user_id=user.id, deleted=False).first()
    if not app:
        return {'error': 'Application not found'}, 404

    data = request.get_json() or {}

    for field in WRITABLE_FIELDS:
        if field in data:
            setattr(app, field, data[field])

    if 'status' in data:
        app.status = data['status']
    if 'applied_date' in data:
        app.applied_date = _parse_date(data['applied_date'])

    app.updated_at = datetime.utcnow()
    db.session.commit()

    _safe_auto_backup(user)
    return _serialize(app), 200


@apps_bp.route('/<app_id>', methods=['DELETE'])
@token_required
def delete_application(user, app_id):
    """Soft-Delete (Standard) oder Hard-Delete via ?permanent=true."""
    app = Application.query.filter_by(id=app_id, user_id=user.id).first()
    if not app:
        return {'error': 'Application not found'}, 404

    permanent = request.args.get('permanent', '').lower() == 'true'

    if permanent:
        db.session.delete(app)
        db.session.commit()
        _safe_auto_backup(user)
        return {'message': 'Application permanently deleted'}, 200

    app.deleted = True
    app.deleted_at = datetime.utcnow()
    db.session.commit()
    _safe_auto_backup(user)
    return {'message': 'Application moved to trash', 'id': app.id}, 200


@apps_bp.route('/<app_id>/recover', methods=['POST'])
@token_required
def recover_application(user, app_id):
    """Soft-gelöschte Bewerbung wiederherstellen."""
    app = Application.query.filter_by(id=app_id, user_id=user.id).first()
    if not app:
        return {'error': 'Application not found'}, 404
    if not app.deleted:
        return {'error': 'Application is not deleted'}, 400

    app.deleted = False
    app.deleted_at = None
    app.updated_at = datetime.utcnow()
    db.session.commit()
    _safe_auto_backup(user)
    return _serialize(app), 200
