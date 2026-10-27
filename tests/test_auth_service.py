# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import bcrypt
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


# --- SHA-256 pre-hash migration (bcrypt 5) -------------------------------
# bcrypt 5 raises ValueError above 72 UTF-8 bytes, bcrypt 4 silently
# truncated. Passwords are pre-hashed now; legacy hashes keep working and are
# upgraded on the next successful login.

LONG_PASSWORD = 'Korrekt-Pferd-Batterie-Klausur-' * 8 + 'äöüß-€'


def test_hash_uses_prehash_scheme():
    hashed = AuthService.hash_password('short-password')

    assert hashed.startswith(AuthService.PASSWORD_HASH_PREFIX)
    assert not AuthService.is_legacy_hash(hashed)
    assert AuthService.hash_password('short-password') != hashed  # salted


def test_long_password_roundtrip():
    """More than 72 UTF-8 bytes must hash and verify (bcrypt 4 truncated)."""
    assert len(LONG_PASSWORD.encode('utf-8')) > 72

    hashed = AuthService.hash_password(LONG_PASSWORD)

    assert AuthService.verify_password(LONG_PASSWORD, hashed)
    # bcrypt 4 would have accepted this truncated variant; the pre-hash must not.
    assert not AuthService.verify_password(LONG_PASSWORD[:72], hashed)
    assert not AuthService.verify_password(LONG_PASSWORD + 'x', hashed)


def test_legacy_short_password_still_verifies():
    legacy = bcrypt.hashpw(b'legacy-password', bcrypt.gensalt()).decode('utf-8')

    assert AuthService.is_legacy_hash(legacy)
    assert AuthService.verify_password('legacy-password', legacy)
    assert not AuthService.verify_password('wrong-password', legacy)


def test_legacy_long_password_verifies_against_truncated_bytes():
    """bcrypt 4 hashed only the first 72 bytes; those users must still log in."""
    legacy = bcrypt.hashpw(LONG_PASSWORD.encode('utf-8')[:72], bcrypt.gensalt()).decode('utf-8')

    assert AuthService.verify_password(LONG_PASSWORD, legacy)
    assert not AuthService.verify_password('completely-different', legacy)


def test_malformed_hash_never_raises():
    assert AuthService.verify_password('password', 'not-a-bcrypt-hash') is False


def test_login_upgrades_legacy_hash(app):
    from models import User
    from database import db

    legacy = bcrypt.hashpw(b'legacy-password', bcrypt.gensalt()).decode('utf-8')

    with app.app_context():
        user = User(email='legacy@example.com', password_hash=legacy,
                    is_active=True, email_confirmed=True)
        db.session.add(user)
        db.session.commit()

        success, logged_in, msg = AuthService.login_user('legacy@example.com', 'legacy-password')
        assert success, msg

        migrated = User.query.filter_by(email='legacy@example.com').first().password_hash
        assert not AuthService.is_legacy_hash(migrated)
        assert AuthService.verify_password('legacy-password', migrated)


def test_login_upgrades_only_once(app):
    from models import User

    with app.app_context():
        AuthService.register_user('fresh@example.com', 'password123')
        first = User.query.filter_by(email='fresh@example.com').first().password_hash

        AuthService.login_user('fresh@example.com', 'password123')
        second = User.query.filter_by(email='fresh@example.com').first().password_hash

        # Already-migrated hashes are not re-hashed on every login.
        assert first == second
