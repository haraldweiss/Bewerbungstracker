# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für cron_indeed_email_import_source Handler."""
from unittest.mock import patch

import pytest

from database import db
from models import JobSource, User
from services.job_sources.base import FetchedJob


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
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
def user_with_imap(app):
    from imap_service import IMAPCredentialManager
    u = User(email="u@example.com", password_hash="x", is_active=True,
            job_discovery_enabled=True)
    u.imap_host = "imap.example.com"
    u.imap_user = "u@example.com"
    u.imap_password_encrypted = IMAPCredentialManager.encrypt_password("pw")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def indeed_source(user_with_imap):
    src = JobSource(user_id=user_with_imap.id, type="indeed_email",
                    name="Indeed", enabled=True, crawl_interval_min=60)
    src.config = {}
    db.session.add(src)
    db.session.commit()
    return src


def test_handler_imports_one_source_and_commits(app, indeed_source):
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    fetched = [FetchedJob(
        external_id="https://de.indeed.com/viewjob?jk=t1",
        title="Dev", url="https://de.indeed.com/viewjob?jk=t1",
        company="Acme", location="Berlin", description="...",
    )]
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["status"] == "ok"
    assert result["imported"] == 1
    assert result["mode"] == "imap"
    # last_crawled_at gesetzt → kommit erfolgt
    db.session.refresh(indeed_source)
    assert indeed_source.last_crawled_at is not None


def test_handler_returns_skipped_when_no_credentials(app):
    """User ohne IMAP/Apps-Script → skipped, KEIN raise."""
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    u = User(email="b@example.com", password_hash="x", is_active=True,
             job_discovery_enabled=True)
    db.session.add(u)
    db.session.commit()
    src = JobSource(user_id=u.id, type="indeed_email", name="x",
                    enabled=True, crawl_interval_min=60)
    src.config = {}
    db.session.add(src)
    db.session.commit()

    result = handle_cron_indeed_email_import_source(
        {"source_id": src.id}, progress_cb=None,
    )
    assert result["status"] == "skipped_no_credentials"


def test_handler_records_failure_and_auto_disables_after_threshold(app, indeed_source):
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    indeed_source.consecutive_failures = 4  # one more failure → 5 → disable
    db.session.commit()

    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               side_effect=RuntimeError("IMAP boom")):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["status"] == "error"
    assert "IMAP boom" in result["error"]
    db.session.refresh(indeed_source)
    assert indeed_source.consecutive_failures == 5
    assert indeed_source.enabled is False


def test_handler_blocked_company_creates_dismissed_match(app, indeed_source, user_with_imap):
    """Company in Reject-Window → JobMatch(status='dismissed',
    feedback_text='auto_blocked_by_rejection')."""
    from services.tasks.handlers.cron_indeed_email_import import (
        handle_cron_indeed_email_import_source,
    )
    from models import Application
    user_with_imap.job_reject_filter_enabled = True
    user_with_imap.job_reject_window_days = 180
    db.session.commit()
    # Application mit company='Acme' und Rejection-Status
    app_rec = Application(
        user_id=user_with_imap.id, company="Acme", position="Old",
        status="absage", applied_date=__import__('datetime').date.today(),
    )
    db.session.add(app_rec)
    db.session.commit()

    fetched = [FetchedJob(
        external_id="https://de.indeed.com/viewjob?jk=blocked1",
        title="Dev2", url="https://de.indeed.com/viewjob?jk=blocked1",
        company="Acme", location="Berlin", description="...",
    )]
    with patch('services.job_sources.email_jobs.IndeedEmailAdapter.fetch',
               return_value=fetched):
        result = handle_cron_indeed_email_import_source(
            {"source_id": indeed_source.id}, progress_cb=None,
        )
    assert result["imported"] == 0
    assert result["blocked_auto"] == 1
