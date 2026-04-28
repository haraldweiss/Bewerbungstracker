"""Tests for backup API endpoints"""

import pytest
import json
from datetime import datetime, timedelta
from io import BytesIO
from app import create_app
from database import db
from models import User, Application, Email, BackupHistory
from auth_service import AuthService
from services.backup_service import BackupService
import jwt
from config import Config


# app, client und auth_headers kommen aus tests/conftest.py.
# Backup-Endpoints brauchen Envelope-Encryption-Keys (DEK im Cache),
# daher hier auf die zentrale Variante mit Crypto umstellen.


@pytest.fixture
def auth_headers(auth_headers_with_keys):
    """Backup-Tests benötigen aktivierte Envelope-Encryption + DEK-Cache."""
    return auth_headers_with_keys


@pytest.fixture
def backup_with_data(app, auth_headers):
    """Create test data and backup"""
    headers, user = auth_headers

    with app.app_context():
        # Create applications
        app1 = Application(
            user_id=user.id,
            company='Acme Corp',
            position='Senior Developer',
            status='applied'
        )
        app2 = Application(
            user_id=user.id,
            company='Tech Inc',
            position='DevOps Engineer',
            status='interview'
        )
        db.session.add_all([app1, app2])
        db.session.flush()

        # Create emails
        email1 = Email(
            user_id=user.id,
            message_id='msg_001@example.com',
            subject='Thank you for applying',
            from_address='hr@acme.com',
            matched_application_id=app1.id
        )
        db.session.add(email1)
        db.session.commit()

        # Create backup
        backup = BackupService.create_backup(user, backup_type='automatic')

        return headers, user, [app1, app2], [email1], backup


