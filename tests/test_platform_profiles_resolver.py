# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
import re
from services.job_sources.email_jobs import (
    get_profile, PROFILES, PlatformProfile, _build_profile_from_row,
)


def test_get_profile_hardcoded_indeed():
    p = get_profile("indeed")
    assert p is PROFILES["indeed"]


def test_get_profile_hardcoded_linkedin():
    p = get_profile("linkedin")
    assert p.name == "linkedin"


def test_get_profile_unknown_raises(app):
    with pytest.raises(KeyError):
        get_profile("does_not_exist_anywhere")


def test_get_profile_from_db(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone",
        display_name="Stepstone",
        domain="stepstone.de",
        subject_must_contain='["stelle", "job"]',
        ai_schema_hint="Test hint",
        digest_threshold=3,
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()

    p = get_profile("stepstone")
    assert isinstance(p, PlatformProfile)
    assert p.name == "stepstone"
    assert p.source_label == "Stepstone"
    assert p.subject_must_contain == ("stelle", "job")
    assert p.ai_schema_hint == "Test hint"


def test_build_profile_auto_generates_url_pattern(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert p.url_pattern.search("https://www.stepstone.de/job/12345")
    assert p.url_pattern.search("https://www.stepstone.de/anything/here")
    assert not p.url_pattern.search("https://example.com/foo")


def test_build_profile_auto_generates_from_whitelist(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert len(p.from_whitelist) == 1
    pattern = re.compile(p.from_whitelist[0])
    assert pattern.search("noreply@stepstone.de")
    assert pattern.search("alerts@jobs.stepstone.de")
    assert not pattern.search("noreply@example.com")


def test_build_profile_url_pattern_override(app, user_factory):
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    custom = r"https?://(?:www\.)?stepstone\.de/stellenangebote/\d+"
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", url_pattern_override=custom,
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    p = _build_profile_from_row(row)
    assert p.url_pattern.pattern == custom
    assert p.url_pattern.search("https://stepstone.de/stellenangebote/123")
    assert not p.url_pattern.search("https://stepstone.de/news/foo")


def test_build_profile_falls_back_on_invalid_url_override(app, user_factory, caplog):
    """If url_pattern_override is malformed, fall back to auto-gen + warn-log."""
    import logging
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]",
        url_pattern_override="[invalid(regex",
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    with caplog.at_level(logging.WARNING):
        p = _build_profile_from_row(row)
    # Falls back: auto-generated url_pattern matches stepstone.de
    assert p.url_pattern.search("https://stepstone.de/job/1")
    assert any("url_pattern_override" in rec.message for rec in caplog.records)


def test_build_profile_falls_back_on_invalid_from_whitelist_override(app, user_factory, caplog):
    """If from_whitelist_override is malformed, fall back to auto-gen."""
    import logging
    import re as _re
    from database import db
    from models import PlatformProfileRow
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]",
        from_whitelist_override="[bad(regex",
        created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    with caplog.at_level(logging.WARNING):
        p = _build_profile_from_row(row)
    # Falls back: auto-generated from_whitelist matches *@stepstone.de
    assert _re.compile(p.from_whitelist[0]).search("noreply@stepstone.de")
    assert any("from_whitelist_override" in rec.message for rec in caplog.records)


def test_get_adapter_with_db_platform(app, user_factory):
    """get_adapter() für 'stepstone_email' findet die Plattform in der DB."""
    from database import db
    from models import PlatformProfileRow
    from services.job_sources import get_adapter
    from services.job_sources.email_jobs import EmailJobsAdapter
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone", display_name="Stepstone", domain="stepstone.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()

    adapter = get_adapter("stepstone_email", config={}, user=user)
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile.name == "stepstone"
