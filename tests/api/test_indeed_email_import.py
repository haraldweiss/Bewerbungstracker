# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""API-Tests für Indeed-Email Import + Approval Flow."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from database import db
from models import Application, JobMatch, JobSource, RawJob
from services.job_sources.base import FetchedJob


# ── Fixtures ──────────────────────────────────────────────────────────────


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
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app, user_factory):
    from auth_service import AuthService
    user = user_factory()
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def indeed_source(auth_header):
    _, user = auth_header
    src = JobSource(
        user_id=user.id,
        name='Indeed',
        type='indeed_email',
        enabled=True,
    )
    src.config = {'folder': 'Indeed', 'lookback_days': 30}
    db.session.add(src)
    db.session.commit()
    return src


# ── Validation: Source-Type indeed_email ─────────────────────────────────


def test_create_indeed_email_source_with_valid_config(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Indeed Folder",
        "type": "indeed_email",
        "config": {"folder": "Indeed", "lookback_days": 30},
    }, headers=headers)
    assert r.status_code == 201
    assert r.get_json()["source"]["type"] == "indeed_email"


def test_create_indeed_email_source_rejects_bad_folder_name(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Bad",
        "type": "indeed_email",
        "config": {"folder": "bad\r\n; DROP TABLE"},
    }, headers=headers)
    assert r.status_code == 400


def test_create_indeed_email_source_rejects_invalid_lookback(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Bad",
        "type": "indeed_email",
        "config": {"folder": "Indeed", "lookback_days": 9999},
    }, headers=headers)
    assert r.status_code == 400


def test_create_indeed_email_source_defaults_folder(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Indeed",
        "type": "indeed_email",
        "config": {},  # Default folder applies
    }, headers=headers)
    assert r.status_code == 201


# ── Import-Endpoint: Happy Path ──────────────────────────────────────────


def _make_fetched(title, company, url, location='Berlin'):
    return FetchedJob(
        external_id=url,
        title=title,
        url=url,
        company=company,
        location=location,
        description='Job description here',
    )


def test_import_creates_raw_job_and_match_for_new_jobs(client, auth_header, indeed_source):
    headers, user = auth_header
    fetched = [
        _make_fetched("Senior Python Dev", "TechCorp", "https://de.indeed.com/viewjob?jk=a1"),
        _make_fetched("Data Engineer", "DataCo", "https://de.indeed.com/viewjob?jk=a2"),
    ]
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["imported"] == 2
    assert body["blocked"] == []
    assert body["duplicates"] == 0
    assert body["total_emails"] == 2

    # DB: 2 RawJobs + 2 JobMatches
    assert RawJob.query.count() == 2
    matches = JobMatch.query.filter_by(user_id=user.id).all()
    assert len(matches) == 2
    assert all(m.status == 'new' for m in matches)


def test_import_blocks_rejected_company(client, auth_header, indeed_source):
    headers, user = auth_header
    # Application mit Status 'absage' für KA Resources, 30 Tage alt
    app_rej = Application(
        user_id=user.id,
        company='KA Resources',
        position='IT Consultant',
        status='absage',
        applied_date=(datetime.utcnow() - timedelta(days=30)).date(),
    )
    db.session.add(app_rej)
    db.session.commit()

    fetched = [
        _make_fetched("IT Consultant", "KA Resources", "https://de.indeed.com/viewjob?jk=b1"),
        _make_fetched("Senior Dev", "GoodCo", "https://de.indeed.com/viewjob?jk=b2"),
    ]
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["imported"] == 1                # only GoodCo direct
    assert len(body["blocked"]) == 1            # KA Resources in dialog
    assert body["blocked"][0]["company"] == "KA Resources"

    # DB: nur 1 RawJob (für GoodCo) — blocked geht ins Dialog, kein DB-Eintrag
    assert RawJob.query.count() == 1


