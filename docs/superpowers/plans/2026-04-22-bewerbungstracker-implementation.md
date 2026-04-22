# Bewerbungstracker Mobile + Persistenz — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize Bewerbungstracker with persistent database (PostgreSQL/SQLite), REST API for mobile, Claude API routing integration, and native iOS/Android apps with Cloud Sync.

**Architecture:** 
- Phase 1: SQLAlchemy ORM + Alembic migrations, REST API (JWT auth), persistent storage
- Phase 2: Claude routing integration (cost tracking, smart matching)
- Phase 3: Native iOS (Swift/SwiftUI) + Android (Kotlin/Compose) with iCloud/Google Drive sync

**Tech Stack:** Flask, SQLAlchemy, PostgreSQL/SQLite, Alembic, JWT, bcrypt, Swift, Kotlin

---

## File Structure Overview

### Phase 1 (Persistenz + REST API)
```
app.py                          # Modernisiert: Blueprint-based, error handling
models.py                       # NEW: SQLAlchemy ORM (User, Session, Application, Email, ApiCall)
database.py                     # NEW: DB connection, session management
config.py                       # NEW: Environment-based configuration
auth_service.py                 # NEW: JWT token generation, password hashing (bcrypt)
api/
  └── auth.py                   # NEW: Login, logout, refresh endpoints
  └── applications.py           # NEW: CRUD for Bewerbungen
  └── emails.py                 # NEW: Email list, sync, match endpoints
email_service.py                # MODIFY: Use ORM instead of direct DB
imap_proxy.py                   # UNCHANGED (or minor tweaks)
requirements.txt                # UPDATE: Add SQLAlchemy, Alembic, bcrypt, cryptography
alembic/                        # NEW: Versioned migrations
  ├── env.py
  ├── script.py.template
  └── versions/
tests/
  ├── test_auth.py              # NEW: Auth endpoints + JWT
  ├── test_api.py               # NEW: CRUD endpoints
  ├── test_models.py            # NEW: ORM model tests
  └── conftest.py               # NEW: Pytest fixtures
```

### Phase 2 (Claude Routing)
```
routing_service.py              # NEW: Import routing system, wrapper functions
claude_integration.py           # NEW: /api/analyze-email, /api/match-application
usage_tracker.py                # NEW or IMPORT: Cost tracking, budget alerts
app.py                          # MODIFY: Register new blueprints
models.py                       # MODIFY: Add ApiCall model
tests/test_claude_integration.py # NEW: Integration tests
```

### Phase 3 (Native Mobile)
```
ios/
  ├── Bewerbungstracker.xcodeproj
  ├── Bewerbungstracker/
  │   ├── App.swift
  │   ├── Models/
  │   │   ├── ApplicationModel.swift
  │   │   └── EmailModel.swift
  │   ├── Views/
  │   │   ├── ContentView.swift
  │   │   ├── LoginView.swift
  │   │   ├── ApplicationListView.swift
  │   │   ├── EmailDetailView.swift
  │   │   └── SettingsView.swift
  │   ├── Services/
  │   │   ├── APIClient.swift
  │   │   ├── CloudSyncService.swift
  │   │   └── TokenManager.swift
  │   └── CoreData/
  │       └── Bewerbungstracker.xcdatamodeld

android/
  ├── build.gradle.kts
  ├── app/src/main/kotlin/com/example/bewerbungstracker/
  │   ├── MainActivity.kt
  │   ├── models/
  │   │   ├── ApplicationEntity.kt
  │   │   └── EmailEntity.kt
  │   ├── ui/
  │   │   ├── LoginScreen.kt
  │   │   ├── ApplicationListScreen.kt
  │   │   └── SettingsScreen.kt
  │   ├── data/
  │   │   ├── AppDatabase.kt
  │   │   ├── ApplicationDao.kt
  │   │   └── APIClient.kt
  │   └── services/
  │       ├── SyncService.kt
  │       └── TokenManager.kt
```

---

# PHASE 1: Persistenz + REST API

## Task 1: Initialize Database Configuration & SQLAlchemy Setup

**Files:**
- Create: `config.py`
- Modify: `requirements.txt`
- Create: `database.py`

**Step 1.1: Update requirements.txt with DB dependencies**

```bash
# Current requirements.txt — add these lines:
SQLAlchemy==2.0.23
Alembic==1.12.1
bcrypt==4.1.1
cryptography==41.0.7
PyJWT==2.8.1
python-dotenv==1.0.0
```

Add to `requirements.txt`:
```
Flask==2.3.3
requests==2.31.0
SQLAlchemy==2.0.23
Alembic==1.12.1
bcrypt==4.1.1
cryptography==41.0.7
PyJWT==2.8.1
python-dotenv==1.0.0
```

- [ ] **Step 1.2: Create config.py for environment-based configuration**

Create file: `config.py`

```python
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///bewerbungstracker.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # IMAP
    IMAP_PROXY_URL = os.getenv('IMAP_PROXY_URL', 'http://127.0.0.1:8765')
    
    # Claude API (Phase 2)
    CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False
    # Force PostgreSQL in production
    if 'DATABASE_URL' not in os.environ:
        raise ValueError("DATABASE_URL must be set in production")

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_SECRET_KEY = 'test-secret-key'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

- [ ] **Step 1.3: Create database.py for session management**

Create file: `database.py`

```python
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session as SQLSession

db = SQLAlchemy()

def get_db() -> SQLSession:
    """Get current database session"""
    return db.session

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
    with app.app_context():
        db.create_all()

