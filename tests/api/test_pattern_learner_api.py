# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Integration-Tests fuer Pattern-Learner-API (POST /train-pattern)."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from database import db
from models import JobSource, LearnedEmailPattern, User


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


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_source(user, type_="linkedin_email"):
    src = JobSource(
        user_id=user.id,
        type=type_,
        name="LinkedIn",
        enabled=True,
    )
    src.config = {"folder": "INBOX", "lookback_days": 30, "limit": 30}
    db.session.add(src)
    db.session.commit()
    return src


def _fake_pattern():
    return {
        "subject_pattern": {
            "prefix_optional": True,
            "prefix_keywords": [],
            "separator": "bei",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": [],
            "company_blacklist_separators": [],
        },
    }


# ── Tests ────────────────────────────────────────────────────────────────


def test_train_pattern_happy_path(client, auth_header):
    headers, user = auth_header
    src = _make_source(user)
    body = (
        "Senior Engineer\r\n"
        "TechCorp\r\n"
        "Berlin, Deutschland\r\n"
        "Jobangebot ansehen: https://linkedin.com/comm/jobs/view/1"
    )
    fake_mails = [{"subject": "Senior Engineer bei TechCorp", "body": body}] * 30
    with patch(
        "services.job_sources.pattern_learner.fetch_sample_mails",
        return_value=fake_mails,
    ), patch(
        "services.job_sources.pattern_learner.ai_learn_pattern",
        return_value=_fake_pattern(),
    ):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=headers,
            json={},
        )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["hit_rate"] >= 0.40
    active = LearnedEmailPattern.query.filter_by(
        platform="linkedin", is_active=True
    ).first()
    assert active is not None
    assert active.trained_by_user_id == user.id


def test_train_rate_limited(client, auth_header):
    headers, user = auth_header
    src = _make_source(user)
    db.session.add(LearnedEmailPattern(
        platform="linkedin",
        pattern_json="{}",
        sample_count=10,
        hit_rate=0.5,
        trained_at=datetime.utcnow() - timedelta(minutes=30),
        trained_by_user_id=user.id,
        is_active=True,
    ))
    db.session.commit()
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=headers,
        json={},
    )
    assert resp.status_code == 429


def test_train_hit_rate_too_low(client, auth_header):
    headers, user = auth_header
    src = _make_source(user)
    fake_mails = [{"subject": "S", "body": "no structure"}] * 30
    with patch(
        "services.job_sources.pattern_learner.fetch_sample_mails",
        return_value=fake_mails,
    ), patch(
        "services.job_sources.pattern_learner.ai_learn_pattern",
        return_value=_fake_pattern(),
    ):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=headers,
            json={},
        )
    assert resp.status_code == 422
    assert LearnedEmailPattern.query.filter_by(platform="linkedin").count() == 0


def test_train_auto_reduces_train_size_when_few_mails(client, auth_header):
    """Bei < train_size + 1 Mails wird train_size auto-reduziert statt 400."""
    headers, user = auth_header
    src = _make_source(user)
    body = (
        "Senior Engineer\r\n"
        "TechCorp\r\n"
        "Berlin, Deutschland\r\n"
        "Jobangebot ansehen: https://linkedin.com/comm/jobs/view/1"
    )
    # Nur 2 Mails (default train_size=5 wuerde sonst 400 returnen).
    fake_mails = [{"subject": "Senior Engineer bei TechCorp", "body": body}] * 2
    with patch(
        "services.job_sources.pattern_learner.fetch_sample_mails",
        return_value=fake_mails,
    ), patch(
        "services.job_sources.pattern_learner.ai_learn_pattern",
        return_value=_fake_pattern(),
    ):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=headers,
            json={},
        )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["train_size_reduced"] is True
    assert data["train_size_used"] == 1
    assert data["sample_count"] == 1
    assert data["mails_total"] == 2


def test_train_rejects_single_mail(client, auth_header):
    """1 Mail = kann nicht train+test splitten -> 400."""
    headers, user = auth_header
    src = _make_source(user)
    fake_mails = [{"subject": "S", "body": "no structure"}]
    with patch(
        "services.job_sources.pattern_learner.fetch_sample_mails",
        return_value=fake_mails,
    ):
        resp = client.post(
            f"/api/jobs/sources/{src.id}/train-pattern",
            headers=headers,
            json={},
        )
    assert resp.status_code == 400
    assert "mind. 2" in resp.get_json()["error"].lower() or "2 noetig" in resp.get_json()["error"]


