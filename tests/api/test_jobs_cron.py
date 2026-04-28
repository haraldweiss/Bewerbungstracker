import os
import json
from pathlib import Path
import pytest
import responses
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

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


def test_prefilter_scores_pending_matches(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react", "typescript"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Senior React Developer", description="React, TypeScript, Berlin",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    r = client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["scored"] == 1

    m = JobMatch.query.first()
    assert m.prefilter_score is not None
    assert m.prefilter_score > 0


def test_prefilter_dismisses_low_scores(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["python"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Designer", description="Figma",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    m = JobMatch.query.first()
    assert m.status == 'dismissed'


@patch("api.jobs_cron._get_anthropic_client")
def test_claude_match_scores_top_n_per_user(mock_factory, app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react"], "summary": "React expert"}}),
        job_claude_budget_per_tick=2,
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    for i in range(5):
        raw = RawJob(source_id=src.id, external_id=f"id-{i}",
                     title=f"React Job {i}", description="React",
                     url=f"https://example.com/{i}", crawl_status='raw')
        db.session.add(raw); db.session.flush()
        db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                                prefilter_score=70 + i))
    db.session.commit()

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 88, "reasoning": "ok", "missing_skills": []}')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    )
    mock_factory.return_value = mock_client

    r = client.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})
    body = r.get_json()
    assert body["matched"] == 2
    matched = JobMatch.query.filter(JobMatch.match_score.isnot(None)).all()
    assert len(matched) == 2


@patch("services.job_matching.notifier._send_push")
def test_notify_sends_for_high_score_only(mock_push, app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, job_notification_threshold=80)
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                            prefilter_score=80, match_score=85))
    raw2 = RawJob(source_id=src.id, external_id="2", title="t", url="x", crawl_status='matched')
    db.session.add(raw2); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw2.id, user_id=user.id, status='new',
                            prefilter_score=70, match_score=70))
    db.session.commit()

    r = client.post("/api/jobs/notify", headers={"X-Cron-Token": "test-token"})
    assert r.get_json()["notified"] == 1
    assert mock_push.call_count == 1
