# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests für services.job_matching.feedback_bridge.

Phase A: Bridge Application.notes → JobMatch.feedback_text bei terminalem
Status (absage/ghosting/interview/zusage). Existing learner.py greift dann
auf das gespiegelte feedback_text zu.
"""
import json
import pytest


def _make_app_with_match(app_ctx, user_factory, status, notes):
    """Create Application + verknüpften JobMatch (über imported_application_id)."""
    from database import db
    from models import Application, RawJob, JobMatch, JobSource

    user = user_factory()
    # JobSource + RawJob (JobSource hat KEIN scope-Feld — nur name/type/enabled/config)
    src = JobSource(name="Test Source", type="rss",
                    enabled=True, config={"url": "https://example.com/feed"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="test-external-1",
                 title="Test Job", url="https://example.com/job/1",
                 crawl_status="raw")
    db.session.add(raw); db.session.flush()
    application = Application(
        user_id=user.id, company="TestCo", position="Dev",
        status=status, notes=notes,
    )
    db.session.add(application); db.session.flush()
    match = JobMatch(raw_job_id=raw.id, user_id=user.id,
                     status="imported",
                     imported_application_id=application.id)
    db.session.add(match)
    db.session.commit()
    return user, application, match


def test_absage_triggers_bridge(app, user_factory):
    """status='absage' + notes nicht leer → feedback_text gefüllt + tag gesetzt."""
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "absage", "Salary war zu niedrig."
    )
    result = maybe_bridge_to_feedback(application)
    assert result is True
    from models import JobMatch
    refreshed = JobMatch.query.get(match.id)
    assert "Salary war zu niedrig" in refreshed.feedback_text
    reasons = json.loads(refreshed.feedback_reasons)
    assert "rejected_after_apply" in reasons


def test_interview_triggers_bridge(app, user_factory):
    """status='interview' → tag 'positive_signal_interview'."""
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "interview", "1. Gespräch sehr positiv."
    )
    assert maybe_bridge_to_feedback(application) is True
    from models import JobMatch
    refreshed = JobMatch.query.get(match.id)
    assert "1. Gespräch sehr positiv" in refreshed.feedback_text
    assert "positive_signal_interview" in json.loads(refreshed.feedback_reasons)


def test_zusage_triggers_bridge(app, user_factory):
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "zusage", "Angenommen!"
    )
    assert maybe_bridge_to_feedback(application) is True
    from models import JobMatch
    refreshed = JobMatch.query.get(match.id)
    assert "positive_signal_offer" in json.loads(refreshed.feedback_reasons)


def test_ghosting_treated_as_rejected(app, user_factory):
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "ghosting", "Keine Rückmeldung seit 4 Wochen."
    )
    assert maybe_bridge_to_feedback(application) is True
    from models import JobMatch
    refreshed = JobMatch.query.get(match.id)
    assert "rejected_after_apply" in json.loads(refreshed.feedback_reasons)


def test_empty_notes_skipped(app, user_factory):
    """Notes leer → kein Update."""
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "absage", ""
    )
    assert maybe_bridge_to_feedback(application) is False


def test_non_terminal_status_skipped(app, user_factory):
    """status='beworben' (non-terminal) → kein Update auch mit notes."""
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "beworben", "Bewerbung abgeschickt."
    )
    assert maybe_bridge_to_feedback(application) is False


def test_no_linked_jobmatch_skipped(app, user_factory):
    """Application ohne JobMatch (manuelle Bewerbung) → kein Update."""
    from database import db
    from models import Application
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user = user_factory()
    application = Application(
        user_id=user.id, company="ManualCo", position="X",
        status="absage", notes="manuelle Bewerbung mit notes",
    )
    db.session.add(application); db.session.commit()
    assert maybe_bridge_to_feedback(application) is False


def test_idempotent_no_double_append(app, user_factory):
    """Zweiter Aufruf mit identischen notes → kein doppeltes Anhängen."""
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    from models import JobMatch
    user, application, match = _make_app_with_match(
        app, user_factory, "absage", "Gleicher Text."
    )
    assert maybe_bridge_to_feedback(application) is True
    text_after_first = JobMatch.query.get(match.id).feedback_text
    # Zweiter Aufruf
    result = maybe_bridge_to_feedback(application)
    text_after_second = JobMatch.query.get(match.id).feedback_text
    assert result is False  # nichts zu tun
    assert text_after_first == text_after_second
    # Tag nicht doppelt
    reasons = json.loads(JobMatch.query.get(match.id).feedback_reasons)
    assert reasons.count("rejected_after_apply") == 1


def test_malformed_feedback_reasons_robust(app, user_factory):
    """Existing malformed JSON in feedback_reasons → fallback zu [] + neuer Tag hinzu."""
    from database import db
    from models import JobMatch
    from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
    user, application, match = _make_app_with_match(
        app, user_factory, "absage", "Test feedback."
    )
    # Korrumpiere feedback_reasons direkt
    match.feedback_reasons = "not-valid-json"
    db.session.commit()
    assert maybe_bridge_to_feedback(application) is True
    refreshed = JobMatch.query.get(match.id)
    reasons = json.loads(refreshed.feedback_reasons)
    assert reasons == ["rejected_after_apply"]
