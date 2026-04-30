import pytest
import json
from unittest.mock import patch, MagicMock
from app import create_app
from database import db
from models import JobSource, RawJob, JobMatch, Application, ApiCall
from services.job_sources.base import FetchedJob


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


# ---------------------------------------------------------------------------
# POST /api/jobs/sources – Validierungs-Pfade
# ---------------------------------------------------------------------------

def test_create_source_invalid_type(client, auth_header):
    """type muss aus _VALID_TYPES sein → 400."""
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Bad", "type": "unknown_type", "config": {},
    }, headers=headers)
    assert r.status_code == 400
    assert "type" in r.get_json()["error"]


def test_create_source_missing_name(client, auth_header):
    """name fehlt → 400."""
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "type": "rss", "config": {"url": "https://example.com/feed"},
    }, headers=headers)
    assert r.status_code == 400
    assert "name" in r.get_json()["error"]


def test_create_source_adzuna_missing_fields(client, auth_header):
    """Adzuna ohne app_id → 400."""
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Adzuna", "type": "adzuna",
        "config": {"country": "de"},  # app_id und app_key fehlen
    }, headers=headers)
    assert r.status_code == 400
    assert "Adzuna" in r.get_json()["error"]


def test_create_source_bundesagentur_missing_both(client, auth_header):
    """Bundesagentur ohne was und ohne wo → 400."""
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "BA", "type": "bundesagentur", "config": {},
    }, headers=headers)
    assert r.status_code == 400
    assert "Bundesagentur" in r.get_json()["error"]


# ---------------------------------------------------------------------------
# PATCH /api/jobs/sources/<id>
# ---------------------------------------------------------------------------

def test_update_source_fields(client, auth_header):
    """Eigene Quelle: name, enabled, crawl_interval_min, config updaten → 200."""
    headers, user = auth_header
    src = JobSource(user_id=user.id, name="Old", type="rss",
                    config={"url": "https://example.com/old"})
    db.session.add(src); db.session.commit()

    r = client.patch(f"/api/jobs/sources/{src.id}", json={
        "name": "New", "enabled": False,
        "crawl_interval_min": 120,
        "config": {"url": "https://example.com/new"},
    }, headers=headers)
    assert r.status_code == 200
    body = r.get_json()["source"]
    assert body["name"] == "New"
    assert body["enabled"] is False
    assert body["crawl_interval_min"] == 120


def test_update_source_not_found(client, auth_header):
    """Nicht-existente ID → 404."""
    headers, _ = auth_header
    r = client.patch("/api/jobs/sources/99999", json={"name": "X"}, headers=headers)
    assert r.status_code == 404


