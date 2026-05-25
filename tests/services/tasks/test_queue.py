# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für services.tasks.queue: enqueue_task helper."""
import json
import pytest
import uuid
import threading
from datetime import datetime

from database import db
from models import User, TaskQueue
from services.tasks.queue import enqueue_task, pick_next_task


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


def test_pick_next_task_marks_running(app, user):
    """pick_next_task sollte einen queued-Task auf running setzen und zurückgeben."""
    task_id = enqueue_task('test_noop', user.id, {})
    picked = pick_next_task(worker_id='w1')
    assert picked is not None
    assert picked.id == task_id
    assert picked.status == 'running'
    assert picked.worker_id == 'w1'
    assert picked.attempts == 1
    assert picked.started_at is not None
    assert picked.heartbeat_at is not None


def test_pick_next_task_returns_none_when_empty(app, user):
    """pick_next_task sollte None zurückgeben wenn keine queued-Tasks vorhanden sind."""
    assert pick_next_task(worker_id='w1') is None


def test_pick_next_task_skips_running(app, user):
    """pick_next_task sollte bereits running-Tasks ignorieren."""
    enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    assert pick_next_task(worker_id='w2') is None


def test_pick_next_task_is_atomic_under_concurrency(app, user):
    """2 Threads picken gleichzeitig — nur einer kriegt den Job."""
    enqueue_task('test_noop', user.id, {})
    results = []
    lock = threading.Lock()

    def worker(wid):
        with app.app_context():
            t = pick_next_task(worker_id=wid)
            with lock:
                results.append(t)

    threads = [threading.Thread(target=worker, args=(f'w{i}',)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [r for r in results if r is not None]
    assert len(successes) == 1, f"expected 1 pick, got {len(successes)}"