def test_import_respects_rejection_window_expiry(client, auth_header, indeed_source):
    """Absage älter als window_days → nicht mehr blocked."""
    headers, user = auth_header
    # User-default window_days ist 180. Application 200 Tage alt → ausgelaufen
    app_rej = Application(
        user_id=user.id,
        company='OldRejection Co',
        position='Dev',
        status='absage',
        applied_date=(datetime.utcnow() - timedelta(days=200)).date(),
    )
    db.session.add(app_rej)
    db.session.commit()

    fetched = [_make_fetched("Dev", "OldRejection Co", "https://de.indeed.com/viewjob?jk=c1")]
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    body = r.get_json()
    assert body["imported"] == 1
    assert body["blocked"] == []


def test_import_dedupes_existing_urls(client, auth_header, indeed_source):
    headers, user = auth_header
    # Existing RawJob mit gleicher URL
    existing = RawJob(
        source_id=indeed_source.id,
        external_id='https://de.indeed.com/viewjob?jk=dup',
        title='Existing',
        url='https://de.indeed.com/viewjob?jk=dup',
        crawl_status='raw',
    )
    db.session.add(existing)
    db.session.commit()

    fetched = [
        _make_fetched("New One", "NewCo", "https://de.indeed.com/viewjob?jk=fresh"),
        _make_fetched("Dup", "DupCo", "https://de.indeed.com/viewjob?jk=dup"),
    ]
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    body = r.get_json()
    assert body["imported"] == 1
    assert body["duplicates"] == 1


def test_import_forbidden_for_other_users_source(client, auth_header):
    headers, _ = auth_header
    other = JobSource(
        user_id='other-user-id', name='Other', type='indeed_email',
    )
    other.config = {'folder': 'Indeed'}
    db.session.add(other)
    db.session.commit()

    r = client.post(f"/api/jobs/sources/{other.id}/import-from-email", headers=headers)
    assert r.status_code == 403


def test_import_rejects_wrong_source_type(client, auth_header):
    headers, user = auth_header
    rss = JobSource(user_id=user.id, name='RSS', type='rss')
    rss.config = {'url': 'https://example.com/feed.xml'}
    db.session.add(rss)
    db.session.commit()

    r = client.post(f"/api/jobs/sources/{rss.id}/import-from-email", headers=headers)
    assert r.status_code == 400


def test_import_handles_fetch_error_and_increments_failures(client, auth_header, indeed_source):
    headers, _ = auth_header
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("IMAP unreachable")):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code in (502, 503)
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 1
    assert 'IMAP unreachable' in (indeed_source.last_error or '')


def test_import_auto_disables_after_5_failures(client, auth_header, indeed_source):
    headers, _ = auth_header
    indeed_source.consecutive_failures = 4
    db.session.commit()

    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("boom")):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code == 502
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 5
    assert indeed_source.enabled is False


def test_import_resets_failure_counter_on_success(client, auth_header, indeed_source):
    headers, _ = auth_header
    indeed_source.consecutive_failures = 3
    indeed_source.last_error = 'previous'
    db.session.commit()

    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=[]):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code == 200
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 0
    assert indeed_source.last_error is None


# ── Approve-Endpoint ──────────────────────────────────────────────────────


def test_approve_import_as_new_creates_new_match(client, auth_header, indeed_source):
    headers, user = auth_header
    payload = {
        "decisions": [
            {
                "action": "import_as_new",
                "job": {
                    "title": "IT Consultant", "company": "KA Resources",
                    "location": "Munich",
                    "url": "https://de.indeed.com/viewjob?jk=approve1",
                    "external_id": "https://de.indeed.com/viewjob?jk=approve1",
                    "description": "...",
                },
            }
        ]
    }
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email/approve",
        json=payload, headers=headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body == {"imported": 1, "skipped": 0, "ignored": 0}
    assert RawJob.query.count() == 1
    match = JobMatch.query.filter_by(user_id=user.id).one()
    assert match.status == 'new'


