"""Backup API endpoints for export, import, restore, and list operations"""

from flask import Blueprint, request, jsonify, make_response
from api.auth import token_required
from models import BackupHistory, Application, User
from database import db
from services.backup_service import BackupService
from services.encryption_service import EncryptionService
import json
import csv
from io import StringIO
from datetime import datetime

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')


@backup_bp.route('/list', methods=['GET'])
@token_required
def list_backups(user):
    """
    GET /api/backup/list
    Returns list of all backup versions with metadata
    """
    try:
        backups = BackupService.get_user_backups(user.id, limit=100)

        return {
            'count': len(backups),
            'backups': [
                {
                    'version': backup.version,
                    'created_at': backup.created_at.isoformat(),
                    'backup_type': backup.backup_type,
                    'summary': backup.summary,
                    'format': backup.format
                }
                for backup in backups
            ]
        }, 200
    except Exception as e:
        return {'error': str(e)}, 500


@backup_bp.route('/export', methods=['GET'])
@token_required
def export_backup(user):
    """
    GET /api/backup/export?format=json|csv&include_emails=true|false
    Exports current user data in requested format
    """
    try:
        format_type = request.args.get('format', 'json').lower()
        include_emails = request.args.get('include_emails', 'true').lower() == 'true'

        # Validate format
        if format_type not in ['json', 'csv']:
            return {'error': 'Format must be json or csv'}, 400

        # Get current applications
        applications = Application.query.filter_by(user_id=user.id).all()

        if format_type == 'json':
            # Build JSON export
            export_data = {
                'applications': [
                    {
                        'id': app.id,
                        'company': app.company,
                        'position': app.position,
                        'status': app.status,
                        'applied_date': app.applied_date.isoformat() if app.applied_date else None,
                        'created_at': app.created_at.isoformat(),
                        'updated_at': app.updated_at.isoformat(),
                    }
                    for app in applications
                ],
                'exported_at': datetime.utcnow().isoformat()
            }

            if include_emails:
                from models import Email
                emails = Email.query.filter_by(user_id=user.id).all()
                export_data['emails'] = [
                    {
                        'id': email.id,
                        'message_id': email.message_id,
                        'subject': email.subject,
                        'from_address': email.from_address,
                        'timestamp': email.timestamp.isoformat() if email.timestamp else None,
                        'matched_application_id': email.matched_application_id,
                    }
                    for email in emails
                ]

            # Create JSON response
            response = make_response(
                json.dumps(export_data, indent=2),
                200
            )
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = 'attachment; filename=backup_export.json'
            return response

        else:  # CSV format
            # CSV export: applications only (emails would require nested structure)
            csv_buffer = StringIO()

            if applications:
                fieldnames = ['id', 'company', 'position', 'status', 'applied_date', 'created_at', 'updated_at']
                writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                writer.writeheader()

                for app in applications:
                    writer.writerow({
                        'id': app.id,
                        'company': app.company,
                        'position': app.position,
                        'status': app.status,
                        'applied_date': app.applied_date.isoformat() if app.applied_date else '',
                        'created_at': app.created_at.isoformat(),
                        'updated_at': app.updated_at.isoformat(),
                    })
            else:
                # Write header only if no applications
                csv_buffer.write('id,company,position,status,applied_date,created_at,updated_at\n')

            csv_content = csv_buffer.getvalue()
            response = make_response(csv_content, 200)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=backup_export.csv'
            return response

    except Exception as e:
        return {'error': str(e)}, 500


@backup_bp.route('/<int:version>', methods=['GET'])
@token_required
def get_backup(user, version):
    """
    GET /api/backup/:version?decrypt=true|false
    Retrieve specific backup version
    """
    try:
        decrypt = request.args.get('decrypt', 'true').lower() == 'true'

        # Get backup by version and user_id
        backup = BackupHistory.query.filter_by(
            user_id=user.id,
            version=version
        ).first()

        if not backup:
            return {'error': 'Backup not found'}, 404

        if decrypt:
            try:
                # Decrypt the backup data
                decrypted_data = BackupService.get_backup_decrypted(
                    backup,
                    user.email,
                    user.password_hash
                )

                return {
                    'version': backup.version,
                    'created_at': backup.created_at.isoformat(),
                    'backup_type': backup.backup_type,
                    'summary': backup.summary,
                    'data': decrypted_data
                }, 200

            except Exception as e:
                return {'error': 'Failed to decrypt backup'}, 400

        else:
            # Return encrypted data
            return {
                'version': backup.version,
                'created_at': backup.created_at.isoformat(),
                'backup_type': backup.backup_type,
                'summary': backup.summary,
                'encrypted_data': backup.encrypted_data,
                'format': backup.format
            }, 200

    except Exception as e:
        return {'error': str(e)}, 500


