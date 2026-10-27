# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import base64
import hashlib

import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple
from config import Config
from models import User, SessionToken
from database import db
from imap_service import IMAPCredentialManager


class AuthService:
    """Service for authentication and token management"""

    # bcrypt 5 rejects inputs longer than 72 bytes with ValueError (bcrypt 4
    # truncated silently). Passwords are therefore SHA-256 pre-hashed and
    # base64-encoded before bcrypt, so the length is fixed at 44 ASCII bytes:
    # full length is used, and no NUL byte truncates the digest.
    PASSWORD_HASH_PREFIX = '$bcrypt-sha256$'
    _BCRYPT_ROUNDS = 12

    @staticmethod
    def _prehash(password: str) -> bytes:
        """Return the bcrypt-safe digest of a password.

        base64 keeps the digest printable and NUL-free — bcrypt stops at the
        first NUL byte, which would silently weaken a raw 32-byte digest.
        """
        return base64.b64encode(hashlib.sha256(password.encode('utf-8')).digest())

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with SHA-256 pre-hashing + bcrypt."""
        salt = bcrypt.gensalt(rounds=AuthService._BCRYPT_ROUNDS)
        digest = bcrypt.hashpw(AuthService._prehash(password), salt).decode('utf-8')
        return f'{AuthService.PASSWORD_HASH_PREFIX}{digest}'

    @staticmethod
    def is_legacy_hash(password_hash: str) -> bool:
        """True for hashes created before the SHA-256 pre-hash change."""
        return not password_hash.startswith(AuthService.PASSWORD_HASH_PREFIX)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against either the new or a legacy hash.

        Legacy (bcrypt 4) hashes were computed over the raw password and were
        truncated at 72 bytes, so verification truncates as well instead of
        letting bcrypt 5 raise ValueError for long passwords.
        """
        try:
            if AuthService.is_legacy_hash(password_hash):
                candidate = password.encode('utf-8')[:72]
            else:
                candidate = AuthService._prehash(password)
                password_hash = password_hash[len(AuthService.PASSWORD_HASH_PREFIX):]
            return bcrypt.checkpw(candidate, password_hash.encode('utf-8'))
        except ValueError:
            # Malformed hash or unexpectedly long input: never 500 a login.
            return False

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

        # Transparent upgrade: legacy bcrypt-4 hashes are re-hashed with the
        # SHA-256 pre-hash scheme on the first successful login. A failure here
        # must never block an otherwise valid login.
        if AuthService.is_legacy_hash(user.password_hash):
            try:
                user.password_hash = AuthService.hash_password(password)
                db.session.commit()
            except Exception:
                db.session.rollback()

        return True, user, "Login successful"

    @staticmethod
    def register_imap_credentials(user_id: str, imap_host: str, imap_user: str, imap_password: str) -> Tuple[bool, str]:
        """Register IMAP credentials for user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            user.imap_host = imap_host
            user.imap_user = imap_user
            user.imap_password_encrypted = IMAPCredentialManager.encrypt_password(imap_password)
            db.session.commit()
            return True, "IMAP credentials registered successfully"
        except Exception as e:
            db.session.rollback()
            return False, str(e)
