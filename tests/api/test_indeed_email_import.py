# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""API-Tests für Indeed-Email Import + Approval Flow."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from database import db
from models import Application, JobMatch, JobSource, RawJob, User
from services.job_sources.base import FetchedJob


def _run_enqueued_handler_sync(client_response):
    """Führt den gerade enqueueten Handler synchron aus, returnt result-dict.

    Genutzt nach POST /import-from-email (returnt 202): liest die Job-Row,
    ruft den Handler direkt auf, returnt das gleiche result-dict das früher
    direkt in der HTTP-Response stand.
    """
    import json
    from models import TaskQueue
    from services.tasks.handlers.email_import import handle_email_import
    task_id = client_response.get_json()['task_id']
    row = db.session.get(TaskQueue, task_id)
    return handle_email_import(json.loads(row.payload), progress_cb=None)


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
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        body = _run_enqueued_handler_sync(r)
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
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        body = _run_enqueued_handler_sync(r)
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
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        body = _run_enqueued_handler_sync(r)
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
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        body = _run_enqueued_handler_sync(r)
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
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("IMAP unreachable")):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="IMAP unreachable"):
            _run_enqueued_handler_sync(r)
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 1
    assert 'IMAP unreachable' in (indeed_source.last_error or '')


def test_import_auto_disables_after_5_failures(client, auth_header, indeed_source):
    headers, _ = auth_header
    indeed_source.consecutive_failures = 4
    db.session.commit()

    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("boom")):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="boom"):
            _run_enqueued_handler_sync(r)
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 5
    assert indeed_source.enabled is False


def test_import_resets_failure_counter_on_success(client, auth_header, indeed_source):
    headers, _ = auth_header
    indeed_source.consecutive_failures = 3
    indeed_source.last_error = 'previous'
    db.session.commit()

    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=[]):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        _run_enqueued_handler_sync(r)
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
    assert r.status_code == 202
    data = _run_enqueued_handler_sync(r)
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
    assert r.status_code == 202
    data = _run_enqueued_handler_sync(r)
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
    from services.email_import_utils import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    with patch('requests.get', return_value=FakeResp()):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': 'https://script.google.com/macros/s/ABCdef123_-/exec'},
            headers=headers,
        )
        assert r.status_code == 202
        data = _run_enqueued_handler_sync(r)
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

    from services.email_import_utils import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    url = 'https://script.google.com/macros/s/CacheTest_-abc/exec'
    with patch('requests.get', return_value=FakeResp()) as mock_get:
        # 1. Call: Cache miss → fetcht
        r1 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        assert r1.status_code == 202
        data1 = _run_enqueued_handler_sync(r1)
        # 2. Call: Cache hit → kein fetch, aber 0 new (URL bereits in DB als RawJob)
        r2 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        assert r2.status_code == 202
        data2 = _run_enqueued_handler_sync(r2)
        assert mock_get.call_count == 1  # nur 1× ausgegangen!

    assert data1['cache_hit'] is False
    assert data2['cache_hit'] is True


def test_apps_script_force_refresh_bypasses_cache(client, auth_header, indeed_source):
    """force_refresh=true im Body → Cache wird ignoriert, fetcht nochmal."""
    headers, _ = auth_header
    fake_response = {'status': 'ok', 'count': 0, 'emails': []}

    class FakeResp:
        status_code = 200
        headers = {'Content-Type': 'application/json'}
        text = '{}'
        def json(self): return fake_response

    from services.email_import_utils import _APPS_SCRIPT_CACHE
    _APPS_SCRIPT_CACHE.clear()

    url = 'https://script.google.com/macros/s/ForceTest_-xyz/exec'
    with patch('requests.get', return_value=FakeResp()) as mock_get:
        # 1. Call → cache miss
        r1 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url}, headers=headers,
        )
        assert r1.status_code == 202
        _run_enqueued_handler_sync(r1)
        # 2. Call mit force_refresh → cache bypass, neuer fetch
        r2 = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            json={'script_url': url, 'force_refresh': True}, headers=headers,
        )
        assert r2.status_code == 202
        data2 = _run_enqueued_handler_sync(r2)
        assert mock_get.call_count == 2

    assert data2['cache_hit'] is False


def test_import_apps_script_proxy_rejects_bad_url(client, auth_header, indeed_source):
    """SSRF-Schutz: nur script.google.com URLs sind erlaubt."""
    headers, _ = auth_header
    r = client.post(
        f"/api/jobs/sources/{indeed_source.id}/import-from-email",
        json={'script_url': 'https://evil.example.com/steal'},
        headers=headers,
    )
    assert r.status_code == 202
    import pytest as _pytest
    with _pytest.raises(Exception) as exc_info:
        _run_enqueued_handler_sync(r)
    err = str(exc_info.value)
    assert 'script.google.com' in err or 'ValueError' in err or 'evil' in err