def test_train_non_email_source(client, auth_header):
    headers, user = auth_header
    # RSS-Source ueber direkte DB-Insertion, da Endpoint-Validation
    # nur Source-Type prueft, nicht config.
    src = JobSource(user_id=user.id, type="rss", name="Some Feed", enabled=True)
    src.config = {"url": "https://example.com/feed.xml"}
    db.session.add(src)
    db.session.commit()
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=headers,
        json={},
    )
    assert resp.status_code == 400


def test_train_forbidden(client, auth_header, user_factory):
    headers, _ = auth_header
    other = user_factory()
    src = _make_source(other)
    resp = client.post(
        f"/api/jobs/sources/{src.id}/train-pattern",
        headers=headers,
        json={},
    )
    assert resp.status_code == 403


def test_get_learned_patterns_lists_active(client, auth_header, db_session):
    headers, user = auth_header
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json="{}", sample_count=20, hit_rate=0.55,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    ))
    db_session.add(LearnedEmailPattern(
        platform="xing", pattern_json="{}", sample_count=15, hit_rate=0.70,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    ))
    db_session.commit()
    resp = client.get("/api/jobs/learned-patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    platforms = {p["platform"] for p in data["patterns"]}
    assert "linkedin" in platforms
    assert "xing" in platforms
    for p in data["patterns"]:
        assert "history_count" in p


def test_get_learned_patterns_history_count(client, auth_header, db_session):
    """history_count = anzahl rows fuer gleiche plattform die NICHT die aktive sind."""
    headers, user = auth_header
    # 1 inactive older + 1 active newer for linkedin
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":1}', sample_count=10, hit_rate=0.4,
        trained_at=datetime.utcnow() - timedelta(days=3),
        trained_by_user_id=user.id, is_active=False,
    ))
    db_session.add(LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":2}', sample_count=15, hit_rate=0.6,
        trained_at=datetime.utcnow(), trained_by_user_id=user.id, is_active=True,
    ))
    db_session.commit()
    resp = client.get("/api/jobs/learned-patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    ln = next(p for p in data["patterns"] if p["platform"] == "linkedin")
    assert ln["history_count"] == 1


def test_rollback_restores_previous(client, auth_header, db_session):
    headers, user = auth_header
    older = LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":1}', sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow() - timedelta(days=2),
        trained_by_user_id=user.id, is_active=False,
    )
    newer = LearnedEmailPattern(
        platform="linkedin", pattern_json='{"v":2}', sample_count=20, hit_rate=0.7,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id, is_active=True,
    )
    db_session.add_all([older, newer]); db_session.commit()
    resp = client.post(
        "/api/jobs/learned-patterns/linkedin/rollback",
        headers=headers, json={},
    )
    assert resp.status_code == 200
    db_session.expire_all()
    older_after = LearnedEmailPattern.query.filter_by(pattern_json='{"v":1}').first()
    newer_after = LearnedEmailPattern.query.filter_by(pattern_json='{"v":2}').first()
    assert older_after.is_active is True
    assert newer_after.is_active is False
    assert newer_after.rolled_back_at is not None
    assert newer_after.rolled_back_by_user_id == user.id


def test_rollback_no_history_returns_400(client, auth_header, db_session):
    headers, user = auth_header
    only_one = LearnedEmailPattern(
        platform="linkedin", pattern_json='{}', sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id, is_active=True,
    )
    db_session.add(only_one); db_session.commit()
    resp = client.post(
        "/api/jobs/learned-patterns/linkedin/rollback",
        headers=headers, json={},
    )
    assert resp.status_code == 400


def test_rollback_no_active_pattern_returns_400(client, auth_header, db_session):
    headers, user = auth_header
    # Plattform mit nur inaktiven Rows
    db_session.add(LearnedEmailPattern(
        platform="xing", pattern_json='{}', sample_count=10, hit_rate=0.5,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id, is_active=False,
    ))
    db_session.commit()
    resp = client.post(
        "/api/jobs/learned-patterns/xing/rollback",
        headers=headers, json={},
    )
    assert resp.status_code == 400
