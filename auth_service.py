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
