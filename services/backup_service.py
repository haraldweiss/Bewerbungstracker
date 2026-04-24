"""Backup service for automatic backup creation with encryption and versioning"""

import json
from datetime import datetime
from models import User, Application, Email, BackupHistory
from services.encryption_service import EncryptionService
from database import db


class BackupService:
    """
    Service for creating, managing, and decrypting user backups.

    Features:
    - Automatic backup creation with encryption per user
    - Automatic pruning to keep max 10 backups per user
    - Backup versioning (sequential per user)
    - Backup decryption with user credentials
    """

    MAX_BACKUPS_PER_USER = 10

    @staticmethod
    def create_backup(user: User, backup_type: str = 'automatic') -> BackupHistory:
        """
        Create an encrypted backup of user's applications and emails.

        Args:
            user: User object to backup
            backup_type: 'automatic' or 'manual'

        Returns:
            BackupHistory object with encrypted data and metadata
        """
        # Collect applications for this user
        applications = Application.query.filter_by(user_id=user.id).all()

        # Collect emails for this user
        emails = Email.query.filter_by(user_id=user.id).all()

        # Build backup data structure
        backup_data = {
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
            'emails': [
                {
                    'id': email.id,
                    'message_id': email.message_id,
                    'subject': email.subject,
                    'from_address': email.from_address,
                    'timestamp': email.timestamp.isoformat() if email.timestamp else None,
                    'matched_application_id': email.matched_application_id,
                }
                for email in emails
            ],
            'backed_up_at': datetime.utcnow().isoformat(),
        }

        # Serialize to JSON
        plaintext = json.dumps(backup_data, indent=2)

        # Derive encryption key from user email and password hash
        encryption_key = EncryptionService.derive_user_key(
            user.email,
            user.password_hash
        )

        # Encrypt the backup data
        encrypted_data = EncryptionService.encrypt_data(plaintext, encryption_key)

        # Determine next version number
        latest_backup = BackupHistory.query.filter_by(
            user_id=user.id
        ).order_by(BackupHistory.version.desc()).first()

        next_version = (latest_backup.version + 1) if latest_backup else 1

        # Create backup summary
        app_count = len(applications)
        email_count = len(emails)
        summary = f"{app_count} applications, {email_count} emails"

        # Create BackupHistory record
        backup = BackupHistory(
            user_id=user.id,
            encrypted_data=encrypted_data,
            format='json',
            version=next_version,
            backup_type=backup_type,
            summary=summary,
        )

        db.session.add(backup)
        db.session.commit()

        # Prune old backups (keep only max 10)
        BackupService._prune_old_backups(user.id)

        return backup

    @staticmethod
    def _prune_old_backups(user_id: str) -> None:
        """
        Remove excess backups for user, keeping only the MAX_BACKUPS_PER_USER latest.

        Args:
            user_id: User ID to prune backups for
        """
        # Get all backups ordered by version descending
        all_backups = BackupHistory.query.filter_by(
            user_id=user_id
        ).order_by(BackupHistory.version.desc()).all()

        # If we have more than max, delete the oldest ones
        if len(all_backups) > BackupService.MAX_BACKUPS_PER_USER:
            backups_to_delete = all_backups[BackupService.MAX_BACKUPS_PER_USER:]

            for backup in backups_to_delete:
                db.session.delete(backup)

            db.session.commit()

    @staticmethod
    def get_backup_decrypted(
        backup: BackupHistory,
        user_email: str,
        user_password_hash: str
    ) -> dict:
        """
        Decrypt a backup and return the decrypted data.

        Args:
            backup: BackupHistory object to decrypt
            user_email: User's email for key derivation
            user_password_hash: User's password hash for key derivation

        Returns:
            Dictionary with decrypted applications and emails

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails (wrong credentials)
        """
        # Derive encryption key
        encryption_key = EncryptionService.derive_user_key(
            user_email,
            user_password_hash
        )

        # Decrypt the data
        plaintext = EncryptionService.decrypt_data(backup.encrypted_data, encryption_key)

        # Parse JSON
        decrypted_data = json.loads(plaintext)

        return decrypted_data

    @staticmethod
    def get_user_backups(user_id: str, limit: int = 10) -> list:
        """
        Get recent backups for a user.

        Args:
            user_id: User ID to get backups for
            limit: Maximum number of backups to return

        Returns:
            List of BackupHistory objects ordered by created_at descending
        """
        backups = BackupHistory.query.filter_by(
            user_id=user_id
        ).order_by(BackupHistory.created_at.desc()).limit(limit).all()

        return backups
