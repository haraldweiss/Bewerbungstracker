# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests für services.job_matching.feedback_context (Phase B)."""
import json
import pytest
from datetime import datetime, timedelta


def _make_job_match(db, user_id, days_ago=0, feedback_text=None, feedback_reasons=None):
    from models import JobSource, RawJob, JobMatch
    src = JobSource(name=f"Src{days_ago}", type="rss", enabled=True,
                    config={"url": f"https://ex.com/feed{days_ago}"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id=f"ext-{days_ago}",
                 title=f"Job {days_ago}", url=f"https://ex.com/j/{days_ago}",
                 crawl_status="raw")
    db.session.add(raw); db.session.flush()
    match = JobMatch(
        raw_job_id=raw.id, user_id=user_id, status="dismissed",
        feedback_text=feedback_text,
        feedback_reasons=json.dumps(feedback_reasons) if feedback_reasons else None,
        updated_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.session.add(match); db.session.commit()
    return match


def test_no_feedback_returns_empty(app, user_factory):
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    assert get_user_feedback_context(user.id) == ""


def test_feedback_text_only(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    _make_job_match(db, user.id, days_ago=1, feedback_text="Salary zu niedrig")
    out = get_user_feedback_context(user.id)
    assert "Salary zu niedrig" in out
    assert "user_feedback_history" in out


def test_feedback_reasons_only(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    _make_job_match(db, user.id, days_ago=1, feedback_reasons=["rejected_after_apply"])
    out = get_user_feedback_context(user.id)
    assert "rejected_after_apply" in out


def test_combined_text_and_reasons(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    _make_job_match(db, user.id, days_ago=1,
                    feedback_text="Recruiter unfreundlich",
                    feedback_reasons=["rejected_after_apply"])
    out = get_user_feedback_context(user.id)
    assert "Recruiter unfreundlich" in out
    assert "rejected_after_apply" in out


def test_limit_respected(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    for i in range(15):
        _make_job_match(db, user.id, days_ago=i, feedback_text=f"Feedback {i}")
    out = get_user_feedback_context(user.id, limit=5)
    count = sum(1 for i in range(15) if f"Feedback {i}" in out)
    assert count == 5


def test_newest_first(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    _make_job_match(db, user.id, days_ago=5, feedback_text="alt")
    _make_job_match(db, user.id, days_ago=1, feedback_text="neu")
    out = get_user_feedback_context(user.id)
    assert out.find("neu") < out.find("alt")


def test_skips_entries_without_feedback(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    _make_job_match(db, user.id, days_ago=1)
    assert get_user_feedback_context(user.id) == ""


def test_isolated_per_user(app, user_factory):
    from database import db
    from services.job_matching.feedback_context import get_user_feedback_context
    u1 = user_factory()
    u2 = user_factory()
    _make_job_match(db, u1.id, days_ago=1, feedback_text="u1-secret")
    _make_job_match(db, u2.id, days_ago=1, feedback_text="u2-secret")
    out1 = get_user_feedback_context(u1.id)
    out2 = get_user_feedback_context(u2.id)
    assert "u1-secret" in out1 and "u2-secret" not in out1
    assert "u2-secret" in out2 and "u1-secret" not in out2


def test_robust_malformed_reasons_json(app, user_factory):
    from database import db
    from models import JobMatch
    from services.job_matching.feedback_context import get_user_feedback_context
    user = user_factory()
    m = _make_job_match(db, user.id, days_ago=1, feedback_text="OK-text")
    m.feedback_reasons = "not-valid-json"
    db.session.commit()
    out = get_user_feedback_context(user.id)
    assert "OK-text" in out
