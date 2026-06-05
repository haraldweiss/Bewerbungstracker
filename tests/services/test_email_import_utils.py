# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Unit-Tests für normalize_company() + get_rejected_companies_lower().

Hintergrund: Auto-Reject-Analyse (2026-06-05) zeigte 12+ User-Texte vom Typ
"X hat schon abgesagt", denen das System nur 7 Treffer entgegen­setzte —
Hauptursachen: (a) Company-String mit/ohne Rechtsform-Suffix, (b) Status
'ghosting' wurde nicht als Reject behandelt. Tests sichern beide Regeln ab.
"""
from datetime import datetime, timedelta

from database import db
from models import Application
from services.email_import_utils import (
    get_rejected_companies_lower,
    normalize_company,
)


def test_strips_common_german_legal_forms():
    assert normalize_company("BWI GmbH") == "bwi"
    assert normalize_company("Beispiel AG") == "beispiel"
    assert normalize_company("Foo KG") == "foo"
    assert normalize_company("Bar SE") == "bar"
    assert normalize_company("Baz mbH") == "baz"
    assert normalize_company("Qux UG") == "qux"


def test_strips_gmbh_co_kg_compound():
    assert normalize_company("Acme GmbH & Co. KG") == "acme"
    assert normalize_company("Acme GmbH & Co KG") == "acme"
    assert normalize_company("Acme GmbH Co. KG") == "acme"


def test_strips_trailing_group_holding():
    assert normalize_company("Signal Iduna Group AG") == "signal iduna"
    assert normalize_company("Telefónica Deutschland Holding") == "telefónica deutschland"
    assert normalize_company("Continental Group") == "continental"


def test_strips_english_legal_forms():
    assert normalize_company("Foo Inc.") == "foo"
    assert normalize_company("Bar Ltd") == "bar"
    assert normalize_company("Baz LLC") == "baz"
    assert normalize_company("Qux Corp") == "qux"


def test_strips_trailing_parenthesis():
    assert normalize_company("Continental (Germany)") == "continental"
    assert normalize_company("Acme GmbH (Berlin)") == "acme"


def test_no_change_when_no_suffix():
    assert normalize_company("Hire Feed") == "hire feed"
    assert normalize_company("Signal Iduna") == "signal iduna"
    assert normalize_company("Amadeus Fire") == "amadeus fire"


def test_handles_none_and_empty():
    assert normalize_company(None) == ""
    assert normalize_company("") == ""
    assert normalize_company("   ") == ""


def test_collapses_whitespace():
    assert normalize_company("  Signal   Iduna  Group   AG  ") == "signal iduna"
    assert normalize_company("Acme\tGmbH") == "acme"


def test_idempotent():
    cases = [
        "Signal Iduna Group AG",
        "Acme GmbH & Co. KG",
        "Continental (Germany)",
        "Hire Feed",
        "",
    ]
    for c in cases:
        once = normalize_company(c)
        twice = normalize_company(once)
        assert once == twice, f"not idempotent: {c!r} → {once!r} → {twice!r}"


def test_does_not_strip_legal_form_at_start():
    # "International Business Machines" darf nicht zu "Business Machines"
    # werden — das Suffix-Regex ist anchored at $.
    assert normalize_company("International Business Machines") == "international business machines"


def test_does_not_truncate_names_containing_legal_form_word():
    # "Decathlon" enthält "de" — darf nicht gestrippt werden
    assert normalize_company("Decathlon") == "decathlon"
    # "Cocacola" enthält kein eigenständiges Token
    assert normalize_company("Cocacola") == "cocacola"


def test_strips_e_v():
    assert normalize_company("Open Source e.V.") == "open source"
    assert normalize_company("KfH Kuratorium e.V.") == "kfh kuratorium"


# --- Integration: get_rejected_companies_lower (Status-Set + Window) -----

def _add_app(user_id: str, company: str, status: str,
             applied_days_ago: int | None = 0,
             created_days_ago: int = 0) -> Application:
    today = datetime.utcnow().date()
    applied = (today - timedelta(days=applied_days_ago)) if applied_days_ago is not None else None
    a = Application(
        user_id=user_id, company=company,
        position="Test Position", status=status,
        applied_date=applied,
        created_at=datetime.utcnow() - timedelta(days=created_days_ago),
    )
    db.session.add(a)
    db.session.commit()
    return a


def test_rejected_set_includes_absage_status(app, user_factory):
    with app.app_context():
        user = user_factory()
        _add_app(user.id, "Signal Iduna Group AG", "absage", applied_days_ago=10)
        result = get_rejected_companies_lower(user.id, window_days=180)
        assert result == {"signal iduna"}


def test_rejected_set_includes_ghosting_status(app, user_factory):
    """Regression: 'ghosting' wird als Reject behandelt (feedback_bridge
    mapped es ohnehin auf rejected_after_apply)."""
    with app.app_context():
        user = user_factory()
        _add_app(user.id, "Amadeus Fire", "ghosting", applied_days_ago=30)
        result = get_rejected_companies_lower(user.id, window_days=180)
        assert result == {"amadeus fire"}


def test_rejected_set_excludes_beworben_and_interview(app, user_factory):
    with app.app_context():
        user = user_factory()
        _add_app(user.id, "Acme GmbH", "beworben", applied_days_ago=5)
        _add_app(user.id, "Beta AG", "interview", applied_days_ago=5)
        _add_app(user.id, "Gamma KG", "absage", applied_days_ago=5)
        result = get_rejected_companies_lower(user.id, window_days=180)
        assert result == {"gamma"}


def test_rejected_set_respects_window(app, user_factory):
    with app.app_context():
        user = user_factory()
        _add_app(user.id, "Inside Window AG", "absage", applied_days_ago=10)
        _add_app(user.id, "Outside Window AG", "absage", applied_days_ago=400)
        result = get_rejected_companies_lower(user.id, window_days=180)
        assert result == {"inside window"}


def test_rejected_set_ignores_deleted(app, user_factory):
    with app.app_context():
        user = user_factory()
        a = _add_app(user.id, "Soft Deleted GmbH", "absage", applied_days_ago=5)
        a.deleted = True
        db.session.commit()
        result = get_rejected_companies_lower(user.id, window_days=180)
        assert result == set()
