"""Tests für services.job_sources.__init__.get_adapter mit _email-Typen."""
from unittest.mock import MagicMock
from services.job_sources import get_adapter, _VALID_TYPES
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES


def test_valid_types_contains_all_email_variants():
    assert "indeed_email" in _VALID_TYPES
    assert "linkedin_email" in _VALID_TYPES
    assert "xing_email" in _VALID_TYPES


def test_get_adapter_indeed_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "indeed_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["indeed"]


def test_get_adapter_linkedin_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "linkedin_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["linkedin"]


def test_get_adapter_xing_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "xing_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["xing"]
