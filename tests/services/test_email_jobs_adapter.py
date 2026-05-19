"""Unit-Tests für EmailJobsAdapter mit verschiedenen Profilen."""
from unittest.mock import MagicMock
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES


def test_adapter_accepts_profile_indeed():
    adapter = EmailJobsAdapter(
        config={"folder": "INBOX", "lookback_days": 30},
        user=MagicMock(),
        platform_profile=PROFILES["indeed"],
    )
    assert adapter.profile.name == "indeed"


def test_adapter_accepts_profile_linkedin():
    adapter = EmailJobsAdapter(
        config={"folder": "INBOX", "lookback_days": 30},
        user=MagicMock(),
        platform_profile=PROFILES["linkedin"],
    )
    assert adapter.profile.name == "linkedin"


def test_adapter_parses_single_linkedin_job_subject():
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    email_dict = {
        "subject": "Neue Stelle: Senior Python Developer bei Acme GmbH",
        "from": "jobs-noreply@linkedin.com",
        "body": "Schau dir https://www.linkedin.com/jobs/view/3812345678/ an",
        "date": "2026-05-19T10:00:00",
        "message_id": "<abc@linkedin.com>",
    }
    jobs = adapter.parse_emails([email_dict])
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Python Developer"
    assert jobs[0].company == "Acme GmbH"
    assert "linkedin.com/jobs/view/3812345678" in jobs[0].url


def test_adapter_digest_triggers_ai_fallback(monkeypatch):
    """≥3 LinkedIn-URLs im Body → sofort AI-Fallback (kein Subject-Regex)."""
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    ai_called = {"count": 0, "hint": None}

    def fake_ai(em):
        ai_called["count"] += 1
        ai_called["hint"] = adapter.profile.ai_hint
        from services.job_sources.base import FetchedJob
        return [
            FetchedJob(
                title="A", company="X", location="DE",
                url="https://linkedin.com/jobs/view/1", platform="linkedin",
                posted_at=None, external_id="linkedin:1", raw={}
            )
        ]

    monkeypatch.setattr(adapter, "_ai_fallback_digest", fake_ai)
    email_dict = {
        "subject": "Jobs you may be interested in",
        "from": "jobs-noreply@linkedin.com",
        "body": (
            "1. https://linkedin.com/jobs/view/1 "
            "2. https://linkedin.com/jobs/view/2 "
            "3. https://linkedin.com/jobs/view/3"
        ),
        "date": "2026-05-19T10:00:00",
    }
    adapter.parse_emails([email_dict])
    assert ai_called["count"] == 1
    assert "LinkedIn" in ai_called["hint"]


def test_adapter_from_whitelist_blocks_wrong_domain():
    """Email mit xing.com From wird bei LinkedIn-Profil NICHT akzeptiert."""
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    email_dict = {
        "subject": "Neue Stelle bei Acme",
        "from": "jobs@xing.com",
        "body": "https://linkedin.com/jobs/view/3812345678/",
        "date": "2026-05-19T10:00:00",
    }
    jobs = adapter.parse_emails([email_dict])
    # Erwartung: From-Whitelist-Mismatch → Mail wird skipped
    assert jobs == []
