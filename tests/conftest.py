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


@pytest.fixture
def user_factory(app):
    def _create(email=None, **kwargs):
        u = User(
            id=str(uuid.uuid4()),
            email=email or f"user-{uuid.uuid4().hex[:8]}@test.de",
            password_hash="$2b$12$dummy",
            is_active=True,
            **kwargs,
        )
        db.session.add(u)
        db.session.commit()
        return u
    return _create
