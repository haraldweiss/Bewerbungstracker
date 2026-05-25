# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für services.tasks.handlers.email_import."""
import uuid
import pytest
from unittest.mock import patch

from database import db
from models import User, JobSource
from services.tasks.handlers.email_import import handle_email_import


@pytest.fixture
def app(monkeypatch):
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
    """Erstellt einen Test-User (Muster aus test_queue.py)."""
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


@pytest.fixture
def indeed_source(app, user):
    src = JobSource(
        user_id=user.id,
        name='Indeed',
        type='indeed_email',
        enabled=True,
    )
    src.config = {'folder': 'INBOX'}
    db.session.add(src)
    db.session.commit()
    return src


def test_handle_email_import_apps_script_mode(app, user, indeed_source):
    """Apps-Script-Mode: keine IMAP-Connection nötig."""
    payload = {
        'user_id': user.id,
        'source_id': indeed_source.id,
        'emails': [{
            'message_id': 'm1',
            'subject': 'New Indeed Job: Python Dev at Acme',
            'from': 'jobs@indeed.com',
            'body': '<a href="https://indeed.com/jobs/123">Python Dev at Acme - Berlin</a>',
        }],
    }
    with app.app_context():
        result = handle_email_import(payload, progress_cb=None)
    assert 'imported' in result
    assert 'total_emails' in result
    assert result['fetch_mode'] == 'apps_script'


def test_handle_email_import_invalid_user(app, indeed_source):
    """Unbekannte user_id wirft ValueError."""
    payload = {
        'user_id': str(uuid.uuid4()),
        'source_id': indeed_source.id,
        'emails': [],
    }
    with app.app_context():
        with pytest.raises(ValueError, match='user_id'):
            handle_email_import(payload, progress_cb=None)


def test_handle_email_import_wrong_source(app, user, indeed_source):
    """source_id, die nicht dem User gehört, wirft ValueError."""
    # Zweiten User + Source anlegen
    other_user = User(
        id=str(uuid.uuid4()),
        email='other@example.com',
        password_hash='$2b$12$dummy',
        is_active=True,
        email_confirmed=True,
    )
    db.session.add(other_user)
    db.session.commit()
    other_src = JobSource(
        user_id=other_user.id,
        name='OtherIndeed',
        type='indeed_email',
        enabled=True,
    )
    other_src.config = {}
    db.session.add(other_src)
    db.session.commit()

    payload = {
        'user_id': user.id,
        'source_id': other_src.id,
        'emails': [],
    }
    with app.app_context():
        with pytest.raises(ValueError, match='source_id'):
            handle_email_import(payload, progress_cb=None)


def test_handle_email_import_empty_emails(app, user, indeed_source):
    """Leere Email-Liste: 0 imports, 0 duplicates, fetch_mode apps_script."""
    payload = {
        'user_id': user.id,
        'source_id': indeed_source.id,
        'emails': [],
    }
    with app.app_context():
        result = handle_email_import(payload, progress_cb=None)
    assert result['imported'] == 0
    assert result['duplicates'] == 0
    assert result['total_emails'] == 0
    assert result['fetch_mode'] == 'apps_script'


def test_handle_email_import_progress_cb(app, user, indeed_source):
    """progress_cb wird aufgerufen."""
    calls = []

    def cb(pct, msg):
        calls.append((pct, msg))

    payload = {
        'user_id': user.id,
        'source_id': indeed_source.id,
        'emails': [],
    }
    with app.app_context():
        handle_email_import(payload, progress_cb=cb)
    assert len(calls) >= 2
    assert calls[0][0] == 5
    assert calls[-1][0] == 100
