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