class TestListBackups:
    def test_list_backups_no_auth(self, client):
        """Test list backups without authentication"""
        response = client.get('/api/backup/list')
        assert response.status_code == 401

    def test_list_backups_empty(self, app, client, auth_headers):
        """Test list backups when no backups exist"""
        headers, user = auth_headers

        response = client.get(
            '/api/backup/list',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 0
        assert data['backups'] == []

    def test_list_backups_with_data(self, client, backup_with_data):
        """Test list backups with backup data"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            '/api/backup/list',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] >= 1
        assert len(data['backups']) >= 1

        backup_item = data['backups'][0]
        assert 'version' in backup_item
        assert 'created_at' in backup_item
        assert 'backup_type' in backup_item
        assert 'summary' in backup_item
        assert 'format' in backup_item


class TestExportBackup:
    def test_export_json_no_auth(self, client):
        """Test export without authentication"""
        response = client.get('/api/backup/export?format=json')
        assert response.status_code == 401

    def test_export_json_empty(self, app, client, auth_headers):
        """Test JSON export with no data"""
        headers, user = auth_headers

        response = client.get(
            '/api/backup/export?format=json',
            headers=headers
        )

        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/json'
        data = json.loads(response.data)
        assert 'applications' in data
        assert 'exported_at' in data

    def test_export_json_with_data(self, client, backup_with_data):
        """Test JSON export with applications and emails"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            '/api/backup/export?format=json&include_emails=true',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['applications']) == 2
        assert len(data.get('emails', [])) >= 1

    def test_export_json_no_emails(self, client, backup_with_data):
        """Test JSON export without emails"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            '/api/backup/export?format=json&include_emails=false',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['applications']) == 2
        assert 'emails' not in data or data['emails'] is None

    def test_export_csv(self, client, backup_with_data):
        """Test CSV export"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            '/api/backup/export?format=csv',
            headers=headers
        )

        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv'
        content = response.data.decode('utf-8')
        assert 'company' in content
        assert 'Acme Corp' in content
        assert 'Tech Inc' in content

    def test_export_invalid_format(self, client, auth_headers):
        """Test export with invalid format"""
        headers, user = auth_headers

        response = client.get(
            '/api/backup/export?format=invalid',
            headers=headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestGetBackup:
    def test_get_backup_no_auth(self, client):
        """Test get backup without authentication"""
        response = client.get('/api/backup/1')
        assert response.status_code == 401

    def test_get_backup_not_found(self, app, client, auth_headers):
        """Test get non-existent backup"""
        headers, user = auth_headers

        response = client.get(
            '/api/backup/999',
            headers=headers
        )

        assert response.status_code == 404

    def test_get_backup_decrypted(self, client, backup_with_data):
        """Test get backup with decryption"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            f'/api/backup/{backup.version}?decrypt=true',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['version'] == backup.version
        assert 'data' in data
        assert 'applications' in data['data']

    def test_get_backup_encrypted(self, client, backup_with_data):
        """Test get backup without decryption"""
        headers, user, apps, emails, backup = backup_with_data

        response = client.get(
            f'/api/backup/{backup.version}?decrypt=false',
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['version'] == backup.version
        assert 'encrypted_data' in data
        assert 'data' not in data


class TestRestoreBackup:
    def test_restore_backup_no_auth(self, client):
        """Test restore without authentication"""
        response = client.post('/api/backup/1/restore', json={'confirm': True})
        assert response.status_code == 401

    def test_restore_backup_no_confirm(self, app, client, auth_headers):
        """Test restore without confirmation"""
        headers, user = auth_headers

        response = client.post(
            '/api/backup/1/restore',
            json={'confirm': False},
            headers=headers
        )

        assert response.status_code == 400

    def test_restore_backup_not_found(self, app, client, auth_headers):
        """Test restore non-existent backup"""
        headers, user = auth_headers

        response = client.post(
            '/api/backup/999/restore',
            json={'confirm': True},
            headers=headers
        )

        assert response.status_code == 404

    def test_restore_backup_success(self, app, client, backup_with_data):
        """Test successful backup restore"""
        headers, user, apps, emails, backup = backup_with_data

        # Delete original data
        with app.app_context():
            Application.query.filter_by(user_id=user.id).delete()
            Email.query.filter_by(user_id=user.id).delete()
            db.session.commit()

        # Restore from backup
        response = client.post(
            f'/api/backup/{backup.version}/restore',
            json={'confirm': True, 'clear_existing': False},
            headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'restored_applications' in data
        assert data['restored_applications'] > 0

        # Verify data was restored
        with app.app_context():
            restored_apps = Application.query.filter_by(user_id=user.id).all()
            assert len(restored_apps) > 0


class TestImportBackup:
    def test_import_backup_no_auth(self, client):
        """Test import without authentication"""
        response = client.post('/api/backup/import')
        assert response.status_code == 401

    def test_import_backup_no_file(self, client, auth_headers):
        """Test import without file"""
        headers, user = auth_headers

        response = client.post(
            '/api/backup/import',
            headers=headers
        )

        assert response.status_code == 400

    def test_import_backup_invalid_json(self, app, client, auth_headers):
        """Test import with invalid JSON"""
        headers, user = auth_headers

        response = client.post(
            '/api/backup/import',
            data={'backup': (BytesIO(b'invalid json'), 'backup.json')},
            headers={
                'Authorization': headers['Authorization']
            }
        )

        assert response.status_code == 400

    def test_import_backup_missing_applications(self, app, client, auth_headers):
        """Test import without applications key"""
        headers, user = auth_headers
        from io import BytesIO

        invalid_data = json.dumps({'emails': []})
        response = client.post(
            '/api/backup/import',
            data={'backup': (BytesIO(invalid_data.encode()), 'backup.json')},
            headers={
                'Authorization': headers['Authorization']
            }
        )

        assert response.status_code == 400

    def test_import_backup_success(self, app, client, auth_headers):
        """Test successful backup import"""
        headers, user = auth_headers

        import_data = {
            'applications': [
                {
                    'company': 'Imported Corp',
                    'position': 'Senior Engineer',
                    'status': 'applied',
                    'applied_date': None
                }
            ],
            'emails': []
        }

        response = client.post(
            '/api/backup/import',
            data={'backup': (BytesIO(json.dumps(import_data).encode()), 'backup.json')},
            headers={
                'Authorization': headers['Authorization']
            }
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['imported_applications'] > 0

        # Verify imported data
        with app.app_context():
            imported_app = Application.query.filter_by(
                user_id=user.id,
                company='Imported Corp'
            ).first()
            assert imported_app is not None
