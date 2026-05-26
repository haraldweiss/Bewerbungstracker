# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""Integration-Test fuer /api/jobs/url-health-check Cron-Endpoint."""
import json
import uuid
import pytest
from unittest.mock import patch

from app import create_app
from database import db
from models import JobSource, RawJob, User


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def source(app):
    """RawJob.source_id ist NOT NULL — Tests brauchen eine JobSource."""
    src = JobSource(name="UrlHealthTest", type="rss",
                    config={"url": "https://example.com/feed.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src)
    db.session.commit()
    return src


def _make_admin():
    """Erstellt einen Admin-User (Pflicht für _system_user_id in cron-Endpoints)."""
    admin = User(
        id=str(uuid.uuid4()),
        email=f"admin-{uuid.uuid4().hex[:8]}@test.de",
        password_hash="$2b$12$dummy",
        is_active=True,
        email_confirmed=True,
        is_admin=True,
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def _run_cron_handler_sync(app, response, handler_fn):
    """Führt den gerade enqueueten cron-Handler synchron aus für Tests."""
    from models import TaskQueue
    task_id = response.get_json()['task_id']
    row = db.session.get(TaskQueue, task_id)
    return handler_fn(json.loads(row.payload), progress_cb=None)


def test_url_health_check_marks_404_immediately(client, app, source):
    """RawJob mit 404-URL bekommt sofort crawl_status='marked_for_deletion'."""
    from services.tasks.handlers.cron_url_health_check import handle_cron_url_health_check
    _make_admin()
    rj = RawJob(
        source_id=source.id, external_id='abc',
        title='Test Job', url='https://example.com/dead-job',
        crawl_status='raw',
    )
    db.session.add(rj)
    db.session.commit()
    rj_id = rj.id

    with patch('services.url_health_check.check_url', return_value=('404', 404)):
        resp = client.post(
            '/api/jobs/url-health-check',
            headers={'X-Cron-Token': 'test-token'},
        )
        assert resp.status_code == 202
        data = _run_cron_handler_sync(app, resp, handle_cron_url_health_check)

    assert data['marked'] == 1
    assert data['checked'] == 1

    rj_after = db.session.get(RawJob, rj_id)
    assert rj_after.crawl_status == 'marked_for_deletion'
    assert rj_after.url_check_status == '404'


def test_url_health_check_ok_keeps_active(client, app, source):
    """OK-Response setzt url_check_failures zurueck und laesst Status."""
    from services.tasks.handlers.cron_url_health_check import handle_cron_url_health_check
    _make_admin()
    rj = RawJob(
        source_id=source.id, external_id='abc2',
        title='Live Job', url='https://example.com/live',
        crawl_status='raw', url_check_failures=2,  # prior failures
    )
    db.session.add(rj)
    db.session.commit()
    rj_id = rj.id

    with patch('services.url_health_check.check_url', return_value=('ok', 200)):
        resp = client.post(
            '/api/jobs/url-health-check',
            headers={'X-Cron-Token': 'test-token'},
        )
        assert resp.status_code == 202
        data = _run_cron_handler_sync(app, resp, handle_cron_url_health_check)

    assert data['ok'] == 1
    assert data['marked'] == 0

    rj_after = db.session.get(RawJob, rj_id)
    assert rj_after.crawl_status == 'raw'
    assert rj_after.url_check_failures == 0  # reset


def test_url_health_check_skips_archived(client, app, source):
    """Archived/marked_for_deletion RawJobs werden nicht mehr geprueft."""
    from services.tasks.handlers.cron_url_health_check import handle_cron_url_health_check
    _make_admin()
    rj_archived = RawJob(
        source_id=source.id, external_id='abc3',
        title='Old Archived', url='https://example.com/archived',
        crawl_status='archived',
    )
    rj_marked = RawJob(
        source_id=source.id, external_id='abc4',
        title='Already marked', url='https://example.com/marked',
        crawl_status='marked_for_deletion',
    )
    db.session.add_all([rj_archived, rj_marked])
    db.session.commit()

    with patch('services.url_health_check.check_url',
               return_value=('404', 404)) as m:
        resp = client.post(
            '/api/jobs/url-health-check',
            headers={'X-Cron-Token': 'test-token'},
        )
        assert resp.status_code == 202
        data = _run_cron_handler_sync(app, resp, handle_cron_url_health_check)

    assert data['checked'] == 0
    assert m.call_count == 0


def test_url_health_check_rejects_without_token(client):
    resp = client.post('/api/jobs/url-health-check')
    assert resp.status_code == 403
