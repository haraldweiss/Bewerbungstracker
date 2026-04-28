import pytest
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from config import TestingConfig
from models import User


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


@pytest.fixture(autouse=True)
def mock_smtp(monkeypatch):
    """Stub alle SMTP-Sends in Tests.

    Ohne diesen Mock scheitert der /api/auth/register-Endpoint, weil er
    eine Confirmation-Mail verschickt. SMTP-Credentials sind in CI/Tests
    nicht konfiguriert, und echte Mails sind eh unerwünscht.

    autouse=True: jeder Test bekommt das Stub automatisch. Tests die
    explizit das Send-Verhalten prüfen wollen, können `mock_send_confirmation`
    fixture nutzen (gibt das MagicMock zurück).
    """
    from unittest.mock import MagicMock
    fake_send = MagicMock(return_value=True)
    monkeypatch.setattr("api.auth.send_confirmation_email", fake_send)
    monkeypatch.setattr("services.email_service._send_via_smtp", MagicMock(return_value=True))
    return fake_send


@pytest.fixture
def mock_send_confirmation(mock_smtp):
    """Returns the MagicMock for send_confirmation_email — falls Tests
    Aufrufe assertieren wollen."""
    return mock_smtp


@pytest.fixture
def user_factory(app):
    """Erstellt einen aktivierten User OHNE Envelope-Encryption.

    Reicht für Tests die nur Auth+CRUD prüfen ohne Backup/Encryption.
    Für Crypto-Tests: `user_factory_with_keys` nutzen.
    """
    def _create(email=None, **kwargs):
        u = User(
            id=str(uuid.uuid4()),
            email=email or f"user-{uuid.uuid4().hex[:8]}@test.de",
            password_hash="$2b$12$dummy",
            is_active=True,
            email_confirmed=True,
            **kwargs,
        )
        db.session.add(u)
        db.session.commit()
        return u
    return _create


@pytest.fixture
def user_factory_with_keys(app):
    """Erstellt einen aktivierten User MIT Envelope-Encryption-Keys.

    Generiert Salt + DEK, persistiert sie im User-Record und legt den DEK
    direkt in den KeyCache, sodass Backup-Operationen sofort funktionieren
    ohne expliziten Login.

    Returns:
        (user, password) — Password ist 'test_password_123' wenn nicht
        anders übergeben.
    """
    from auth_service import AuthService
    from services.encryption_service import EncryptionService
    from services.key_cache import get_key_cache

    def _create(email=None, password='test_password_123', **kwargs):
        salt, encrypted_dek, dek = EncryptionService.create_user_keys(password)
        u = User(
            id=str(uuid.uuid4()),
            email=email or f"user-{uuid.uuid4().hex[:8]}@test.de",
            password_hash=AuthService.hash_password(password),
            is_active=True,
            email_confirmed=True,
            encryption_salt=salt,
            encrypted_data_key=encrypted_dek,
            **kwargs,
        )
        db.session.add(u)
        db.session.commit()
        get_key_cache().put(u.id, dek)
        return u, password
    return _create


@pytest.fixture
def auth_headers(user_factory):
    """Auth-Header-Dict + User-Objekt.

    Returns: ({'Authorization': 'Bearer ...', 'Content-Type': 'application/json'}, user)

    Umgeht den register/login-Flow komplett — kein SMTP, kein Email-Confirm
    nötig. Reicht für Tests die nur Auth+CRUD prüfen.
    """
    from auth_service import AuthService
    user = user_factory()
    token = AuthService.create_access_token(user.id)
    return ({
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }, user)


@pytest.fixture
def auth_token(auth_headers):
    """JWT-Token-String für legacy Tests die nur den Token brauchen.

    Teilt sich denselben User mit `auth_headers` (pytest fixture-caching),
    sodass beide im gleichen Test konsistent sind.
    """
    headers, _ = auth_headers
    return headers['Authorization'].replace('Bearer ', '')


@pytest.fixture
def activate_user_after_register(app):
    """Helper für Tests die den ECHTEN /register → /login Flow durchlaufen.

    Nach `client.post('/api/auth/register', ...)` ist der User inaktiv
    (email_confirmed=False, is_active=False). Dieser Helper aktiviert ihn
    direkt in der DB, sodass der nachfolgende /login durchgeht.
    """
    def _activate(email: str):
        u = User.query.filter_by(email=email).first()
        assert u is not None, f"User {email} nicht gefunden — wurde register aufgerufen?"
        u.email_confirmed = True
        u.is_active = True
        db.session.commit()
        return u
    return _activate


@pytest.fixture
def auth_headers_with_keys(user_factory_with_keys):
    """Wie auth_headers, aber mit Envelope-Encryption-Keys + KeyCache.

    Für Tests die Backup/Crypto-Endpoints aufrufen.
    """
    from auth_service import AuthService
    user, password = user_factory_with_keys()
    token = AuthService.create_access_token(user.id)
    return ({
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }, user)
