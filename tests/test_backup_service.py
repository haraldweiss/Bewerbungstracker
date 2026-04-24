"""Tests for BackupService with automatic backup creation and pruning"""

import pytest
import json
from datetime import datetime
from models import User, Application, Email, BackupHistory
from services.backup_service import BackupService
from services.encryption_service import EncryptionService
from database import db


@pytest.fixture
def test_user(app):
    """Create a test user"""
    with app.app_context():
        user = User(
            email="backup_test@example.com",
            password_hash="hashed_password_123"
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    # Return the user ID so we can fetch it fresh in each test
    return user_id


@pytest.fixture
def user_with_data(app, test_user):
    """Create a test user with applications and emails"""
    with app.app_context():
        user = db.session.get(User, test_user)

        # Create applications
        app1 = Application(
            user_id=user.id,
            company="TechCorp",
            position="Senior Engineer",
            status="applied",
            applied_date=datetime.utcnow().date()
        )
        app2 = Application(
            user_id=user.id,
            company="WebInc",
            position="Full Stack Developer",
            status="interview",
            applied_date=datetime.utcnow().date()
        )
        db.session.add_all([app1, app2])
        db.session.flush()

        # Create emails
        email1 = Email(
            user_id=user.id,
            message_id="msg_001",
            subject="TechCorp - Interview Invitation",
            from_address="hr@techcorp.com",
            matched_application_id=app1.id,
            timestamp=datetime.utcnow()
        )
        email2 = Email(
            user_id=user.id,
            message_id="msg_002",
            subject="WebInc - Application Received",
            from_address="noreply@webinc.com",
            matched_application_id=app2.id,
            timestamp=datetime.utcnow()
        )
        db.session.add_all([email1, email2])
        db.session.commit()

        return user.id


def test_create_automatic_backup(app, user_with_data):
    """Test creating an automatic backup and verify fields"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        # Create backup
        backup = BackupService.create_backup(user, backup_type='automatic')

        # Verify backup record created
        assert backup is not None
        assert isinstance(backup, BackupHistory)
        assert backup.user_id == user.id
        assert backup.backup_type == 'automatic'
        assert backup.version == 1
        assert backup.format == 'json'
        assert backup.encrypted_data is not None
        assert backup.summary is not None

        # Verify summary includes count
        assert "applications" in backup.summary.lower()
        assert "emails" in backup.summary.lower()


def test_backup_versioning_max_10(app, user_with_data):
    """Test that only maximum 10 backups are kept per user"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        # Create 15 backups
        backups = []
        for i in range(15):
            backup = BackupService.create_backup(user, backup_type='automatic')
            backups.append(backup)

        # Verify only 10 are kept
        remaining_backups = BackupService.get_user_backups(user_with_data, limit=100)

        assert len(remaining_backups) == 10

        # Verify versions are sequential (1-10)
        versions = sorted([b.version for b in remaining_backups])
        assert versions == list(range(6, 16))  # Versions 6-15 should remain


def test_decrypt_backup_data(app, user_with_data):
    """Test decrypting backup data and verify structure"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        # Create backup
        backup = BackupService.create_backup(user, backup_type='automatic')

        # Decrypt backup
        decrypted_data = BackupService.get_backup_decrypted(
            backup,
            user.email,
            user.password_hash
        )

        # Verify structure
        assert isinstance(decrypted_data, dict)
        assert 'applications' in decrypted_data
        assert 'emails' in decrypted_data
        assert 'backed_up_at' in decrypted_data

        # Verify applications structure
        assert isinstance(decrypted_data['applications'], list)
        assert len(decrypted_data['applications']) == 2

        app_data = decrypted_data['applications'][0]
        assert 'id' in app_data
        assert 'company' in app_data
        assert 'position' in app_data
        assert 'status' in app_data
        assert 'applied_date' in app_data
        assert 'created_at' in app_data
        assert 'updated_at' in app_data

        # Verify emails structure
        assert isinstance(decrypted_data['emails'], list)
        assert len(decrypted_data['emails']) == 2

        email_data = decrypted_data['emails'][0]
        assert 'id' in email_data
        assert 'message_id' in email_data
        assert 'subject' in email_data
        assert 'from_address' in email_data
        assert 'timestamp' in email_data
        assert 'matched_application_id' in email_data


def test_get_user_backups(app, user_with_data):
    """Test retrieving user's recent backups"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        # Create 3 backups
        for i in range(3):
            BackupService.create_backup(user, backup_type='automatic')

        # Get backups
        backups = BackupService.get_user_backups(user.id, limit=10)

        assert len(backups) == 3
        assert all(b.user_id == user.id for b in backups)

        # Verify ordered by created_at descending (most recent first)
        for i in range(len(backups) - 1):
            assert backups[i].created_at >= backups[i + 1].created_at


def test_create_backup_empty_user(app, test_user):
    """Test creating backup for user with no applications/emails"""
    with app.app_context():
        user = db.session.get(User, test_user)

        # Create backup
        backup = BackupService.create_backup(user, backup_type='automatic')

        assert backup is not None
        assert backup.version == 1

        # Decrypt and verify empty data
        decrypted = BackupService.get_backup_decrypted(
            backup,
            user.email,
            user.password_hash
        )

        assert len(decrypted['applications']) == 0
        assert len(decrypted['emails']) == 0


def test_backup_summary_format(app, user_with_data):
    """Test that backup summary has correct format"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        backup = BackupService.create_backup(user, backup_type='automatic')

        # Summary should contain counts
        assert "2" in backup.summary  # 2 applications
        assert "2" in backup.summary  # 2 emails


def test_manual_backup_type(app, user_with_data):
    """Test creating a manual backup"""
    with app.app_context():
        user = db.session.get(User, user_with_data)

        backup = BackupService.create_backup(user, backup_type='manual')

        assert backup.backup_type == 'manual'
        assert backup.version == 1
