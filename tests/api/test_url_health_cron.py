# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""Integration-Test fuer /api/jobs/url-health-check Cron-Endpoint."""
import pytest
from unittest.mock import patch

from app import create_app
from database import db
from models import JobSource, RawJob


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


def test_url_health_check_marks_404_immediately(client, app, source):
    """RawJob mit 404-URL bekommt sofort crawl_status='marked_for_deletion'."""
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

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['marked'] == 1
    assert data['checked'] == 1

    rj_after = db.session.get(RawJob, rj_id)
    assert rj_after.crawl_status == 'marked_for_deletion'
    assert rj_after.url_check_status == '404'


def test_url_health_check_ok_keeps_active(client, app, source):
    """OK-Response setzt url_check_failures zurueck und laesst Status."""
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

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] == 1
    assert data['marked'] == 0

    rj_after = db.session.get(RawJob, rj_id)
    assert rj_after.crawl_status == 'raw'
    assert rj_after.url_check_failures == 0  # reset


def test_url_health_check_skips_archived(client, app, source):
    """Archived/marked_for_deletion RawJobs werden nicht mehr geprueft."""
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

    assert resp.status_code == 200
    assert resp.get_json()['checked'] == 0
    assert m.call_count == 0


def test_url_health_check_rejects_without_token(client):
    resp = client.post('/api/jobs/url-health-check')
    assert resp.status_code == 403
