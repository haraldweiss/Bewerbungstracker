import pytest
import json
from app import create_app
from database import db
from models import JobSource, RawJob, JobMatch, Application


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
def auth_header(app, user_factory):
    """JWT-Header für authentifizierte Requests."""
    from auth_service import AuthService
    user = user_factory()
    # AuthService.create_access_token(user_id) erzeugt einen JWT-Access-Token
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_list_sources_returns_global_and_own(client, app, user_factory, auth_header):
    headers, user = auth_header
    db.session.add(JobSource(name="Global1", type="rss", config={"url": "x"}))
    db.session.add(JobSource(name="Mine", type="rss", config={"url": "y"}, user_id=user.id))
    db.session.add(JobSource(name="Other-User", type="rss", config={"url": "z"}, user_id="other-uuid"))
    db.session.commit()

    r = client.get("/api/jobs/sources", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    names = [s["name"] for s in body["sources"]]
    assert "Global1" in names
    assert "Mine" in names
    assert "Other-User" not in names


def test_create_own_source(client, auth_header):
    headers, user = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "My RSS", "type": "rss", "config": {"url": "https://example.com/feed.xml"},
        "crawl_interval_min": 30,
    }, headers=headers)
    assert r.status_code == 201
    src = JobSource.query.filter_by(user_id=user.id).first()
    assert src.name == "My RSS"


def test_create_source_validates_ssrf(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Hack", "type": "rss", "config": {"url": "http://localhost/feed"},
    }, headers=headers)
    assert r.status_code == 400


def test_user_cannot_modify_global_source(client, auth_header):
    headers, _ = auth_header
    g = JobSource(name="Global", type="rss", config={"url": "x"})
    db.session.add(g); db.session.commit()
    r = client.patch(f"/api/jobs/sources/{g.id}", json={"enabled": False}, headers=headers)
    assert r.status_code == 403


def test_list_matches_filters_by_score_and_status(client, app, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()

    for i, score in enumerate([90, 75, 50, 30]):
        raw = RawJob(source_id=src.id, external_id=f"id-{i}", title=f"Job {i}",
                     url="x", crawl_status='matched')
        db.session.add(raw); db.session.flush()
        db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id,
                                status='new', match_score=score, prefilter_score=80))
    db.session.commit()

    r = client.get("/api/jobs/matches?min_score=70&status=new", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["matches"]) == 2  # 90 und 75
    assert body["matches"][0]["match_score"] == 90  # sorted DESC


def test_patch_match_status(client, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    db.session.add(m); db.session.commit()

    r = client.patch(f"/api/jobs/matches/{m.id}", json={"status": "dismissed"}, headers=headers)
    assert r.status_code == 200
    db.session.refresh(m)
    assert m.status == "dismissed"


def test_import_match_creates_application(client, user_factory, auth_header):
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="React Dev", company="ACME",
                 location="Berlin", url="https://example.com/job", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=85, match_reasoning="Toller Match")
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    assert "application_id" in body
    db.session.refresh(m)
    assert m.status == "imported"
    assert m.imported_application_id == body["application_id"]
    app_obj = Application.query.get(body["application_id"])
    assert app_obj.user_id == user.id
    assert "ACME" in app_obj.company
