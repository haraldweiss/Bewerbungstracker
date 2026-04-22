from database import db
from datetime import datetime
from enum import Enum
import uuid


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    imap_host = db.Column(db.String(255))
    imap_user = db.Column(db.String(255))
    imap_password_encrypted = db.Column(db.Text)  # Fernet encrypted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = db.relationship('SessionToken', backref='user', cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='user', cascade='all, delete-orphan')
    emails = db.relationship('Email', backref='user', cascade='all, delete-orphan')
    api_calls = db.relationship('ApiCall', backref='user', cascade='all, delete-orphan')

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


class ApplicationStatus(str, Enum):
    APPLIED = 'applied'
    INTERVIEW = 'interview'
    OFFER = 'offer'
    REJECTED = 'rejected'
    ARCHIVED = 'archived'


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    company = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default=ApplicationStatus.APPLIED.value)
    applied_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emails = db.relationship('Email', backref='application', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Application {self.company} - {self.position}>'


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
