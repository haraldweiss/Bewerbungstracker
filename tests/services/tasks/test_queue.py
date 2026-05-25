# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für services.tasks.queue: enqueue_task helper."""
import json
import pytest
import uuid
from datetime import datetime

from database import db
from models import User, TaskQueue
from services.tasks.queue import enqueue_task


@pytest.fixture
def app(monkeypatch):
    """Test-App mit in-memory SQLite."""
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def user(app):
    """Erstellt einen Test-User."""
    u = User(
        id=str(uuid.uuid4()),
        email='test@example.com',
        password_hash='$2b$12$dummy',
        is_active=True,
        email_confirmed=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def test_enqueue_creates_queued_row(app, user):
    """enqueue_task sollte eine neue TaskQueue-Row mit status='queued' erstellen."""
    task_id = enqueue_task('test_noop', user.id, {'foo': 'bar'})

    row = db.session.get(TaskQueue, task_id)
    assert row is not None
    assert row.status == 'queued'
    assert row.type == 'test_noop'
    assert row.user_id == user.id
    assert json.loads(row.payload) == {'foo': 'bar'}
    assert row.attempts == 0
    assert isinstance(row.created_at, datetime)