@backup_bp.route('/<int:version>/restore', methods=['POST'])
@token_required
def restore_backup(user, version):
    """
    POST /api/backup/:version/restore
    Restore from specific backup version
    Request body: {"confirm": true, "clear_existing": true|false}
    """
    try:
        data = request.get_json()

        if not data or not data.get('confirm'):
            return {'error': 'Confirmation required (confirm: true)'}, 400

        clear_existing = data.get('clear_existing', False)

        # Get backup
        backup = BackupHistory.query.filter_by(
            user_id=user.id,
            version=version
        ).first()

        if not backup:
            return {'error': 'Backup not found'}, 404

        try:
            # Decrypt backup
            decrypted_data = BackupService.get_backup_decrypted(
                backup,
                user.email,
                user.password_hash
            )
        except Exception as e:
            return {'error': 'Failed to decrypt backup'}, 400

        # Clear existing data if requested
        if clear_existing:
            Application.query.filter_by(user_id=user.id).delete()
            from models import Email
            Email.query.filter_by(user_id=user.id).delete()
            db.session.commit()

        # Restore applications
        applications_data = decrypted_data.get('applications', [])
        restored_apps = []

        for app_data in applications_data:
            # Check if application already exists
            existing_app = Application.query.filter_by(
                user_id=user.id,
                id=app_data['id']
            ).first()

            if not existing_app:
                # Create new application
                app = Application(
                    id=app_data['id'],
                    user_id=user.id,
                    company=app_data['company'],
                    position=app_data['position'],
                    status=app_data.get('status', 'applied'),
                    applied_date=datetime.fromisoformat(app_data['applied_date']).date() if app_data.get('applied_date') else None
                )
                db.session.add(app)
                restored_apps.append(app_data['company'])

        # Restore emails if included in backup
        emails_data = decrypted_data.get('emails', [])
        restored_emails = 0

        if emails_data:
            from models import Email
            for email_data in emails_data:
                existing_email = Email.query.filter_by(
                    user_id=user.id,
                    id=email_data['id']
                ).first()

                if not existing_email:
                    email = Email(
                        id=email_data['id'],
                        user_id=user.id,
                        message_id=email_data.get('message_id'),
                        subject=email_data.get('subject'),
                        from_address=email_data.get('from_address'),
                        timestamp=datetime.fromisoformat(email_data['timestamp']) if email_data.get('timestamp') else None,
                        matched_application_id=email_data.get('matched_application_id')
                    )
                    db.session.add(email)
                    restored_emails += 1

        db.session.commit()

        # Create backup after restore
        new_backup = BackupService.create_backup(user, backup_type='manual_restore')

        return {
            'message': 'Restore completed',
            'restored_applications': len(restored_apps),
            'restored_emails': restored_emails,
            'new_backup_version': new_backup.version,
            'warning': 'Restore successful. A new backup was created as a precaution.'
        }, 200

    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500


@backup_bp.route('/import', methods=['POST'])
@token_required
def import_backup(user):
    """
    POST /api/backup/import
    Import JSON backup file
    Multipart form: file field with 'backup' JSON
    """
    try:
        if 'file' not in request.files:
            return {'error': 'File field required'}, 400

        file = request.files['file']

        if file.filename == '':
            return {'error': 'No file selected'}, 400

        # Read and parse JSON
        try:
            import_data = json.loads(file.read().decode('utf-8'))
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON format'}, 400

        # Validate structure
        if 'applications' not in import_data:
            return {'error': 'Import file must contain "applications" key'}, 400

        applications_data = import_data.get('applications', [])
        emails_data = import_data.get('emails', [])

        # Import applications
        imported_apps = 0
        for app_data in applications_data:
            if not app_data.get('company') or not app_data.get('position'):
                continue

            # Check if application already exists
            existing_app = Application.query.filter_by(
                user_id=user.id,
                company=app_data['company'],
                position=app_data['position']
            ).first()

            if not existing_app:
                app = Application(
                    user_id=user.id,
                    company=app_data['company'],
                    position=app_data['position'],
                    status=app_data.get('status', 'applied'),
                    applied_date=datetime.fromisoformat(app_data['applied_date']).date() if app_data.get('applied_date') else None
                )
                db.session.add(app)
                imported_apps += 1

        # Import emails if included
        imported_emails = 0
        if emails_data:
            from models import Email
            for email_data in emails_data:
                if not email_data.get('message_id'):
                    continue

                existing_email = Email.query.filter_by(
                    user_id=user.id,
                    message_id=email_data['message_id']
                ).first()

                if not existing_email:
                    email = Email(
                        user_id=user.id,
                        message_id=email_data['message_id'],
                        subject=email_data.get('subject'),
                        from_address=email_data.get('from_address'),
                        timestamp=datetime.fromisoformat(email_data['timestamp']) if email_data.get('timestamp') else None,
                        matched_application_id=email_data.get('matched_application_id')
                    )
                    db.session.add(email)
                    imported_emails += 1

        db.session.commit()

        # Create backup after import
        new_backup = BackupService.create_backup(user, backup_type='manual_import')

        return {
            'message': 'Import completed',
            'imported_applications': imported_apps,
            'imported_emails': imported_emails,
            'backup_version': new_backup.version
        }, 201

    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500