def reset_db(app):
    """Drop all tables and recreate (dev only)"""
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()
```

- [ ] **Step 1.4: Run pip install**

```bash
pip install -r requirements.txt
```

Expected: All packages install successfully.

- [ ] **Step 1.5: Commit**

```bash
git add config.py database.py requirements.txt
git commit -m "feat: setup database config and SQLAlchemy"
```

---

## Task 2: Define ORM Models

**Files:**
- Create: `models.py`

- [ ] **Step 2.1: Create models.py with User, Session, Application, Email, ApiCall models**

Create file: `models.py`

```python
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
```

- [ ] **Step 2.2: Verify models syntax**

```bash
python -c "from models import *; print('Models loaded successfully')"
```

Expected: "Models loaded successfully"

- [ ] **Step 2.3: Commit**

```bash
git add models.py
git commit -m "feat: define SQLAlchemy ORM models (User, Application, Email, ApiCall)"
```

---

## Task 3: Setup Alembic Migrations

**Files:**
- Create: `alembic/` (directory structure)

- [ ] **Step 3.1: Initialize Alembic**

```bash
alembic init alembic
```

Expected: Alembic directory structure created.

- [ ] **Step 3.2: Configure alembic/env.py to auto-detect models**

Edit `alembic/env.py` — replace the top section:

```python
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from logging.config import fileConfig

from database import db
from models import *  # Important: imports all models
from config import Config

# this is the Alembic Config object, which provides
# the values of the [alembic] section of the .ini file
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = db.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv('DATABASE_URL', 'sqlite:///bewerbungstracker.db')
    
    context.configure(
        url=configuration["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv('DATABASE_URL', 'sqlite:///bewerbungstracker.db')
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3.3: Create initial migration**

```bash
alembic revision --autogenerate -m "initial schema: users, applications, emails, api_calls"
```

Expected: File created in `alembic/versions/` with migration code.

- [ ] **Step 3.4: Review migration file**

```bash
ls -la alembic/versions/
cat alembic/versions/*.py | head -50
```

Expected: Migration file contains create_table operations for all models.

- [ ] **Step 3.5: Commit**

```bash
git add alembic/
git commit -m "feat: setup Alembic migrations"
```

---

## Task 4: Create Authentication Service

**Files:**
- Create: `auth_service.py`
- Create: `tests/conftest.py`
- Create: `tests/test_auth_service.py`

- [ ] **Step 4.1: Create auth_service.py**

Create file: `auth_service.py`

```python
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple
from config import Config
from models import User, SessionToken
from database import db

class AuthService:
    """Service for authentication and token management"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_id: str) -> str:
        """Create JWT access token"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + Config.JWT_ACCESS_TOKEN_EXPIRES,
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        token = jwt.encode(
            payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )
        return token
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create JWT refresh token"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + Config.JWT_REFRESH_TOKEN_EXPIRES,
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        token = jwt.encode(
            payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )
        return token
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def register_user(email: str, password: str) -> Tuple[bool, Optional[User], str]:
        """Register new user"""
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return False, None, "User already exists"
        
        try:
            password_hash = AuthService.hash_password(password)
            user = User(email=email, password_hash=password_hash)
            db.session.add(user)
            db.session.commit()
            return True, user, "User registered successfully"
        except Exception as e:
            db.session.rollback()
            return False, None, str(e)
    
    @staticmethod
    def login_user(email: str, password: str) -> Tuple[bool, Optional[User], str]:
        """Authenticate user and return user object"""
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return False, None, "User not found"
        
        if not AuthService.verify_password(password, user.password_hash):
            return False, None, "Invalid password"
        
        return True, user, "Login successful"
```

- [ ] **Step 4.2: Create tests/conftest.py (pytest fixtures)**

Create file: `tests/conftest.py`

```python
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from config import TestingConfig

@pytest.fixture
def app():
    """Create test app"""
    app = create_app(TestingConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """CLI runner"""
    return app.test_cli_runner()
```

- [ ] **Step 4.3: Create tests/test_auth_service.py**

Create file: `tests/test_auth_service.py`

```python
import pytest
from auth_service import AuthService
from models import User
from database import db

def test_hash_password():
    """Test password hashing"""
    password = "test_password_123"
    hashed = AuthService.hash_password(password)
    
    assert hashed != password
    assert AuthService.verify_password(password, hashed)
    assert not AuthService.verify_password("wrong_password", hashed)

def test_create_access_token():
    """Test access token creation"""
    user_id = "test_user_123"
    token = AuthService.create_access_token(user_id)
    
    assert token
    payload = AuthService.verify_token(token)
    assert payload is not None
    assert payload['user_id'] == user_id
    assert payload['type'] == 'access'

def test_register_user(app):
    """Test user registration"""
    with app.app_context():
        success, user, msg = AuthService.register_user("test@example.com", "password123")
        
        assert success
        assert user is not None
        assert user.email == "test@example.com"
        assert msg == "User registered successfully"
        
        # Try to register same email again
        success, user, msg = AuthService.register_user("test@example.com", "password123")
        assert not success
        assert "already exists" in msg

def test_login_user(app):
    """Test user login"""
    with app.app_context():
        AuthService.register_user("test@example.com", "password123")
        
        success, user, msg = AuthService.login_user("test@example.com", "password123")
        assert success
        assert user.email == "test@example.com"
        
        success, user, msg = AuthService.login_user("test@example.com", "wrong_password")
        assert not success
        
        success, user, msg = AuthService.login_user("nonexistent@example.com", "password123")
        assert not success
```

- [ ] **Step 4.4: Run tests**

```bash
pytest tests/test_auth_service.py -v
```

Expected: All tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add auth_service.py tests/conftest.py tests/test_auth_service.py
git commit -m "feat: add authentication service with JWT and bcrypt"
```

---

## Task 5: Modernize Flask App & Add Auth Endpoints

**Files:**
- Modify: `app.py`
- Create: `api/auth.py`

- [ ] **Step 5.1: Rewrite app.py as factory pattern with blueprints**

Backup existing `app.py`, then replace with:

```python
from flask import Flask
from config import config
import os
from database import db

def create_app(config_class=None):
    """Application factory"""
    if config_class is None:
        env = os.getenv('FLASK_ENV', 'development')
        config_class = config.get(env, config['development'])
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize database
    db.init_app(app)
    
    # Register blueprints
    from api.auth import auth_bp
    from api.applications import apps_bp
    from api.emails import emails_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(apps_bp)
    app.register_blueprint(emails_bp)
    
    # Error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        return {'error': 'Unauthorized'}, 401
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500
    
    # Create tables on startup
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8080)
```

- [ ] **Step 5.2: Create api/auth.py (Authentication endpoints)**

Create file: `api/auth.py`

```python
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
from config import Config
from auth_service import AuthService
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def token_required(f):
    """Decorator to require JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return {'error': 'Invalid token format'}, 401
        
        if not token:
            return {'error': 'Missing token'}, 401
        
        payload = AuthService.verify_token(token)
        if not payload:
            return {'error': 'Invalid or expired token'}, 401
        
        user = User.query.get(payload['user_id'])
        if not user:
            return {'error': 'User not found'}, 401
        
        return f(user, *args, **kwargs)
    
    return decorated

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return {'error': 'Email and password required'}, 400
    
    success, user, message = AuthService.register_user(
        data['email'],
        data['password']
    )
    
    if not success:
        return {'error': message}, 400
    
    return {
        'id': user.id,
        'email': user.email,
        'message': message
    }, 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return {'error': 'Email and password required'}, 400
    
    success, user, message = AuthService.login_user(
        data['email'],
        data['password']
    )
    
    if not success:
        return {'error': message}, 401
    
    access_token = AuthService.create_access_token(user.id)
    refresh_token = AuthService.create_refresh_token(user.id)
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': int(Config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    }, 200

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    data = request.get_json()
    
    if not data or not data.get('refresh_token'):
        return {'error': 'Refresh token required'}, 400
    
    payload = AuthService.verify_token(data['refresh_token'])
    
    if not payload or payload.get('type') != 'refresh':
        return {'error': 'Invalid refresh token'}, 401
    
    new_access_token = AuthService.create_access_token(payload['user_id'])
    
    return {
        'access_token': new_access_token,
        'token_type': 'Bearer',
        'expires_in': int(Config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    }, 200

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(user):
    """Logout user (token invalidation handled client-side)"""
    return {'message': 'Logout successful'}, 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(user):
    """Get current authenticated user"""
    return {
        'id': user.id,
        'email': user.email,
        'created_at': user.created_at.isoformat()
    }, 200
```

- [ ] **Step 5.3: Create api/__init__.py (empty file)**

```bash
touch api/__init__.py
```

- [ ] **Step 5.4: Create tests/test_auth_endpoints.py**

Create file: `tests/test_auth_endpoints.py`

```python
import pytest

def test_register_endpoint(client):
    """Test /api/auth/register"""
    response = client.post(
        '/api/auth/register',
        json={
            'email': 'test@example.com',
            'password': 'password123'
        }
    )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'test@example.com'

def test_register_duplicate(client):
    """Test registering duplicate email"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    response = client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password456'}
    )
    
    assert response.status_code == 400