def test_update_source_invalid_config(client, auth_header):
    """Config-Update mit SSRF-URL → 400."""
    headers, user = auth_header
    src = JobSource(user_id=user.id, name="Mine", type="rss",
                    config={"url": "https://example.com/feed"})
    db.session.add(src); db.session.commit()

    r = client.patch(f"/api/jobs/sources/{src.id}", json={
        "config": {"url": "http://192.168.1.1/feed"},
    }, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/jobs/sources/<id>
# ---------------------------------------------------------------------------

def test_delete_own_source(client, auth_header):
    """Eigene Quelle löschen → 204."""
    headers, user = auth_header
    src = JobSource(user_id=user.id, name="Del", type="rss",
                    config={"url": "https://example.com/feed"})
    db.session.add(src); db.session.commit()
    src_id = src.id

    r = client.delete(f"/api/jobs/sources/{src_id}", headers=headers)
    assert r.status_code == 204
    assert JobSource.query.get(src_id) is None


def test_delete_global_source_forbidden(client, auth_header):
    """Globale Quelle (user_id=None) löschen → 403."""
    headers, _ = auth_header
    g = JobSource(name="Global", type="rss", config={"url": "x"})
    db.session.add(g); db.session.commit()

    r = client.delete(f"/api/jobs/sources/{g.id}", headers=headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/jobs/sources/<id>/test-crawl
# ---------------------------------------------------------------------------

def test_test_crawl_success(client, auth_header):
    """Test-Crawl mit gemocktem Adapter → 200, ok=True, found_jobs=2."""
    headers, user = auth_header
    src = JobSource(user_id=user.id, name="RSS", type="rss",
                    config={"url": "https://example.com/feed"})
    db.session.add(src); db.session.commit()

    with patch("services.job_sources.get_adapter") as mock_get_adapter:
        mock_adapter = MagicMock()
        mock_adapter.fetch.return_value = [
            FetchedJob(external_id="a", title="Job A", url="https://a.com"),
            FetchedJob(external_id="b", title="Job B", url="https://b.com"),
        ]
        mock_get_adapter.return_value = mock_adapter

        r = client.post(f"/api/jobs/sources/{src.id}/test-crawl", headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["found_jobs"] == 2
    assert body["sample_titles"] == ["Job A", "Job B"]


def test_test_crawl_adapter_exception(client, auth_header):
    """Test-Crawl mit fehlschlagendem Adapter → 200, ok=False."""
    headers, user = auth_header
    src = JobSource(user_id=user.id, name="RSS2", type="rss",
                    config={"url": "https://example.com/feed"})
    db.session.add(src); db.session.commit()

    with patch("services.job_sources.get_adapter") as mock_get_adapter:
        mock_get_adapter.side_effect = Exception("Verbindungsfehler")

        r = client.post(f"/api/jobs/sources/{src.id}/test-crawl", headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is False
    assert "Verbindungsfehler" in body["error"]


def test_test_crawl_other_user_source_forbidden(client, auth_header):
    """Quelle eines anderen Users → 403."""
    headers, _ = auth_header
    other_src = JobSource(user_id="other-user-uuid", name="Other", type="rss",
                          config={"url": "https://example.com/feed"})
    db.session.add(other_src); db.session.commit()

    r = client.post(f"/api/jobs/sources/{other_src.id}/test-crawl", headers=headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/jobs/matches – Filter
# ---------------------------------------------------------------------------

def test_list_matches_source_id_filter(client, auth_header):
    """source_id-Filter gibt nur Matches der betreffenden Quelle zurück."""
    headers, user = auth_header
    src1 = JobSource(name="S1", type="rss", config={"url": "x"})
    src2 = JobSource(name="S2", type="rss", config={"url": "y"})
    db.session.add_all([src1, src2]); db.session.flush()

    raw1 = RawJob(source_id=src1.id, external_id="r1", title="Job1", url="x", crawl_status='matched')
    raw2 = RawJob(source_id=src2.id, external_id="r2", title="Job2", url="y", crawl_status='matched')
    db.session.add_all([raw1, raw2]); db.session.flush()

    db.session.add(JobMatch(raw_job_id=raw1.id, user_id=user.id, status='new', match_score=80, prefilter_score=70))
    db.session.add(JobMatch(raw_job_id=raw2.id, user_id=user.id, status='new', match_score=75, prefilter_score=70))
    db.session.commit()

    r = client.get(f"/api/jobs/matches?source_id={src1.id}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["matches"]) == 1
    assert body["matches"][0]["raw_job"]["source_id"] == src1.id


def test_list_matches_text_search(client, auth_header):
    """q-Filter sucht nach Titel/Company."""
    headers, user = auth_header
    src = JobSource(name="S", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()

    raw1 = RawJob(source_id=src.id, external_id="q1", title="Python Developer",
                  company="TechCo", url="x", crawl_status='matched')
    raw2 = RawJob(source_id=src.id, external_id="q2", title="Java Engineer",
                  company="JavaCorp", url="y", crawl_status='matched')
    db.session.add_all([raw1, raw2]); db.session.flush()

    db.session.add(JobMatch(raw_job_id=raw1.id, user_id=user.id, status='new', prefilter_score=70))
    db.session.add(JobMatch(raw_job_id=raw2.id, user_id=user.id, status='new', prefilter_score=70))
    db.session.commit()

    r = client.get("/api/jobs/matches?q=python", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["matches"]) == 1
    assert "Python" in body["matches"][0]["raw_job"]["title"]


# ---------------------------------------------------------------------------
# PATCH /api/jobs/matches/<id>
# ---------------------------------------------------------------------------

def test_update_match_other_user_forbidden(client, auth_header, user_factory):
    """Match eines anderen Users patchen → 403."""
    headers, _ = auth_header
    other_user = user_factory()
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="z", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=other_user.id, status='new')
    db.session.add(m); db.session.commit()

    r = client.patch(f"/api/jobs/matches/{m.id}", json={"status": "seen"}, headers=headers)
    assert r.status_code == 403


def test_update_match_invalid_status(client, auth_header):
    """Ungültiger Status → 400."""
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="w", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
    db.session.add(m); db.session.commit()

    r = client.patch(f"/api/jobs/matches/{m.id}", json={"status": "invalid"}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/jobs/matches/<id>/import
# ---------------------------------------------------------------------------

def test_import_match_other_user_forbidden(client, auth_header, user_factory):
    """Match eines anderen Users importieren → 403."""
    headers, _ = auth_header
    other_user = user_factory()
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="imp1", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=other_user.id, status='new')
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)
    assert r.status_code == 403


def test_import_match_null_score(client, auth_header):
    """Match ohne match_score → trotzdem erfolgreich, '–' in Notiz."""
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="null-score", title="Null Score Job",
                 company="NullCo", url="https://example.com/job", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)
    assert r.status_code == 201
    app_id = r.get_json()["application_id"]
    app_obj = Application.query.get(app_id)
    assert "–" in app_obj.notes  # score_str bei None


def test_import_match_transfers_all_fields(client, auth_header):
    """Import überträgt alle Felder: location, source, applied_date."""
    from datetime import datetime
    headers, user = auth_header
    src = JobSource(name="TestSource", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    posted_date = datetime(2026, 4, 25, 10, 0, 0)
    raw = RawJob(
        source_id=src.id, external_id="full-fields",
        title="React Developer",
        company="TechCorp",
        location="Berlin, Germany",
        url="https://example.com/job/123",
        posted_at=posted_date,
        crawl_status='matched'
    )
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=85)
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/import", headers=headers)
    assert r.status_code == 201
    app_id = r.get_json()["application_id"]
    app_obj = Application.query.get(app_id)

    # Überprüfe, dass alle Felder übertragen wurden
    assert app_obj.company == "TechCorp"
    assert app_obj.position == "React Developer"
    assert app_obj.location == "Berlin, Germany"
    assert app_obj.applied_date == posted_date.date()
    assert app_obj.source == "TestSource"
    assert app_obj.link == "https://example.com/job/123"


# ---------------------------------------------------------------------------
# POST /api/jobs/matches/<id>/score (on-demand single Claude-Match)
# ---------------------------------------------------------------------------

def test_score_single_returns_match_data(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: ruft Claude, schreibt Score, returnt Daten."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Python Dev", "skills": ["python"]}}'
    user.job_daily_budget_cents = 1000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1",
                 description="Wir suchen Python")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 prefilter_score=42, match_score=None)
    db.session.add(m); db.session.commit()

    fake_result = MagicMock(score=80, reasoning="passt gut",
                            missing_skills=["docker"], tokens_in=20, tokens_out=20)
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body["match_score"] == 80
    assert body["match_reasoning"] == "passt gut"
    assert body["missing_skills"] == ["docker"]


def test_score_single_returns_402_when_budget_exhausted(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: Tagesbudget aufgebraucht → 402 Payment Required."""
    headers, user = auth_header
    user.cv_data_json = '{"cv": {"summary": "Dev"}}'
    user.job_daily_budget_cents = 50
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 prefilter_score=42, match_score=None)
    db.session.add(m)
    db.session.add(ApiCall(user_id=user.id, endpoint='/test', model='x',
                           tokens_in=0, tokens_out=0, cost=1.00, key_owner='server'))
    db.session.commit()

    from unittest.mock import patch, MagicMock
    with patch("api.jobs_user._get_anthropic_client", return_value=MagicMock()):
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)

    assert r.status_code == 402
    assert "budget" in r.get_json()["error"].lower()


def test_score_single_returns_403_when_not_owner(client, app, user_factory, auth_header):
    """POST /matches/<id>/score: anderer User → 403."""
    headers, user = auth_header
    other = user_factory(email="other@example.com")
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=other.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)
    assert r.status_code == 403


def test_score_single_returns_existing_score_when_already_matched(client, app, user_factory, auth_header):
    """Wenn match_score schon gesetzt: 200 mit Daten, kein Claude-Call."""
    from unittest.mock import patch, MagicMock
    headers, user = auth_header
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=88, match_reasoning="alt", missing_skills=[])
    db.session.add(m); db.session.commit()

    fake_client = MagicMock()
    with patch("api.jobs_user._get_anthropic_client", return_value=fake_client), \
         patch("api.jobs_cron.match_job_with_claude") as mock_claude:
        r = client.post(f"/api/jobs/matches/{m.id}/score", headers=headers)
        mock_claude.assert_not_called()

    assert r.status_code == 200
    assert r.get_json()["match_score"] == 88
