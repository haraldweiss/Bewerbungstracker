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


from services.job_sources.pattern_learner import validate_pattern


def _sample_mails():
    body_match = (
        "Senior Engineer\r\nAcme GmbH\r\nBerlin\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/123"
    )
    body_nojob = "Random newsletter content with no job structure."
    return [
        {"subject": "Senior Engineer bei Acme GmbH", "body": body_match},
        {"subject": "DevOps bei Bcorp", "body": body_match.replace("Acme", "Bcorp")},
        {"subject": "Frontend bei Ccorp", "body": body_match.replace("Acme", "Ccorp")},
        {"subject": "Random Newsletter", "body": body_nojob},
    ]


def test_validate_counts_hits():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, _sample_mails())
    assert hit_rate == 0.75   # 3 of 4 match
    assert sum(1 for d in diags if d["matched"]) == 3


def test_validate_empty():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, [])
    assert hit_rate == 0.0 and diags == []


def test_validate_missing_body():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, _ = validate_pattern(cp, [
        {"subject": "Test", "body": None},
        {"subject": "Test", "body": ""},
    ])
    assert hit_rate == 0.0


def test_validate_respects_title_blacklist():
    """Card that matches body_card_re but title is on blacklist → not counted."""
    cp = compile_pattern(_valid_pattern_dict())
    bad_body = (
        "Ihre Jobbenachrichtigung fuer X\r\n"
        "SomeCompany\r\nBerlin\r\n"
        "Jobangebot ansehen: https://linkedin.com/comm/jobs/view/99"
    )
    hit_rate, diags = validate_pattern(cp, [{"subject": "Test", "body": bad_body}])
    assert hit_rate == 0.0
    assert diags[0]["matched"] is False


from unittest.mock import MagicMock, patch
from services.job_sources.pattern_learner import fetch_sample_mails


def test_fetch_delegates_to_adapter():
    user = MagicMock()
    user.imap_host = "imap.gmail.com"
    user.imap_user = "u@x.de"
    user.decrypted_imap_password = "pw"
    fake_mails = [{"subject": "X", "body": "Y"}] * 10
    with patch(
        "services.job_sources.email_jobs.EmailJobsAdapter._fetch_emails",
        return_value=fake_mails,
    ) as m:
        result = fetch_sample_mails(
            user, platform="linkedin",
            folder="INBOX", lookback_days=30, n=10,
        )
    assert result == fake_mails
    assert m.called


def test_fetch_unknown_platform_raises():
    user = MagicMock()
    with pytest.raises(ValueError, match="Unknown platform"):
        fetch_sample_mails(user, platform="myspace",
                           folder="INBOX", lookback_days=30, n=10)


def test_fetch_missing_credentials_raises():
    user = MagicMock()
    user.imap_host = None  # missing!
    user.imap_user = "u@x.de"
    user.decrypted_imap_password = "pw"
    with pytest.raises(RuntimeError, match="IMAP-Credentials"):
        fetch_sample_mails(user, platform="linkedin",
                           folder="INBOX", lookback_days=30, n=10)
