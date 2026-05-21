# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for XING-style card schema (title in URL link, fields after URL).

XING-mails use `** [title-text](url) **` followed by company, location on
separate lines. This is structurally different from LinkedIn's
title-company-location-URL block. The pattern system supports both via
the new `title_in_url_link` and `fields_after_url` flags on body_card.
"""
import pytest
import re
import json
from services.job_sources.pattern_learner import (
    compile_pattern,
    normalize_pattern,
    validate_pattern_schema,
)


XING_SAMPLE_BODY = """\
2 neue Stellenangebote für "Ich bin auf der Suche nach..."

Hallo Harald,

# schau, was unsere KI-gestützte Suche für Dich gefunden hat.

[Zu den Ersten gehören](https://www.xing.com/m/UL_yMejjCghS_kvp8KHYAK)

** [IT-Security Consultant (m/w/d)](https://www.xing.com/m/UL_yMejjCghS_kvp8KHYAK)**
hyrUP GmbH
Dortmund
bevorzugtes Tätigkeitsfeld Karriere-Stufe Vollzeit 60.000 € - 85.000 €

[Zu den Ersten gehören](https://www.xing.com/m/UL_yMejjCghS_kvp8KHYAL)

** [OT-Security Specialist (gn)](https://www.xing.com/m/UL_yMejjCghS_kvp8KHYAL)**
Jungwild GmbH
Holzwickede
bevorzugtes Tätigkeitsfeld Karriere-Stufe Vollzeit 62.000 € - 85.000 €
"""

XING_URL_PATTERN = r"https?://(?:www\.)?xing\.com/(?:jobs|app/jobs|m)/[^\s)<>\"'\\]+"


def _xing_pattern_input():
    """A pattern dict in the new XING-style format."""
    return {
        "subject_pattern": {
            "prefix_optional": True,
            "prefix_keywords": ["Neue Stelle", "neue Stellenangebote"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": [],
            "fields_before_url": [],
            "fields_after_url": ["company", "location"],
            "title_in_url_link": True,
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": [],
            "company_blacklist_separators": [],
        },
    }


def test_normalize_accepts_new_fields():
    """normalize_pattern preserves title_in_url_link and fields_after_url."""
    raw = _xing_pattern_input()
    out = normalize_pattern(raw)
    assert out["body_card"]["title_in_url_link"] is True
    assert out["body_card"]["fields_after_url"] == ["company", "location"]


def test_normalize_defaults_for_missing_new_fields():
    """Patterns without the new fields get backward-compatible defaults."""
    raw = {
        "subject_pattern": {
            "prefix_optional": True,
            "prefix_keywords": [],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
            # no title_in_url_link, no fields_after_url
        },
        "filters": {
            "title_blacklist": [],
            "company_blacklist_separators": [],
        },
    }
    out = normalize_pattern(raw)
    assert out["body_card"]["title_in_url_link"] is False
    assert out["body_card"]["fields_after_url"] == []


def test_schema_accepts_new_fields():
    """validate_pattern_schema accepts patterns with the new fields."""
    errors = validate_pattern_schema(_xing_pattern_input())
    assert errors == [], f"Schema rejected XING-style pattern: {errors}"


def test_compile_pattern_xing_mode_matches_card():
    """compile_pattern in title_in_url_link mode matches a XING card and
    extracts title, company, location, url."""
    pattern = normalize_pattern(_xing_pattern_input())
    compiled = compile_pattern(pattern, url_pattern_str=XING_URL_PATTERN)
    matches = list(compiled.body_card_re.finditer(XING_SAMPLE_BODY))
    assert len(matches) >= 2, f"expected ≥2 XING cards, got {len(matches)}"
    first = matches[0]
    assert first.group("title").strip() == "IT-Security Consultant (m/w/d)"
    assert first.group("company").strip() == "hyrUP GmbH"
    assert first.group("location").strip() == "Dortmund"
    assert "xing.com/m/UL_yMejjCghS_kvp8KHYAK" in first.group("url")


def test_compile_pattern_linkedin_mode_unchanged():
    """LinkedIn-mode (title_in_url_link=false) still matches the legacy
    title-company-location-URL structure."""
    pattern = {
        "subject_pattern": {
            "prefix_optional": True,
            "prefix_keywords": [],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "fields_after_url": [],
            "title_in_url_link": False,
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": [],
            "company_blacklist_separators": [],
        },
    }
    linkedin_body = (
        "Senior Security Engineer\n"
        "TechCo GmbH\n"
        "Berlin\n"
        "\n"
        "Jobangebot ansehen: https://www.linkedin.com/jobs/view/12345\n"
    )
    compiled = compile_pattern(
        pattern,
        url_pattern_str=r"https?://(?:www\.)?linkedin\.com/jobs/view/\d+[^\s)<>\"'\\]*",
    )
    matches = list(compiled.body_card_re.finditer(linkedin_body))
    assert len(matches) == 1, f"LinkedIn card not matched in legacy mode: {len(matches)}"
    assert matches[0].group("title").strip() == "Senior Security Engineer"
    assert matches[0].group("company").strip() == "TechCo GmbH"


def test_compile_pattern_xing_without_url_pattern_uses_generic():
    """If no url_pattern_str is passed, falls back to a generic https URL match."""
    pattern = normalize_pattern(_xing_pattern_input())
    compiled = compile_pattern(pattern)
    matches = list(compiled.body_card_re.finditer(XING_SAMPLE_BODY))
    # Generic URL still matches the markdown link's URL.
    assert len(matches) >= 2, f"generic mode fails: {len(matches)}"


def test_example_output_documents_new_fields():
    """_EXAMPLE_OUTPUT should mention title_in_url_link and fields_after_url
    (as placeholder values) so the AI knows they exist."""
    from services.job_sources.pattern_learner import _EXAMPLE_OUTPUT
    bc = _EXAMPLE_OUTPUT["body_card"]
    assert "title_in_url_link" in bc
    assert "fields_after_url" in bc


def test_prompt_explains_new_fields():
    """_build_user_prompt should explain the new fields in the field-explanation
    section."""
    from services.job_sources.pattern_learner import _build_user_prompt
    prompt = _build_user_prompt(
        [{"subject": "x", "body": "y"}], platform="xing"
    )
    assert "title_in_url_link" in prompt
    assert "fields_after_url" in prompt
