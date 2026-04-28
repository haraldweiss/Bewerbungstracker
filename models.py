from database import db
from datetime import datetime
from enum import Enum
import uuid
from imap_service import IMAPCredentialManager


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    imap_host = db.Column(db.String(255))
    imap_user = db.Column(db.String(255))
    imap_password_encrypted = db.Column(db.Text)  # Fernet encrypted
    is_admin = db.Column(db.Boolean, default=False)
    email_confirmed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=False)

    # Envelope-Encryption: per-User-Salt + verschlüsselter Data Encryption Key.
    # encryption_salt = 16 Bytes random, encrypted_data_key = Fernet-DEK gewrapped
    # mit KEK aus PBKDF2(password, salt). Bei Passwort-Reset wird nur der KEK
    # ausgetauscht – DEK bleibt stabil → Backups bleiben entschlüsselbar.
    encryption_salt = db.Column(db.LargeBinary(16))
    encrypted_data_key = db.Column(db.Text)

    # User-Profil: Settings (Filter, Notification-Prefs, Apps-Script-URL etc.)
    # und CV-Daten (Lebenslauf-Editor + cvComparisons). Beides als JSON-Strings,
    # damit das Frontend frei strukturieren kann ohne neue Migrations.
    settings_json = db.Column(db.Text)   # JSON-Objekt, null = noch nicht gesetzt
    cv_data_json = db.Column(db.Text)    # JSON-Objekt {cv: {...}, comparisons: [...]}

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = db.relationship('SessionToken', backref='user', cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='user', cascade='all, delete-orphan')
    emails = db.relationship('Email', backref='user', cascade='all, delete-orphan')
    api_calls = db.relationship('ApiCall', backref='user', cascade='all, delete-orphan')
    confirmation_tokens = db.relationship('EmailConfirmationToken', backref='user', cascade='all, delete-orphan')

    @property
    def decrypted_imap_password(self) -> str:
        """Get decrypted IMAP password"""
        if self.imap_password_encrypted:
            return IMAPCredentialManager.decrypt_password(self.imap_password_encrypted)
        return None

    def __repr__(self):
        return f'<User {self.email}>'


class SessionToken(db.Model):
    __tablename__ = 'sessions'

    token = db.Column(db.String(500), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SessionToken {self.token[:20]}...>'


class EmailConfirmationToken(db.Model):
    __tablename__ = 'email_confirmation_tokens'

    token = db.Column(db.String(255), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<EmailConfirmationToken {self.token[:20]}...>'


class ApplicationStatus(str, Enum):
    """Statuswerte. Frontend nutzt die deutschen Bezeichnungen; die englischen
    bleiben als API-kompatibler Alias bestehen (legacy-Tests erwarten sie)."""
    # Deutsche Werte (Frontend + Legacy-DB)
    BEWORBEN = 'beworben'
    INTERVIEW = 'interview'
    ANTWORT = 'antwort'
    ABSAGE = 'absage'
    GHOSTING = 'ghosting'
    ZUSAGE = 'zusage'
    # Englische Aliase (älterer Test-Code)
    APPLIED = 'applied'
    OFFER = 'offer'
    REJECTED = 'rejected'
    ARCHIVED = 'archived'


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    company = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default=ApplicationStatus.BEWORBEN.value)
    applied_date = db.Column(db.Date)

    # Erweiterte Felder aus dem Legacy-Schema (data_service.py-Migration).
    # Alle nullable, damit alte Records ohne diese Felder lesbar bleiben.
    salary = db.Column(db.String(100))            # legacy: gehalt
    location = db.Column(db.String(200))          # legacy: ort
    contact_email = db.Column(db.String(255))     # legacy: email
    source = db.Column(db.String(50))             # legacy: quelle (linkedin/xing/...)
    link = db.Column(db.Text)
    notes = db.Column(db.Text)                    # legacy: notizen

    # Soft-Delete (Frontend hat /deleted, /recover, ?permanent=true Endpoints).
    deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emails = db.relationship('Email', backref='application', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Application {self.company} - {self.position}>'


class BackupHistory(db.Model):
    __tablename__ = 'backup_history'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)

    # Encrypted backup data (JSON)
    encrypted_data = db.Column(db.Text, nullable=False)

    # Format: 'json' or 'csv'
    format = db.Column(db.String(10), default='json')

    # Unencrypted version identifier (version 1, 2, 3, etc. per user)
    version = db.Column(db.Integer, default=1)

    # Type: 'automatic' (on entry creation) or 'manual' (user-requested)
    backup_type = db.Column(db.String(20), default='automatic')

    # Summary of backup (e.g., "5 applications, 12 emails")
    summary = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Foreign key relationship
    user = db.relationship('User', backref='backups', foreign_keys=[user_id])

    def __repr__(self):
        return f'<BackupHistory user={self.user_id} v{self.version} {self.created_at}>'


class Email(db.Model):
    __tablename__ = 'emails'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    message_id = db.Column(db.String(500))  # IMAP Message-ID
    subject = db.Column(db.String(500))
    from_address = db.Column(db.String(255))
    body = db.Column(db.Text)  # Optional, for search
    matched_application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=True)
    timestamp = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'message_id', name='uix_user_message_id'),
    )

    def __repr__(self):
        return f'<Email {self.subject[:50]}>'


class ApiCall(db.Model):
    __tablename__ = 'api_calls'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    endpoint = db.Column(db.String(255))  # e.g., '/api/analyze-email'
    model = db.Column(db.String(100))  # 'claude-haiku-3-5', 'claude-sonnet-4-6', etc.
    tokens_in = db.Column(db.Integer, default=0)
    tokens_out = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)  # USD
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<ApiCall {self.model} ${self.cost:.4f}>'
