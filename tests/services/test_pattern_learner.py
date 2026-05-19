"""Unit-Tests für Pattern-Lerner."""
import pytest
from services.job_sources.pattern_learner import (
    PATTERN_JSON_SCHEMA, validate_pattern_schema,
)
from services.job_sources.pattern_learner import compile_pattern, CompiledPattern


def test_valid_pattern_passes():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung"],
            "company_blacklist_separators": ["----"],
        },
    }
    assert validate_pattern_schema(p) == []


def test_invalid_pattern_missing_subject_pattern():
    p = {
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    errors = validate_pattern_schema(p)
    assert len(errors) >= 1
    assert any("subject_pattern" in e for e in errors)


def test_invalid_pattern_wrong_type():
    p = {
        "subject_pattern": {
            "prefix_optional": "not a bool",  # invalid
            "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1


def test_invalid_pattern_extra_field_rejected():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
            "evil_field": "drop table users",
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1


def _valid_pattern_dict():
    return {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle", "Job alert"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen", "View job"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung", "Top-Jobs"],
            "company_blacklist_separators": ["----", "===="],
        },
    }


def test_compile_returns_compiled_pattern():
    cp = compile_pattern(_valid_pattern_dict())
    assert isinstance(cp, CompiledPattern)
    assert cp.body_card_re is not None
    assert cp.subject_re is not None
    assert cp.title_blacklist_re is not None


def test_compile_body_card_matches_linkedin_layout():
    cp = compile_pattern(_valid_pattern_dict())
    body = (
        "Senior Cybersecurity Consultant (m,w,d)\r\n"
        "QESTIT DACH\r\n"
        "Deutschland\r\n"
        "Mit Lebenslauf und Profil bewerben\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/4410189303/"
    )
    matches = list(cp.body_card_re.finditer(body))
    assert len(matches) >= 1
    m = matches[0]
    assert "Senior Cybersecurity Consultant" in m.group('title')
    assert "QESTIT DACH" in m.group('company')
    assert "Deutschland" in m.group('location')
    assert "linkedin.com/comm/jobs/view/4410189303" in m.group('url')


def test_compile_subject_optional_prefix():
    cp = compile_pattern(_valid_pattern_dict())
    m = cp.subject_re.match("Senior Engineer bei Acme GmbH")
    assert m and m.group('title') == "Senior Engineer" and m.group('company') == "Acme GmbH"
    m = cp.subject_re.match("Neue Stelle: Junior Dev bei Bcorp")
    assert m


def test_compile_title_blacklist():
    cp = compile_pattern(_valid_pattern_dict())
    assert cp.title_blacklist_re.search("Ihre Jobbenachrichtigung")
    assert cp.title_blacklist_re.search("Top-Jobs für Sie")
    assert not cp.title_blacklist_re.search("Senior Engineer")