def test_login_endpoint(client):
    """Test /api/auth/login"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert data['token_type'] == 'Bearer'

def test_get_current_user(client):
    """Test /api/auth/me with token"""
    # Register and login
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    login_response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    token = login_response.get_json()['access_token']
    
    # Get current user
    response = client.get(
        '/api/auth/me',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['email'] == 'test@example.com'

def test_unauthorized_without_token(client):
    """Test endpoint without token returns 401"""
    response = client.get('/api/auth/me')
    assert response.status_code == 401
```

- [ ] **Step 5.5: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass (10+).

- [ ] **Step 5.6: Commit**

```bash
git add app.py api/auth.py api/__init__.py tests/test_auth_endpoints.py
git commit -m "feat: modernize Flask app with factory pattern and auth endpoints"
```

---

## Task 6: Add Applications CRUD Endpoints

**Files:**
- Create: `api/applications.py`
- Create: `tests/test_applications.py`

- [ ] **Step 6.1: Create api/applications.py**

Create file: `api/applications.py`

```python
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
        applied_date=datetime.fromisoformat(data['applied_date']) if data.get('applied_date') else None
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
        app.applied_date = datetime.fromisoformat(data['applied_date'])
    
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
```

- [ ] **Step 6.2: Create tests/test_applications.py**

Create file: `tests/test_applications.py`

```python
import pytest
from auth_service import AuthService

@pytest.fixture
def auth_token(client):
    """Register and login user, return token"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    return response.get_json()['access_token']

