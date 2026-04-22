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
