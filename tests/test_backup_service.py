"""Tests für BackupService nach Umstellung auf Envelope-Encryption.

Backups werden jetzt mit dem DEK aus dem KeyCache verschlüsselt – Tests
befüllen den Cache vor jedem Test über das EncryptionService-Helper.
"""

import pytest
from datetime import datetime

from models import User, Application, Email, BackupHistory
from services.backup_service import BackupService, BackupKeyUnavailable
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from database import db


@pytest.fixture(autouse=True)
def reset_key_cache():
    """Cache vor + nach jedem Test leeren."""
    get_key_cache().clear()
    yield
    get_key_cache().clear()


@pytest.fixture
def test_user(app):
    """User mit gesetztem Salt + encrypted_data_key + DEK im Cache."""
    with app.app_context():
        salt, encrypted_dek, dek = EncryptionService.create_user_keys("testpw")
        user = User(
            email="backup_test@example.com",
            password_hash="hashed_password_123",
            encryption_salt=salt,
            encrypted_data_key=encrypted_dek,
        )
        db.session.add(user)
        db.session.commit()
        get_key_cache().put(user.id, dek)
        return user.id


@pytest.fixture
def user_with_data(app, test_user):
    """User mit zwei Applications + zwei Emails."""
    with app.app_context():
        user = db.session.get(User, test_user)

        app1 = Application(
            user_id=user.id, company="TechCorp", position="Senior Engineer",
            status="applied", applied_date=datetime.utcnow().date(),
        )
        app2 = Application(
            user_id=user.id, company="WebInc", position="Full Stack Developer",
            status="interview", applied_date=datetime.utcnow().date(),
        )
        db.session.add_all([app1, app2])
        db.session.flush()

        email1 = Email(
            user_id=user.id, message_id="msg_001",
            subject="TechCorp - Interview Invitation",
            from_address="hr@techcorp.com",
            matched_application_id=app1.id, timestamp=datetime.utcnow(),
        )
        email2 = Email(
            user_id=user.id, message_id="msg_002",
            subject="WebInc - Application Received",
            from_address="noreply@webinc.com",
            matched_application_id=app2.id, timestamp=datetime.utcnow(),
        )
        db.session.add_all([email1, email2])
        db.session.commit()
        return user.id


def test_create_automatic_backup(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        backup = BackupService.create_backup(user, backup_type='automatic')

        assert isinstance(backup, BackupHistory)
        assert backup.user_id == user.id
        assert backup.backup_type == 'automatic'
        assert backup.version == 1
        assert backup.format == 'json'
        assert backup.encrypted_data
        assert "applications" in backup.summary.lower()
        assert "emails" in backup.summary.lower()


def test_create_backup_without_cached_dek_raises(app, test_user):
    with app.app_context():
        user = db.session.get(User, test_user)
        get_key_cache().evict(user.id)

        with pytest.raises(BackupKeyUnavailable):
            BackupService.create_backup(user, backup_type='automatic')


def test_backup_versioning_max_10(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        for _ in range(15):
            BackupService.create_backup(user, backup_type='automatic')

        remaining = BackupService.get_user_backups(user_with_data, limit=100)
        assert len(remaining) == 10
        assert sorted([b.version for b in remaining]) == list(range(6, 16))


def test_decrypt_backup_data(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        backup = BackupService.create_backup(user, backup_type='automatic')

        decrypted = BackupService.get_backup_decrypted(backup, user)

        assert isinstance(decrypted, dict)
        assert 'applications' in decrypted
        assert 'emails' in decrypted
        assert 'backed_up_at' in decrypted
        assert len(decrypted['applications']) == 2
        assert len(decrypted['emails']) == 2

        app_keys = {'id', 'company', 'position', 'status', 'applied_date',
                    'created_at', 'updated_at'}
        assert app_keys.issubset(decrypted['applications'][0].keys())

        email_keys = {'id', 'message_id', 'subject', 'from_address',
                      'timestamp', 'matched_application_id'}
        assert email_keys.issubset(decrypted['emails'][0].keys())


def test_decrypt_backup_without_cached_dek_raises(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        backup = BackupService.create_backup(user, backup_type='automatic')

        get_key_cache().evict(user.id)
        with pytest.raises(BackupKeyUnavailable):
            BackupService.get_backup_decrypted(backup, user)


def test_get_user_backups_ordered_desc(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        for _ in range(3):
            BackupService.create_backup(user, backup_type='automatic')

        backups = BackupService.get_user_backups(user.id, limit=10)
        assert len(backups) == 3
        assert all(b.user_id == user.id for b in backups)
        for i in range(len(backups) - 1):
            assert backups[i].created_at >= backups[i + 1].created_at


def test_create_backup_empty_user(app, test_user):
    with app.app_context():
        user = db.session.get(User, test_user)
        backup = BackupService.create_backup(user, backup_type='automatic')

        decrypted = BackupService.get_backup_decrypted(backup, user)
        assert decrypted['applications'] == []
        assert decrypted['emails'] == []


def test_backup_survives_password_change(app, test_user):
    """Kernpunkt: nach Password-Change bleiben alte Backups entschlüsselbar.

    Dies setzt voraus, dass der Re-Wrap-Flow den DEK stabil hält.
    """
    with app.app_context():
        user = db.session.get(User, test_user)
        backup = BackupService.create_backup(user, backup_type='automatic')

        # Simuliere Password-Change: neuer Salt, DEK bleibt identisch
        new_salt, new_encrypted_dek = EncryptionService.rewrap_dek_for_new_password(
            old_password="testpw",
            new_password="brandnew",
            old_salt=user.encryption_salt,
            encrypted_dek=user.encrypted_data_key,
        )
        user.encryption_salt = new_salt
        user.encrypted_data_key = new_encrypted_dek
        db.session.commit()

        # User loggt sich mit neuem Passwort ein → DEK landet wieder im Cache
        new_dek = EncryptionService.unlock_dek("brandnew", new_salt, new_encrypted_dek)
        get_key_cache().put(user.id, new_dek)

        decrypted = BackupService.get_backup_decrypted(backup, user)
        assert decrypted['applications'] == []


def test_manual_backup_type(app, user_with_data):
    with app.app_context():
        user = db.session.get(User, user_with_data)
        backup = BackupService.create_backup(user, backup_type='manual')
        assert backup.backup_type == 'manual'