def test_import_empty_body_uses_imap_mode(client, auth_header, indeed_source):
    """Leerer Body → IMAP-Mode (existing). Mocked weil keine echten Creds."""
    headers, _ = auth_header
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=[]):
        r = client.post(
            f"/api/jobs/sources/{indeed_source.id}/import-from-email",
            headers=headers,
        )
        assert r.status_code == 202
        data = _run_enqueued_handler_sync(r)
    assert data["fetch_mode"] == "imap"


# ── Cron-Endpoint: Auto-Import alle eligible Sources ─────────────────────


def test_cron_indeed_email_import_skips_source_without_credentials(client, auth_header, indeed_source, monkeypatch):
    """Source ohne IMAP-Creds und ohne indeedScriptUrl → skipped_no_credentials."""
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    r = client.post(
        "/api/jobs/indeed-email-import-all",
        headers={"X-Cron-Token": "test-token"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_sources"] == 1
    assert any(run["status"] == "skipped_no_credentials" for run in data["runs"])


def test_cron_indeed_email_import_runs_via_imap_when_credentials_present(
    client, auth_header, indeed_source, monkeypatch
):
    headers, user = auth_header
    # User mit IMAP-Creds versehen (Test-Modus: encryption_key gesetzt)
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from imap_service import IMAPCredentialManager
    user.imap_host = "imap.example.com"
    user.imap_user = "u@example.com"
    user.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.commit()

    fetched = [
        FetchedJob(external_id="https://de.indeed.com/viewjob?jk=cron1",
                   title="Cron Dev", url="https://de.indeed.com/viewjob?jk=cron1",
                   company="CronCo", location="Berlin", description="..."),
    ]
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        r = client.post(
            "/api/jobs/indeed-email-import-all",
            headers={"X-Cron-Token": "test-token"},
        )
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_imported"] == 1
    assert any(run.get("status") == "ok" and run.get("mode") == "imap"
               for run in data["runs"])


def test_cron_skips_not_due_sources(client, auth_header, indeed_source, monkeypatch):
    """Source mit last_crawled_at < interval → skip (kein run-entry)."""
    headers, user = auth_header
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")

    # Source wurde gerade gecrawlt, Interval ist 60 Min → nicht due.
    indeed_source.last_crawled_at = datetime.utcnow()
    indeed_source.crawl_interval_min = 60
    db.session.commit()

    r = client.post(
        "/api/jobs/indeed-email-import-all",
        headers={"X-Cron-Token": "test-token"},
    )
    assert r.status_code == 200
    data = r.get_json()
    # Quelle existiert (total_sources=1) aber wurde nicht verarbeitet (kein run)
    assert data["total_sources"] == 1
    assert data["processed_runs"] == 0


def test_cron_requires_token(client, indeed_source):
    r = client.post("/api/jobs/indeed-email-import-all")
    assert r.status_code in (401, 403)


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


# ── Cron iteriert über alle drei _email-Typen ────────────────────────────


def test_cron_endpoint_iterates_all_three_email_types(
    client, auth_header, monkeypatch,
):
    """Cron-Endpoint /api/jobs/indeed-email-import-all verarbeitet
    indeed_email, linkedin_email, xing_email gleichzeitig."""
    headers, user = auth_header
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")

    # IMAP-Creds setzen, damit der Cron-Handler den has_imap-Zweig nimmt
    # (sonst werden alle drei Sources mit skipped_no_credentials abgebrochen,
    # bevor EmailJobsAdapter.fetch überhaupt aufgerufen wird).
    from imap_service import IMAPCredentialManager
    user.imap_host = "imap.example.com"
    user.imap_user = "u@example.com"
    user.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.commit()

    for stype, name in [
        ("indeed_email", "Indeed"),
        ("linkedin_email", "LinkedIn"),
        ("xing_email", "Xing"),
    ]:
        src = JobSource(user_id=user.id, type=stype, name=name, enabled=True)
        src.config = {}
        db.session.add(src)
    db.session.commit()
    # Bestehende indeed_source-Fixture wird hier NICHT verwendet — wir legen
    # die Sources direkt an, sodass exakt 3 existieren.

    seen_types = []

    def fake_fetch(self):
        seen_types.append(self.profile.name)
        return []

    monkeypatch.setattr(
        "services.job_sources.email_jobs.EmailJobsAdapter.fetch",
        fake_fetch,
    )

    resp = client.post(
        "/api/jobs/indeed-email-import-all",
        headers={"X-Cron-Token": "test-token"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_sources"] == 3
    assert set(seen_types) == {"indeed", "linkedin", "xing"}


def _make_admin():
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


def test_cron_endpoint_returns_202_and_enqueues_one_task_per_eligible_source(
    client, auth_header, monkeypatch,
):
    """Endpoint enqueueT EINE Task pro eligible Source und returnt 202+task_ids."""
    headers, user = auth_header
    _make_admin()
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from imap_service import IMAPCredentialManager
    user.imap_host = "imap.example.com"
    user.imap_user = "u@example.com"
    user.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.commit()

    for stype, name in [("indeed_email", "I"), ("linkedin_email", "L"),
                        ("xing_email", "X")]:
        s = JobSource(user_id=user.id, type=stype, name=name, enabled=True,
                      crawl_interval_min=60)
        s.config = {}
        db.session.add(s)
    db.session.commit()

    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    data = r.get_json()
    assert data["enqueued"] == 3
    assert len(data["task_ids"]) == 3


def test_cron_endpoint_skips_not_due_sources_at_enqueue_time(
    client, auth_header, indeed_source, monkeypatch,
):
    """Source mit last_crawled_at < interval → KEINE Task wird enqueueT."""
    _make_admin()
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    indeed_source.last_crawled_at = datetime.utcnow()
    indeed_source.crawl_interval_min = 60
    db.session.commit()

    r = client.post("/api/jobs/indeed-email-import-all",
                    headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 202
    data = r.get_json()
    assert data["enqueued"] == 0
    assert data["task_ids"] == []


# ── Source-Type-Validation: linkedin_email + xing_email ───────────────────


def test_create_linkedin_email_source_with_valid_config(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "LinkedIn Folder",
        "type": "linkedin_email",
        "config": {"folder": "[Google Mail]/Alle Nachrichten", "lookback_days": 30},
    }, headers=headers)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["source"]["type"] == "linkedin_email"


def test_create_xing_email_source_with_valid_config(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Xing Folder",
        "type": "xing_email",
        "config": {"folder": "INBOX", "lookback_days": 14},
    }, headers=headers)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["source"]["type"] == "xing_email"


def test_create_linkedin_email_source_rejects_bad_folder(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Bad",
        "type": "linkedin_email",
        "config": {"folder": "bad\r\n; DROP TABLE"},
    }, headers=headers)
    assert r.status_code == 400


def test_create_xing_email_source_rejects_invalid_lookback(client, auth_header):
    headers, _ = auth_header
    r = client.post("/api/jobs/sources", json={
        "name": "Bad",
        "type": "xing_email",
        "config": {"folder": "INBOX", "lookback_days": 9999},
    }, headers=headers)
    assert r.status_code == 400


# ── Bulk-Email Endpoint ───────────────────────────────────────────────────


def test_bulk_email_creates_three_sources(client, auth_header):
    """POST /api/jobs/sources/bulk-email mit 3 Plattformen legt 3 Sources an."""
    headers, user = auth_header
    resp = client.post(
        "/api/jobs/sources/bulk-email",
        headers=headers,
        json={
            "platforms": ["indeed", "linkedin", "xing"],
            "folder": "[Google Mail]/Alle Nachrichten",
            "lookback_days": 30,
            "limit": 100,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert len(data["sources"]) == 3
    types = {s["type"] for s in data["sources"]}
    assert types == {"indeed_email", "linkedin_email", "xing_email"}
    # Idempotent: zweiter Aufruf legt nichts neues an
    resp2 = client.post(
        "/api/jobs/sources/bulk-email",
        headers=headers,
        json={
            "platforms": ["indeed", "linkedin", "xing"],
            "folder": "[Google Mail]/Alle Nachrichten",
        },
    )
    assert resp2.status_code == 201
    assert resp2.get_json()["sources"] == []
    # DB hat trotzdem nur 3 Sources für diesen User
    assert JobSource.query.filter_by(user_id=user.id).count() == 3


def test_bulk_email_rejects_empty_platforms(client, auth_header):
    headers, _ = auth_header
    resp = client.post(
        "/api/jobs/sources/bulk-email",
        headers=headers,
        json={"platforms": [], "folder": "INBOX"},
    )
    assert resp.status_code == 400


def test_bulk_email_rejects_unknown_platform(client, auth_header):
    headers, _ = auth_header
    resp = client.post(
        "/api/jobs/sources/bulk-email",
        headers=headers,
        json={"platforms": ["facebook"], "folder": "INBOX"},
    )
    assert resp.status_code == 400


def test_bulk_email_only_one_platform_allowed(client, auth_header):
    """Auch eine einzelne Plattform ist OK — legt 1 Source an."""
    headers, _ = auth_header
    resp = client.post(
        "/api/jobs/sources/bulk-email",
        headers=headers,
        json={"platforms": ["linkedin"], "folder": "INBOX"},
    )
    assert resp.status_code == 201
    assert len(resp.get_json()["sources"]) == 1
    assert resp.get_json()["sources"][0]["type"] == "linkedin_email"