def test_approve_skip_creates_dismissed_match_with_feedback(client, auth_header, indeed_source):
    headers, user = auth_header
    payload = {
        "decisions": [
            {
                "action": "skip",
                "job": {
                    "title": "IT Consultant", "company": "KA Resources",
                    "url": "https://de.indeed.com/viewjob?jk=skipme",
                },
            }
        ]
    }
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email/approve",
        json=payload, headers=headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body == {"imported": 0, "skipped": 1, "ignored": 0}
    match = JobMatch.query.filter_by(user_id=user.id).one()
    assert match.status == 'dismissed'
    assert match.feedback_text == 'rejection_blocked_skip'


def test_approve_ignores_duplicate_urls(client, auth_header, indeed_source):
    headers, _ = auth_header
    db.session.add(RawJob(
        source_id=indeed_source.id, external_id='x', title='X',
        url='https://de.indeed.com/viewjob?jk=existing', crawl_status='raw',
    ))
    db.session.commit()

    payload = {
        "decisions": [{
            "action": "import_as_new",
            "job": {
                "title": "Dupe", "company": "X",
                "url": "https://de.indeed.com/viewjob?jk=existing",
            },
        }]
    }
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email/approve",
        json=payload, headers=headers,
    )
    body = r.get_json()
    assert body["imported"] == 0
    assert body["ignored"] == 1


# ── Apps-Script-Mode: Emails im Request-Body ─────────────────────────────


def test_import_apps_script_mode_parses_provided_emails(client, auth_header, indeed_source):
    """Wenn Frontend Emails als JSON-Body schickt, soll der Endpoint kein
    IMAP machen sondern direkt parsen + dedupen + rejection-checken."""
    headers, user = auth_header
    body = {
        "emails": [
            {
                "subject": "Neue Stelle: Senior Engineer bei GoodCo",
                "body": "Job-Link: https://de.indeed.com/viewjob?jk=apps_x1",
                "from": "noreply@indeed.com",
                "date": "2026-05-15T08:00:00Z",
            },
            {
                "subject": "Neue Stelle: Dev at OtherCo",
                "body": "https://de.indeed.com/viewjob?jk=apps_x2",
                "from": "jobs@indeed.com",
            },
        ]
    }
    # Patch ist absichtlich nicht da — wir wollen verifizieren dass kein
    # IMAP-fetch ausgelöst wird (sonst würde der Test scheitern weil keine
    # IMAP-Credentials gesetzt sind).
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email",
        json=body, headers=headers,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["imported"] == 2
    assert data["blocked"] == []
    assert data["fetch_mode"] == "apps_script"
    assert data["total_emails"] == 2


def test_import_apps_script_mode_applies_rejection_window(client, auth_header, indeed_source):
    headers, user = auth_header
    # Absage von ProblemCo, 30 Tage alt
    app_rej = Application(
        user_id=user.id, company='ProblemCo', position='Dev',
        status='absage',
        applied_date=(datetime.utcnow() - timedelta(days=30)).date(),
    )
    db.session.add(app_rej)
    db.session.commit()

    body = {
        "emails": [
            {"subject": "Neue Stelle: Dev bei ProblemCo",
             "body": "https://de.indeed.com/viewjob?jk=block_apps"},
            {"subject": "Neue Stelle: Dev bei FreshCo",
             "body": "https://de.indeed.com/viewjob?jk=new_apps"},
        ]
    }
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email",
        json=body, headers=headers,
    )
    data = r.get_json()
    assert data["imported"] == 1
    assert len(data["blocked"]) == 1
    assert data["blocked"][0]["company"] == "ProblemCo"
    assert data["fetch_mode"] == "apps_script"


def test_import_apps_script_proxy_mode_fetches_via_backend(client, auth_header, indeed_source):
    """Body {script_url:...} → Backend macht serverseitigen fetch (CORS-frei)."""
    headers, user = auth_header
    fake_response = {
        'status': 'ok',
        'count': 1,
        'emails': [{
            'subject': 'Neue Stelle: Backend Dev bei ProxyCo',
            'body': 'https://de.indeed.com/viewjob?jk=proxy_test',
            'from': 'jobs@indeed.com',
        }],
    }

    class FakeResp:
        status_code = 200
        headers = {'Content-Type': 'application/json'}
        text = '{"ok":1}'  # noqa
        def json(self):
            return fake_response

    # Cache zwischen Tests leeren — wir wollen einen frischen Fetch sehen.
    from api.jobs_user import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    with patch('requests.get', return_value=FakeResp()):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': 'https://script.google.com/macros/s/ABCdef123_-/exec'},
            headers=headers,
        )
    assert r.status_code == 200
    data = r.get_json()
    assert data['fetch_mode'] == 'apps_script_proxy'
    assert data['imported'] == 1
    assert data['total_emails'] == 1
    assert data['cache_hit'] is False