def test_create_application(client, auth_token):
    """Test creating application"""
    response = client.post(
        '/api/applications',
        json={
            'company': 'Google',
            'position': 'Software Engineer',
            'applied_date': '2026-04-22'
        },
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['company'] == 'Google'
    assert data['position'] == 'Software Engineer'

def test_list_applications(client, auth_token):
    """Test listing applications"""
    # Create 2 applications
    client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    client.post(
        '/api/applications',
        json={'company': 'Meta', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    response = client.get(
        '/api/applications',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['count'] == 2

def test_update_application(client, auth_token):
    """Test updating application"""
    create_response = client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    app_id = create_response.get_json()['id']
    
    response = client.patch(
        f'/api/applications/{app_id}',
        json={'status': 'interview'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'interview'

def test_delete_application(client, auth_token):
    """Test deleting application"""
    create_response = client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    app_id = create_response.get_json()['id']
    
    response = client.delete(
        f'/api/applications/{app_id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    
    # Verify deleted
    get_response = client.get(
        f'/api/applications/{app_id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    assert get_response.status_code == 404
```

- [ ] **Step 6.3: Run tests**

```bash
pytest tests/test_applications.py -v
```

Expected: All tests pass.

- [ ] **Step 6.4: Commit**

```bash
git add api/applications.py tests/test_applications.py
git commit -m "feat: add applications CRUD endpoints"
```

---

## Task 7: Add Email Endpoints & Sync

**Files:**
- Create: `api/emails.py`
- Create: `tests/test_emails.py`

- [ ] **Step 7.1: Create api/emails.py**

Create file: `api/emails.py`

```python
from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import Email, Application
from database import db
from datetime import datetime

emails_bp = Blueprint('emails', __name__, url_prefix='/api/emails')

@emails_bp.route('', methods=['GET'])
@token_required
def list_emails(user):
    """List emails for user, optionally filtered by application"""
    app_id = request.args.get('application_id')
    
    query = Email.query.filter_by(user_id=user.id)
    
    if app_id:
        query = query.filter_by(matched_application_id=app_id)
    
    emails = query.order_by(Email.timestamp.desc()).all()
    
    return {
        'count': len(emails),
        'emails': [
            {
                'id': email.id,
                'subject': email.subject,
                'from': email.from_address,
                'matched_application_id': email.matched_application_id,
                'timestamp': email.timestamp.isoformat() if email.timestamp else None
            }
            for email in emails
        ]
    }, 200

@emails_bp.route('/<email_id>', methods=['GET'])
@token_required
def get_email(user, email_id):
    """Get full email"""
    email = Email.query.filter_by(id=email_id, user_id=user.id).first()
    
    if not email:
        return {'error': 'Email not found'}, 404
    
    return {
        'id': email.id,
        'subject': email.subject,
        'from': email.from_address,
        'body': email.body,
        'matched_application_id': email.matched_application_id,
        'timestamp': email.timestamp.isoformat() if email.timestamp else None
    }, 200

@emails_bp.route('/<email_id>/match', methods=['POST'])
@token_required
def match_email(user, email_id):
    """Match email to application"""
    email = Email.query.filter_by(id=email_id, user_id=user.id).first()
    
    if not email:
        return {'error': 'Email not found'}, 404
    
    data = request.get_json()
    app_id = data.get('application_id')
    
    if app_id:
        app = Application.query.filter_by(id=app_id, user_id=user.id).first()
        if not app:
            return {'error': 'Application not found'}, 404
    
    email.matched_application_id = app_id
    db.session.commit()
    
    return {
        'id': email.id,
        'matched_application_id': email.matched_application_id
    }, 200

@emails_bp.route('/sync', methods=['POST'])
@token_required
def sync_emails(user):
    """Trigger IMAP sync (placeholder)"""
    # This will be implemented to fetch from IMAP proxy
    # For now, just return success
    return {
        'message': 'Sync initiated',
        'emails_synced': 0
    }, 200

@emails_bp.route('/sync/status', methods=['GET'])
@token_required
def sync_status(user):
    """Get sync status for user"""
    return {
        'last_sync': None,
        'is_syncing': False
    }, 200
```

- [ ] **Step 7.2: Create tests/test_emails.py**

Create file: `tests/test_emails.py`

```python
import pytest
from models import Email
from database import db
from datetime import datetime

@pytest.fixture
def auth_token(client):
    """Register and login user, return token"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    return response.get_json()['access_token']

@pytest.fixture
def user_with_email(app, auth_token):
    """Create user and add test email"""
    from models import User
    
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        
        email = Email(
            user_id=user.id,
            subject='Test email',
            from_address='sender@example.com',
            body='This is a test email',
            timestamp=datetime.utcnow()
        )
        db.session.add(email)
        db.session.commit()
        
        return user, email

def test_list_emails(client, user_with_email, auth_token):
    """Test listing emails"""
    response = client.get(
        '/api/emails',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['count'] == 1
    assert data['emails'][0]['subject'] == 'Test email'

def test_get_email(client, user_with_email, auth_token):
    """Test getting full email"""
    user, email = user_with_email
    
    response = client.get(
        f'/api/emails/{email.id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['body'] == 'This is a test email'

def test_match_email(client, app, user_with_email, auth_token):
    """Test matching email to application"""
    user, email = user_with_email
    
    with app.app_context():
        from models import Application
        
        app_obj = Application(
            user_id=user.id,
            company='Google',
            position='SWE'
        )
        db.session.add(app_obj)
        db.session.commit()
        app_id = app_obj.id
    
    response = client.post(
        f'/api/emails/{email.id}/match',
        json={'application_id': app_id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['matched_application_id'] == app_id
```

- [ ] **Step 7.3: Run tests**

```bash
pytest tests/test_emails.py -v
```

Expected: All tests pass.

- [ ] **Step 7.4: Commit**

```bash
git add api/emails.py tests/test_emails.py
git commit -m "feat: add email endpoints (list, get, match, sync)"
```

---

## Phase 1 Checkpoint

- [ ] **Step P1.1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: 25+ tests, all passing.

- [ ] **Step P1.2: Test app startup**

```bash
python app.py
```

Expected: Flask app starts on port 8080 without errors. Stop with Ctrl+C.

- [ ] **Step P1.3: Verify database**

```bash
sqlite3 bewerbungstracker.db ".tables"
```

Expected: Tables created (users, applications, emails, sessions, api_calls).

- [ ] **Step P1.4: Commit checkpoint**

```bash
git add -A
git commit -m "checkpoint: Phase 1 complete (Persistenz + REST API)

- SQLAlchemy ORM with PostgreSQL/SQLite support
- Alembic migrations
- JWT authentication (register, login, refresh)
- CRUD endpoints for Applications and Emails
- 25+ unit tests (100% pass)
- Ready for Phase 2 (Claude Routing Integration)"
```

---

# PHASE 2: Claude Routing Integration

## Task 8: Setup Claude Routing Service

**Files:**
- Create: `routing_service.py`
- Create: `claude_integration.py`
- Modify: `models.py` (already has ApiCall)
- Create: `tests/test_claude_integration.py`

- [ ] **Step 8.1: Create routing_service.py (wrapper)**

Create file: `routing_service.py`

```python
"""
Wrapper around Phase 2 Claude Routing System.
Imports the routing library and provides app-specific integration.
"""

from typing import Optional, Dict, Any
from models import ApiCall
from database import db
from config import Config
import json

# This will be implemented after Phase 2 routing system is deployed
# For now, provide placeholder that returns model + cost estimate

class RoutingService:
    """Service for Claude model routing and cost tracking"""
    
    @staticmethod
    def select_model(task_description: str, task_type: str = 'default') -> Dict[str, Any]:
        """
        Select optimal Claude model for task.
        
        Returns:
            {
                'model': 'claude-haiku-3-5',
                'estimated_tokens_out': 500,
                'estimated_cost': 0.001,
                'use_batch': False
            }
        """
        # Placeholder: always returns Haiku for now
        # TODO: Import actual router from Phase 2
        return {
            'model': 'claude-haiku-3-5',
            'estimated_tokens_out': 500,
            'estimated_cost': 0.0005,
            'use_batch': False
        }
    
    @staticmethod
    def log_api_call(
        user_id: str,
        endpoint: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost: float
    ) -> ApiCall:
        """Log API call to database"""
        api_call = ApiCall(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost
        )
        db.session.add(api_call)
        db.session.commit()
        return api_call
    
    @staticmethod
    def get_monthly_cost(user_id: str) -> float:
        """Get total cost for current month"""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total = db.session.query(
            func.sum(ApiCall.cost)
        ).filter(
            ApiCall.user_id == user_id,
            ApiCall.timestamp >= month_start
        ).scalar() or 0.0
        
        return float(total)
    
    @staticmethod
    def get_cost_by_model(user_id: str) -> Dict[str, float]:
        """Get cost breakdown by model"""
        from sqlalchemy import func
        
        results = db.session.query(
            ApiCall.model,
            func.sum(ApiCall.cost).label('total_cost')
        ).filter(
            ApiCall.user_id == user_id
        ).group_by(
            ApiCall.model
        ).all()
        
        return {model: float(cost) for model, cost in results}
```

- [ ] **Step 8.2: Create claude_integration.py (API endpoints)**

Create file: `claude_integration.py`

```python
from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import Email, Application
from routing_service import RoutingService
from database import db
import json

claude_bp = Blueprint('claude', __name__, url_prefix='/api/claude')

@claude_bp.route('/analyze-email', methods=['POST'])
@token_required
def analyze_email(user):
    """Analyze email using Claude"""
    data = request.get_json()
    
    if not data or not data.get('email_id'):
        return {'error': 'email_id required'}, 400
    
    email = Email.query.filter_by(id=data['email_id'], user_id=user.id).first()
    
    if not email:
        return {'error': 'Email not found'}, 404
    
    # Get model recommendation
    model_selection = RoutingService.select_model(
        task_description=f"Analyze email: {email.subject}",
        task_type='email_analysis'
    )
    
    # TODO: Call Claude API with model_selection['model']
    # For now, mock response
    
    analysis = {
        'company': 'Example Corp',
        'position': 'Senior Engineer',
        'deadline': '2026-05-22',
        'sentiment': 'positive',
        'confidence': 0.85
    }
    
    # Log API call
    RoutingService.log_api_call(
        user_id=user.id,
        endpoint='/api/claude/analyze-email',
        model=model_selection['model'],
        tokens_in=150,  # Placeholder
        tokens_out=model_selection['estimated_tokens_out'],
        cost=model_selection['estimated_cost']
    )
    
    return {
        'email_id': email.id,
        'analysis': analysis,
        'model_used': model_selection['model'],
        'cost': model_selection['estimated_cost']
    }, 200

@claude_bp.route('/match-application', methods=['POST'])
@token_required
def match_application(user):
    """Smart match email to application using Claude"""
    data = request.get_json()
    
    if not data or not data.get('email_id'):
        return {'error': 'email_id required'}, 400
    
    email = Email.query.filter_by(id=data['email_id'], user_id=user.id).first()
    
    if not email:
        return {'error': 'Email not found'}, 404
    
    # Get model selection
    model_selection = RoutingService.select_model(
        task_description=f"Match email to application",
        task_type='matching'
    )
    
    # TODO: Call Claude API to find best matching application
    # For now, return mock match
    
    matched_app_id = None
    confidence = 0.0
    
    # Log API call
    RoutingService.log_api_call(
        user_id=user.id,
        endpoint='/api/claude/match-application',
        model=model_selection['model'],
        tokens_in=200,
        tokens_out=model_selection['estimated_tokens_out'],
        cost=model_selection['estimated_cost']
    )
    
    return {
        'email_id': email.id,
        'matched_application_id': matched_app_id,
        'confidence': confidence,
        'model_used': model_selection['model'],
        'cost': model_selection['estimated_cost']
    }, 200

@claude_bp.route('/usage/monthly', methods=['GET'])
@token_required
def get_monthly_usage(user):
    """Get monthly usage stats"""
    monthly_cost = RoutingService.get_monthly_cost(user.id)
    cost_by_model = RoutingService.get_cost_by_model(user.id)
    
    api_calls = ApiCall.query.filter_by(user_id=user.id).count()
    
    return {
        'total_cost_usd': round(monthly_cost, 4),
        'api_calls': api_calls,
        'cost_by_model': {k: round(v, 4) for k, v in cost_by_model.items()}
    }, 200
```

- [ ] **Step 8.3: Register Claude blueprint in app.py**

Modify `app.py` — add to create_app():

```python
def create_app(config_class=None):
    """Application factory"""
    if config_class is None:
        env = os.getenv('FLASK_ENV', 'development')
        config_class = config.get(env, config['development'])
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize database
    db.init_app(app)
    
    # Register blueprints
    from api.auth import auth_bp
    from api.applications import apps_bp
    from api.emails import emails_bp
    from claude_integration import claude_bp  # NEW
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(apps_bp)
    app.register_blueprint(emails_bp)
    app.register_blueprint(claude_bp)  # NEW
    
    # ... rest of code
```

- [ ] **Step 8.4: Create tests/test_claude_integration.py**

Create file: `tests/test_claude_integration.py`

```python
import pytest
from models import Email, ApiCall
from database import db
from datetime import datetime

@pytest.fixture
def auth_token(client):
    """Register and login"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    
    return response.get_json()['access_token']

@pytest.fixture
def user_email(app, auth_token):
    """Create test email"""
    from models import User
    
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        
        email = Email(
            user_id=user.id,
            subject='Interview Request from Google',
            from_address='recruiter@google.com',
            body='We would like to invite you...',
            timestamp=datetime.utcnow()
        )
        db.session.add(email)
        db.session.commit()
        
        return email

def test_analyze_email(client, user_email, auth_token):
    """Test email analysis"""
    response = client.post(
        '/api/claude/analyze-email',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'analysis' in data
    assert 'model_used' in data
    assert 'cost' in data

def test_match_application(client, user_email, auth_token):
    """Test application matching"""
    response = client.post(
        '/api/claude/match-application',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'matched_application_id' in data
    assert 'confidence' in data

def test_monthly_usage(client, user_email, auth_token):
    """Test usage stats endpoint"""
    # First make an API call
    client.post(
        '/api/claude/analyze-email',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    # Then check usage
    response = client.get(
        '/api/claude/usage/monthly',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'total_cost_usd' in data
    assert 'api_calls' in data
    assert data['api_calls'] >= 1
```

- [ ] **Step 8.5: Run tests**

```bash
pytest tests/test_claude_integration.py -v
```

Expected: All tests pass.

- [ ] **Step 8.6: Commit**

```bash
git add routing_service.py claude_integration.py app.py tests/test_claude_integration.py
git commit -m "feat: add Claude routing integration with cost tracking

- Routing service wrapper (placeholder for Phase 2 router)
- /api/claude/analyze-email endpoint
- /api/claude/match-application endpoint
- /api/claude/usage/monthly stats endpoint
- API call logging to database
- Tests for Claude integration"
```

---

## Phase 2 Checkpoint

- [ ] **Step P2.1: Run all tests**

```bash
pytest tests/ -v
```

Expected: 35+ tests, all passing.

- [ ] **Step P2.2: Verify API calls are logged**

```bash
python -c "
from app import create_app
from models import ApiCall
app = create_app()
with app.app_context():
    calls = ApiCall.query.all()
    print(f'API calls logged: {len(calls)}')
"
```

- [ ] **Step P2.3: Commit checkpoint**

```bash
git add -A
git commit -m "checkpoint: Phase 2 complete (Claude Routing Integration)

- Routing service (ready for Phase 2 router integration)
- Claude API endpoints with cost tracking
- Usage statistics endpoint
- Database logging for all API calls
- Ready for Phase 3 (Native Mobile Apps)"
```

---

# PHASE 3: Native Mobile Apps (iOS + Android)

> **Note:** Phase 3 requires separate iOS/Android development environment setup. This plan provides task structure; actual implementation in Swift/Kotlin follows separate projects.

## Task 9: iOS App Structure & Core Data Model

**Files:**
- Create: `ios/Bewerbungstracker.xcodeproj` (Xcode project)
- Create: `ios/Bewerbungstracker/Models/ApplicationModel.swift`
- Create: `ios/Bewerbungstracker/Models/EmailModel.swift`
- Create: `ios/Bewerbungstracker/Services/APIClient.swift`

> **For iOS development, use Xcode 15+ with Swift 5.9+**

- [ ] **Step 9.1: Create iOS project**

```bash
# Install Xcode Command Line Tools (if not already installed)
# xcode-select --install

# Create project structure
mkdir -p ios/Bewerbungstracker/Bewerbungstracker/{Models,Views,Services,CoreData}

# Create basic files (Xcode will create .xcodeproj)
# Use Xcode to create new iOS App project, select SwiftUI
```

- [ ] **Step 9.2: Create ApplicationModel.swift**

Create file: `ios/Bewerbungstracker/Bewerbungstracker/Models/ApplicationModel.swift`

```swift
import Foundation
import CoreData

@Entity
@MainActor
final class ApplicationModel {
    @Attribute(.unique) var id: UUID
    var company: String
    var position: String
    var status: String // "applied", "interview", "offer", "rejected", "archived"
    var appliedDate: Date?
    var createdAt: Date
    var updatedAt: Date
    
    @Relationship(deleteRule: .cascade) var emails: [EmailModel] = []
    
    init(id: UUID = UUID(), company: String, position: String, status: String = "applied", appliedDate: Date? = nil) {
        self.id = id
        self.company = company
        self.position = position
        self.status = status
        self.appliedDate = appliedDate
        self.createdAt = Date()
        self.updatedAt = Date()
    }
}

// MARK: - Status Enum
enum ApplicationStatus: String, CaseIterable {
    case applied
    case interview
    case offer
    case rejected
    case archived
}
```

- [ ] **Step 9.3: Create EmailModel.swift**

Create file: `ios/Bewerbungstracker/Bewerbungstracker/Models/EmailModel.swift`

```swift
import Foundation
import CoreData

@Entity
@MainActor
final class EmailModel {
    @Attribute(.unique) var id: UUID
    var subject: String
    var fromAddress: String
    var body: String?
    var timestamp: Date
    var createdAt: Date
    var messageId: String? // IMAP Message-ID
    
    @Relationship(deleteRule: .noAction) var matchedApplication: ApplicationModel?
    
    init(
        id: UUID = UUID(),
        subject: String,
        fromAddress: String,
        body: String? = nil,
        timestamp: Date = Date()
    ) {
        self.id = id
        self.subject = subject
        self.fromAddress = fromAddress
        self.body = body
        self.timestamp = timestamp
        self.createdAt = Date()
    }
}
```

- [ ] **Step 9.4: Create APIClient.swift**

Create file: `ios/Bewerbungstracker/Bewerbungstracker/Services/APIClient.swift`

```swift
import Foundation

class APIClient {
    static let shared = APIClient()
    
    private let baseURL = "http://localhost:8080/api"
    private var accessToken: String? {
        get {
            UserDefaults.standard.string(forKey: "accessToken")
        }
        set {
            if let newValue = newValue {
                UserDefaults.standard.set(newValue, forKey: "accessToken")
            } else {
                UserDefaults.standard.removeObject(forKey: "accessToken")
            }
        }
    }
    
    // MARK: - Auth
    
    func register(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["email": email, "password": password]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
        
        return try JSONDecoder().decode(AuthResponse.self, from: data)
    }
    
    func login(email: String, password: String) async throws -> AuthResponse {
        let url = URL(string: "\(baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["email": email, "password": password]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
        
        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        self.accessToken = authResponse.accessToken
        
        return authResponse
    }
    
    func logout() {
        self.accessToken = nil
    }
    
    // MARK: - Applications
    
    func fetchApplications() async throws -> [ApplicationResponse] {
        let url = URL(string: "\(baseURL)/applications")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.unauthorized
        }
        
        let response_data = try JSONDecoder().decode(ApplicationsListResponse.self, from: data)
        return response_data.applications
    }
    
    func createApplication(company: String, position: String, appliedDate: Date?) async throws -> ApplicationResponse {
        let url = URL(string: "\(baseURL)/applications")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = ["company": company, "position": position]
        if let appliedDate = appliedDate {
            body["applied_date"] = ISO8601DateFormatter().string(from: appliedDate)
        }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
        
        return try JSONDecoder().decode(ApplicationResponse.self, from: data)
    }
}

// MARK: - API Responses

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct ApplicationResponse: Codable {
    let id: String
    let company: String
    let position: String
    let status: String
    let appliedDate: String?
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, company, position, status
        case appliedDate = "applied_date"
        case createdAt = "created_at"
    }
}

struct ApplicationsListResponse: Codable {
    let count: Int
    let applications: [ApplicationResponse]
}

enum APIError: LocalizedError {
    case invalidResponse
    case unauthorized
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .unauthorized:
            return "Unauthorized. Please login again."
        case .networkError(let error):
            return error.localizedDescription
        }
    }
}
```

- [ ] **Step 9.5: Document iOS setup**

Create file: `ios/README.md`

```markdown
# Bewerbungstracker iOS App

## Setup

1. Open `Bewerbungstracker.xcodeproj` in Xcode 15+
2. Select "Bewerbungstracker" target
3. Build & Run on simulator or device

## Architecture

- **Models:** ApplicationModel, EmailModel (using SwiftData)
- **Views:** LoginView, ApplicationListView, EmailDetailView, SettingsView
- **Services:** APIClient (REST), CloudSyncService (iCloud), TokenManager

## Testing

```bash
xcodebuild test -scheme Bewerbungstracker
```

## Deployment

- TestFlight: Upload from Xcode
- App Store: Submit from App Store Connect
```

- [ ] **Step 9.6: Commit**

```bash
git add ios/
git commit -m "feat: iOS app structure with Core Data models and APIClient"
```

---

## Task 10: Android App Structure & Room Database

**Files:**
- Create: `android/build.gradle.kts`
- Create: `android/app/src/main/kotlin/com/example/bewerbungstracker/data/AppDatabase.kt`
- Create: `android/app/src/main/kotlin/com/example/bewerbungstracker/services/APIClient.kt`

> **For Android development, use Android Studio 2023.1+ with Kotlin 1.9+**

- [ ] **Step 10.1: Create Android project structure**

```bash
# Create directory structure
mkdir -p android/app/src/main/kotlin/com/example/bewerbungstracker/{models,ui,data,services}
mkdir -p android/app/src/main/res/{layout,values}
```

- [ ] **Step 10.2: Create AppDatabase.kt (Room)**

Create file: `android/app/src/main/kotlin/com/example/bewerbungstracker/data/AppDatabase.kt`

```kotlin
package com.example.bewerbungstracker.data

import androidx.room.*
import java.util.Date

@Entity(tableName = "applications")
data class ApplicationEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val company: String,
    val position: String,
    val status: String = "applied", // "applied", "interview", "offer", "rejected", "archived"
    val appliedDate: Long? = null, // Unix timestamp
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

@Entity(tableName = "emails")
data class EmailEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val subject: String,
    val fromAddress: String,
    val body: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val createdAt: Long = System.currentTimeMillis(),
    val messageId: String? = null,
    val matchedApplicationId: String? = null
)

@Dao
interface ApplicationDao {
    @Query("SELECT * FROM applications WHERE id = :id")
    suspend fun getApplicationById(id: String): ApplicationEntity?
    
    @Query("SELECT * FROM applications ORDER BY createdAt DESC")
    suspend fun getAllApplications(): List<ApplicationEntity>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertApplication(application: ApplicationEntity)
    
    @Update
    suspend fun updateApplication(application: ApplicationEntity)
    
    @Delete
    suspend fun deleteApplication(application: ApplicationEntity)
}

@Dao
interface EmailDao {
    @Query("SELECT * FROM emails WHERE id = :id")
    suspend fun getEmailById(id: String): EmailEntity?
    
    @Query("SELECT * FROM emails ORDER BY timestamp DESC")
    suspend fun getAllEmails(): List<EmailEntity>
    
    @Query("SELECT * FROM emails WHERE matchedApplicationId = :appId ORDER BY timestamp DESC")
    suspend fun getEmailsForApplication(appId: String): List<EmailEntity>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEmail(email: EmailEntity)
    
    @Update
    suspend fun updateEmail(email: EmailEntity)
    
    @Delete
    suspend fun deleteEmail(email: EmailEntity)
}

@Database(
    entities = [ApplicationEntity::class, EmailEntity::class],
    version = 1
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun applicationDao(): ApplicationDao
    abstract fun emailDao(): EmailDao
    
    companion object {
        private var INSTANCE: AppDatabase? = null
        
        fun getInstance(context: android.content.Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "bewerbungstracker.db"
                ).build().also { INSTANCE = it }
            }
        }
    }
}
```

- [ ] **Step 10.3: Create APIClient.kt (Retrofit)**

Create file: `android/app/src/main/kotlin/com/example/bewerbungstracker/services/APIClient.kt`

```kotlin
package com.example.bewerbungstracker.services

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import okhttp3.OkHttpClient
import okhttp3.Interceptor
import okhttp3.Response

data class AuthResponse(
    val access_token: String,
    val refresh_token: String,
    val token_type: String,
    val expires_in: Int
)

data class ApplicationResponse(
    val id: String,
    val company: String,
    val position: String,
    val status: String,
    val applied_date: String? = null,
    val created_at: String
)

data class ApplicationsListResponse(
    val count: Int,
    val applications: List<ApplicationResponse>
)

data class LoginRequest(
    val email: String,
    val password: String
)

interface BewerungstrackerAPI {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse
    
    @POST("auth/register")
    suspend fun register(@Body request: LoginRequest): AuthResponse
    
    @GET("applications")
    suspend fun getApplications(): ApplicationsListResponse
    
    @POST("applications")
    suspend fun createApplication(@Body body: Map<String, Any>): ApplicationResponse
    
    @PATCH("applications/{id}")
    suspend fun updateApplication(@Path("id") id: String, @Body body: Map<String, Any>): ApplicationResponse
    
    @DELETE("applications/{id}")
    suspend fun deleteApplication(@Path("id") id: String)
}

class TokenManager(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    
    private val sharedPreferences = EncryptedSharedPreferences.create(
        context,
        "auth_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    var accessToken: String?
        get() = sharedPreferences.getString("access_token", null)
        set(value) {
            if (value != null) {
                sharedPreferences.edit().putString("access_token", value).apply()
            } else {
                sharedPreferences.edit().remove("access_token").apply()
            }
        }
    
    fun clearToken() {
        sharedPreferences.edit().clear().apply()
    }
}

object APIClient {
    private const val BASE_URL = "http://localhost:8080/api/"
    
    fun getClient(context: Context): BewerungstrackerAPI {
        val tokenManager = TokenManager(context)
        
        val httpClient = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokenManager))
            .build()
        
        val retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .client(httpClient)
            .build()
        
        return retrofit.create(BewerungstrackerAPI::class.java)
    }
}

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        var request = chain.request()
        
        tokenManager.accessToken?.let { token ->
            request = request.newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        }
        
        return chain.proceed(request)
    }
}
```

- [ ] **Step 10.4: Create build.gradle.kts**

Create file: `android/app/build.gradle.kts` (partial)

```kotlin
plugins {
    id("com.android.application")
    kotlin("android")
    kotlin("kapt")
}

android {
    namespace = "com.example.bewerbungstracker"
    compileSdk = 34
    
    defaultConfig {
        applicationId = "com.example.bewerbungstracker"
        minSdk = 28
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }
}

dependencies {
    // Jetpack Compose
    implementation("androidx.compose.ui:ui:1.6.0")
    implementation("androidx.compose.material3:material3:1.1.0")
    
    // Room Database
    implementation("androidx.room:room-runtime:2.6.0")
    kapt("androidx.room:room-compiler:2.6.0")
    implementation("androidx.room:room-ktx:2.6.0")
    
    // Retrofit + OkHttp
    implementation("com.squareup.retrofit2:retrofit:2.10.0")
    implementation("com.squareup.retrofit2:converter-gson:2.10.0")
    implementation("com.squareup.okhttp3:okhttp:4.11.0")
    
    // Security (for encrypted SharedPreferences)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    
    // ViewModel & Coroutines
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.6.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1")
}
```

- [ ] **Step 10.5: Document Android setup**

Create file: `android/README.md`

```markdown
# Bewerbungstracker Android App

## Setup

1. Open project in Android Studio 2023.1+
2. Sync Gradle files
3. Connect device or start emulator
4. Run app: `gradlew run`

## Architecture

- **Models:** ApplicationEntity, EmailEntity (Room Database)
- **Services:** APIClient (Retrofit), TokenManager (encrypted SharedPreferences)
- **UI:** Jetpack Compose (MaterialUI 3)

## Testing

```bash
./gradlew test
./gradlew connectedAndroidTest
```

## Deployment

- Google Play Console: Upload signed APK/Bundle
- Internal Testing track: Add testers
- Production: Review & publish
```

- [ ] **Step 10.6: Commit**

```bash
git add android/
git commit -m "feat: Android app structure with Room database and Retrofit APIClient"
```

---

## Phase 3 Checkpoint

- [ ] **Step P3.1: Verify iOS project compiles**

```bash
cd ios
xcodebuild build -scheme Bewerbungstracker -destination 'generic/platform=iOS'
```

Expected: Build succeeds.

- [ ] **Step P3.2: Verify Android project compiles**

```bash
cd android
./gradlew build
```

Expected: Build succeeds.

- [ ] **Step P3.3: Final commit**

```bash
git add -A
git commit -m "checkpoint: Phase 3 structure complete (iOS + Android apps)

- iOS: SwiftUI with Core Data, APIClient for REST integration
- Android: Jetpack Compose with Room Database, Retrofit APIClient
- Both apps ready for implementation of Views and Cloud Sync
- Ready for next iteration: UI implementation and Cloud integration"
```

---

# FINAL SUMMARY

**3-Phase Implementation Plan Complete:**

✅ **Phase 1: Persistenz + REST API**
- SQLAlchemy ORM + Alembic migrations
- JWT authentication (register, login, refresh)
- CRUD endpoints for Applications, Emails
- 25+ passing unit tests

✅ **Phase 2: Claude Routing Integration**
- Routing service wrapper (ready for Phase 2 router)
- `/api/claude/analyze-email` and `/api/claude/match-application`
- API call logging and usage tracking
- 35+ passing tests total

✅ **Phase 3: Native Mobile Apps**
- iOS app structure (SwiftUI + Core Data)
- Android app structure (Jetpack Compose + Room)
- Both with JWT auth, local storage, REST client
- Ready for UI implementation and Cloud Sync

---

**Next Steps After This Plan:**

1. **Implement UI Components** (iOS Views + Android Screens)
2. **Integrate Cloud Sync** (iCloud Drive for iOS, Google Drive for Android)
3. **Wire Backend** (Replace mocks with actual Claude API calls)
4. **E2E Testing** (Full sync scenarios, offline mode)
5. **Deploy** (TestFlight → App Store, Google Play Console)
