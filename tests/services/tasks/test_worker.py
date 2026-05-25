import json
import pytest
import uuid
from app import create_app
from database import db
from models import User, TaskQueue
from services.tasks.queue import enqueue_task
from services.tasks.worker import run_one_iteration
import services.tasks.handlers  # noqa: F401 — registers handlers


@pytest.fixture
def app(monkeypatch):
    """Test-App mit in-memory SQLite."""
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
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


def test_run_one_iteration_completes_task(app, user):
    task_id = enqueue_task('test_noop', user.id, {'sleep_seconds': 0.01})
    picked = run_one_iteration(app, worker_id='w-test')
    assert picked is True
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'done'
    assert json.loads(row.result) == {'ok': True, 'slept': 0.01}


def test_run_one_iteration_marks_failed_on_unknown_type(app, user):
    task_id = enqueue_task('does_not_exist', user.id, {})
    picked = run_one_iteration(app, worker_id='w-test')
    assert picked is True
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'failed'
    assert 'does_not_exist' in row.error


def test_run_one_iteration_returns_false_when_idle(app, user):
    assert run_one_iteration(app, worker_id='w-test') is False


def test_run_one_iteration_retries_on_exception(app, user):
    from services.tasks.registry import register
    from datetime import datetime

    @register('always_fails')
    def _h(payload, *, progress_cb=None):
        raise RuntimeError("nope")

    task_id = enqueue_task('always_fails', user.id, {}, max_attempts=2)
    run_one_iteration(app, worker_id='w-test')
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'queued'
    assert row.attempts == 1
    row.created_at = datetime.utcnow()
    db.session.commit()
    run_one_iteration(app, worker_id='w-test')
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'failed'
    assert row.attempts == 2