def test_apps_script_cache_skips_second_fetch(client, auth_header, indeed_source):
    """Zweiter Import mit gleicher URL innerhalb TTL → kein neuer HTTP-Call,
    cache_hit=True. Schützt Gmail-Quota."""
    headers, user = auth_header
    fake_response = {
        'status': 'ok', 'count': 1,
        'emails': [{
            'subject': 'Neue Stelle: Dev bei CacheCo',
            'body': 'https://de.indeed.com/viewjob?jk=cache_test',
            'from': 'jobs@indeed.com',
        }],
    }

    class FakeResp:
        status_code = 200
        headers = {'Content-Type': 'application/json'}
        text = '{"ok":1}'  # noqa
        def json(self): return fake_response

    from api.jobs_user import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    url = 'https://script.google.com/macros/s/CacheTest_-abc/exec'
    with patch('requests.get', return_value=FakeResp()) as mock_get:
        # 1. Call: Cache miss → fetcht
        r1 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        # 2. Call: Cache hit → kein fetch, aber 0 new (URL bereits in DB als RawJob)
        r2 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        assert mock_get.call_count == 1  # nur 1× ausgegangen!

    assert r1.get_json()['cache_hit'] is False
    assert r2.get_json()['cache_hit'] is True


def test_apps_script_force_refresh_bypasses_cache(client, auth_header, indeed_source):
    """force_refresh=true im Body → Cache wird ignoriert, fetcht nochmal."""
    headers, _ = auth_header
    fake_response = {'status': 'ok', 'count': 0, 'emails': []}

    class FakeResp:
        status_code = 200
        headers = {'Content-Type': 'application/json'}
        text = '{}'
        def json(self): return fake_response

    from api.jobs_user import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    url = 'https://script.google.com/macros/s/ForceTest_-xyz/exec'
    with patch('requests.get', return_value=FakeResp()) as mock_get:
        # 1. Call → cache miss
        client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        # 2. Call mit force_refresh → cache bypass, neuer fetch
        r2 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url, 'force_refresh': True}, headers=headers,
        )
        assert mock_get.call_count == 2

    assert r2.get_json()['cache_hit'] is False


def test_import_apps_script_proxy_rejects_bad_url(client, auth_header, indeed_source):
    """SSRF-Schutz: nur script.google.com URLs sind erlaubt."""
    headers, _ = auth_header
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email",
        json={'script_url': 'https://evil.example.com/steal'},
        headers=headers,
    )
    assert r.status_code in (502, 503)
    err = r.get_json().get('error', '')
    assert 'script.google.com' in err or 'ValueError' in err


def test_import_empty_body_uses_imap_mode(client, auth_header, indeed_source):
    """Leerer Body → IMAP-Mode (existing). Mocked weil keine echten Creds."""
    headers, _ = auth_header
    with patch('services.job_sources.indeed_email.IndeedEmailAdapter.fetch',
               return_value=[]):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
    assert r.status_code == 200
    assert r.get_json()["fetch_mode"] == "imap"


def test_approve_ignores_malformed_decisions(client, auth_header, indeed_source):
    headers, _ = auth_header
    payload = {
        "decisions": [
            {"action": "import_as_new", "job": {}},  # no url/title
            "not a dict",
            {"action": "weird_action", "job": {"url": "https://de.indeed.com/x", "title": "T"}},
        ]
    }
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email/approve",
        json=payload, headers=headers,
    )
    body = r.get_json()
    assert body["ignored"] == 3
    assert body["imported"] == 0
    assert body["skipped"] == 0
