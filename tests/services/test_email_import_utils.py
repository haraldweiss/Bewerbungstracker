# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Unit-Tests für normalize_company() in services/email_import_utils.py.

Hintergrund: Auto-Reject-Analyse (2026-06-05) zeigte 12+ User-Texte vom Typ
"X hat schon abgesagt", denen das System nur 7 Treffer entgegen­setzte —
Hauptursache: Company-String unterschiedlich ("Signal Iduna" vs.
"Signal Iduna Group AG"). Tests sichern die Normalisierungs-Regel ab.
"""
from services.email_import_utils import normalize_company


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
