# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests für services.job_matching.success_context (Phase C)."""
import pytest


def _add_app(db, user_id, company, position, status, notes=""):
    from models import Application
    a = Application(
        user_id=user_id, company=company, position=position,
        status=status, notes=notes,
    )
    db.session.add(a); db.session.commit()
    return a


def test_no_successful_returns_empty(app, user_factory):
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    assert get_user_success_context(user.id) == ""


def test_zusage_included(app, user_factory):
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    _add_app(db, user.id, "TechCo", "SOC Engineer", "zusage", "Angenommen!")
    out = get_user_success_context(user.id)
    assert "TechCo" in out
    assert "SOC Engineer" in out
    assert "Angenommen" in out
    assert "successful_applications" in out
    assert "zusage" in out.lower()


def test_interview_included(app, user_factory):
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    _add_app(db, user.id, "SecCorp", "Security Analyst", "interview", "1. Gespräch positiv")
    out = get_user_success_context(user.id)
    assert "SecCorp" in out
    assert "Security Analyst" in out
    assert "interview" in out.lower()


def test_absage_excluded(app, user_factory):
    """Nur interview/zusage zählen — absage ist KEIN Erfolg."""
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    _add_app(db, user.id, "BadCo", "X", "absage", "leider nicht")
    out = get_user_success_context(user.id)
    assert out == ""


def test_beworben_excluded(app, user_factory):
    """status beworben (laufend, kein Erfolg) → nicht inkludiert."""
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    _add_app(db, user.id, "PendingCo", "X", "beworben", "läuft noch")
    out = get_user_success_context(user.id)
    assert out == ""


def test_limit_respected(app, user_factory):
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    for i in range(10):
        _add_app(db, user.id, f"Co{i}", f"Pos{i}", "interview", f"note{i}")
    out = get_user_success_context(user.id, limit=3)
    count = sum(1 for i in range(10) if f"Co{i}" in out)
    assert count == 3


def test_isolated_per_user(app, user_factory):
    from database import db
    from services.job_matching.success_context import get_user_success_context
    u1 = user_factory()
    u2 = user_factory()
    _add_app(db, u1.id, "U1Co", "X", "zusage", "u1-info")
    _add_app(db, u2.id, "U2Co", "Y", "zusage", "u2-info")
    out1 = get_user_success_context(u1.id)
    assert "U1Co" in out1 and "U2Co" not in out1


def test_skips_deleted_apps(app, user_factory):
    """Soft-deleted Applications werden nicht inkludiert."""
    from database import db
    from datetime import datetime
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    a = _add_app(db, user.id, "DeletedCo", "X", "zusage", "war gut")
    a.deleted = True
    a.deleted_at = datetime.utcnow()
    db.session.commit()
    out = get_user_success_context(user.id)
    assert "DeletedCo" not in out


def test_notes_truncated_at_300(app, user_factory):
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    long_notes = "A" * 500
    _add_app(db, user.id, "Co", "X", "interview", long_notes)
    out = get_user_success_context(user.id)
    assert "AAAA" in out
    # 500 chars notes must not appear fully (300+truncation)
    assert "A" * 500 not in out


def test_empty_notes_still_includes_app(app, user_factory):
    """Application ohne notes wird trotzdem gezeigt (company+position reichen)."""
    from database import db
    from services.job_matching.success_context import get_user_success_context
    user = user_factory()
    _add_app(db, user.id, "NoNotesCo", "Pos", "zusage", "")
    out = get_user_success_context(user.id)
    assert "NoNotesCo" in out
