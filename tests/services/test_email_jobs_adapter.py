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

    def fake_ai(em, *, deadline=None):
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


import json as _json
from datetime import datetime as _dt


def test_adapter_uses_learned_when_active(app, db_session):
    """Aktives LearnedEmailPattern ueberstimmt das hardcoded body_card_re."""
    from models import LearnedEmailPattern, User
    # Need a real user_id for FK constraint
    u = User.query.first()
    if u is None:
        u = User(id="adapter-test-uid", email="x@y.de", password_hash="x")
        db_session.add(u); db_session.commit()
    learned = LearnedEmailPattern(
        platform="linkedin",
        pattern_json=_json.dumps({
            "subject_pattern": {"prefix_optional": True, "prefix_keywords": [], "separator": "bei"},
            "body_card": {
                "url_labels": ["MAGIC_LABEL"],
                "fields_before_url": ["title", "company", "location"],
                "separator_lines_allowed": 5,
            },
            "filters": {"title_blacklist": [], "company_blacklist_separators": []},
        }),
        sample_count=10, hit_rate=0.8,
        trained_at=_dt.utcnow(),
        trained_by_user_id=u.id, is_active=True,
    )
    db_session.add(learned); db_session.commit()

    from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
    from unittest.mock import MagicMock
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    em = {
        "subject": "Senior Dev bei Acme",
        "from": "jobs@linkedin.com",
        "body": (
            "Senior Dev\r\nAcme GmbH\r\nDE\r\n"
            "MAGIC_LABEL: https://linkedin.com/comm/jobs/view/999"
        ),
        "date": "2026-05-19T10:00:00",
    }
    jobs = adapter.parse_emails([em])
    assert len(jobs) == 1
    assert "999" in jobs[0].url
