import os
import json
from pathlib import Path
import pytest
import responses
from datetime import datetime, timedelta

from app import create_app
from database import db
from models import User, JobSource, RawJob, JobMatch


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


@responses.activate
def test_crawl_source_picks_due_source_creates_raw_jobs_and_matches(app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, cv_data_json='{"cv":{"skills":["react"]}}')

    rss_xml = (Path(__file__).parent.parent / "fixtures" / "rss_stepstone_sample.xml").read_text()
    responses.add(responses.GET, "https://example.com/feed.xml",
                  body=rss_xml, content_type="application/rss+xml", status=200)

    src = JobSource(name="Test", type="rss", config={"url": "https://example.com/feed.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src)
    db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["source_id"] == src.id
    assert body["new_jobs"] == 2
    assert body["matches_created"] == 2  # 2 jobs × 1 user

    raw_jobs = RawJob.query.all()
    assert len(raw_jobs) == 2
    matches = JobMatch.query.all()
    assert len(matches) == 2
    assert all(m.user_id == user.id for m in matches)
    assert all(m.status == "new" for m in matches)


def test_crawl_source_skips_sources_not_due(app, client):
    src = JobSource(name="Recent", type="rss", config={"url": "x"},
                    enabled=True, crawl_interval_min=60,
                    last_crawled_at=datetime.utcnow() - timedelta(minutes=5))
    db.session.add(src); db.session.commit()
    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    assert r.get_json()["source_id"] is None
    assert r.get_json()["reason"] == "no_source_due"


@responses.activate
def test_crawl_source_records_error_and_increments_failures(app, client):
    responses.add(responses.GET, "https://example.com/broken.xml", status=500)
    src = JobSource(name="Broken", type="rss", config={"url": "https://example.com/broken.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src); db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    db.session.refresh(src)
    assert src.consecutive_failures == 1
    assert src.last_error is not None
