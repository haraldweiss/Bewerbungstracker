"""Unit-Tests für PlatformProfile-Dataclass und PROFILES-Registry."""
import re
import pytest
from services.job_sources.email_jobs import PlatformProfile, PROFILES


def test_profile_indeed_exists():
    assert "indeed" in PROFILES
    p = PROFILES["indeed"]
    assert p.name == "indeed"
    assert p.source_label == "Indeed"
    assert p.from_filter.startswith("from:indeed")


def test_profile_linkedin_exists():
    assert "linkedin" in PROFILES
    p = PROFILES["linkedin"]
    assert p.name == "linkedin"
    assert p.source_label == "LinkedIn"
    assert "linkedin.com" in p.from_filter
    assert p.digest_threshold == 3


def test_profile_xing_exists():
    assert "xing" in PROFILES
    p = PROFILES["xing"]
    assert p.name == "xing"
    assert p.source_label == "XING"
    assert "xing.com" in p.from_filter


def test_profile_linkedin_url_pattern_matches_jobs_view():
    p = PROFILES["linkedin"]
    assert p.url_pattern.search("Schau dir https://www.linkedin.com/jobs/view/3812345678/ an")
    assert p.url_pattern.search("https://linkedin.com/comm/jobs/view/3812345678?refId=abc")


def test_profile_xing_url_pattern_matches_jobs():
    p = PROFILES["xing"]
    assert p.url_pattern.search("https://www.xing.com/jobs/python-dev-12345")
    assert p.url_pattern.search("https://xing.com/app/jobs/details/abc-123")


def test_profile_is_frozen():
    """Dataclass frozen=True — versehentliches Überschreiben unterbunden."""
    p = PROFILES["indeed"]
    with pytest.raises((AttributeError, TypeError)):
        p.name = "modified"
