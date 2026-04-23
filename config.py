import os
from datetime import timedelta


class Config:
    """Base configuration"""
    # Database
    _database_url = os.getenv(
        'DATABASE_URL',
        'sqlite:///bewerbungstracker.db' if os.getenv('FLASK_ENV') != 'production' else None
    )

    if os.getenv('FLASK_ENV') == 'production' and not _database_url:
        raise ValueError('DATABASE_URL must be set in production')

    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT - VALIDATE IN PRODUCTION
    _jwt_secret = os.getenv('JWT_SECRET_KEY')
    if not _jwt_secret:
        if os.getenv('FLASK_ENV') == 'production':
            raise ValueError("JWT_SECRET_KEY environment variable MUST be set in production")
        _jwt_secret = 'dev-secret-key-change-in-prod'

    JWT_SECRET_KEY = _jwt_secret
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
    # Note: DATABASE_URL validation should happen at runtime, not at class definition time


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
