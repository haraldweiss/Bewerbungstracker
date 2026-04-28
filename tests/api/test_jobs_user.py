import pytest
import json
from app import create_app
from database import db
from models import JobSource


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
