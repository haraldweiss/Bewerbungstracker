"""Unit-Tests für Pattern-Lerner."""
import pytest
from services.job_sources.pattern_learner import (
    PATTERN_JSON_SCHEMA, validate_pattern_schema,
)


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
