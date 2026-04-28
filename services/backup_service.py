"""Backup service for automatic backup creation with encryption and versioning"""

import json
from datetime import datetime
from models import User, Application, Email, BackupHistory
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from database import db


class BackupKeyUnavailable(RuntimeError):
    """Wird geworfen, wenn kein DEK im KeyCache liegt (Re-Login nötig)."""


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
    def _get_dek(user: User) -> bytes:
        """Holt den DEK aus dem KeyCache. Wirft BackupKeyUnavailable bei Miss."""
        dek = get_key_cache().get(user.id)
        if dek is None:
            raise BackupKeyUnavailable(
                "DEK nicht im Cache – User muss sich erneut anmelden, um Backups "
                "zu verschlüsseln/entschlüsseln."
            )
        return dek

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

        # Build backup data structure – inkl. Legacy-Felder + Soft-Delete-State.
        backup_data = {
            'applications': [
                {
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

        # Envelope-Encryption: DEK aus dem In-Memory-Cache (befüllt beim Login)
        # statt aus password_hash ableiten. Dadurch bleiben Backups bei einem
        # Passwort-Reset gültig (DEK ändert sich nicht, nur die KEK-Verpackung).
        dek = BackupService._get_dek(user)
        encrypted_data = EncryptionService.encrypt_data(plaintext, dek)

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
    def get_backup_decrypted(backup: BackupHistory, user: User) -> dict:
        """Entschlüsselt ein Backup mit dem im KeyCache liegenden DEK.

        Raises:
            BackupKeyUnavailable: Wenn DEK nicht gecacht ist (User muss sich
                neu anmelden, damit der DEK aus encrypted_data_key entsperrt wird).
            cryptography.fernet.InvalidToken: Bei korrupten Daten / falschem DEK.
        """
        dek = BackupService._get_dek(user)
        plaintext = EncryptionService.decrypt_data(backup.encrypted_data, dek)
        return json.loads(plaintext)

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
