# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from sqlalchemy.exc import IntegrityError
from models import PlatformProfileRow


def test_create_platform_profile(app, user_factory):
    user = user_factory()
    row = PlatformProfileRow(
        slug="stepstone",
        display_name="Stepstone",
        domain="stepstone.de",
        subject_must_contain='["stelle", "job"]',
        ai_schema_hint="Generic European job board.",
        digest_threshold=3,
        created_by_user_id=user.id,
    )
    from database import db
    db.session.add(row)
    db.session.commit()
    fetched = PlatformProfileRow.query.filter_by(slug="stepstone").first()
    assert fetched.display_name == "Stepstone"
    assert fetched.domain == "stepstone.de"


def test_slug_unique(app, user_factory):
    from database import db
    user = user_factory()
    r1 = PlatformProfileRow(
        slug="stepstone", display_name="A", domain="a.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(r1); db.session.commit()
    r2 = PlatformProfileRow(
        slug="stepstone", display_name="B", domain="b.de",
        subject_must_contain="[]", created_by_user_id=user.id,
    )
    db.session.add(r2)
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_to_dict_handles_malformed_json(app, user_factory):
    """If subject_must_contain contains garbage, to_dict() must not raise."""
    from database import db
    user = user_factory()
    row = PlatformProfileRow(
        slug="malformed", display_name="X", domain="x.de",
        subject_must_contain="not-valid-json", created_by_user_id=user.id,
    )
    db.session.add(row); db.session.commit()
    d = row.to_dict()
    assert d["subject_must_contain"] == []
