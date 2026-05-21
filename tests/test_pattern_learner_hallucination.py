# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hallucination filter: AI-generated url_labels that don't occur in sample
mails are removed before the pattern is persisted.

Background: Indeed-mails have no clear 'label-before-URL' card schema. Even
with placeholder-based prompts, the AI hallucinates plausible-sounding
phrases like 'Jobangebot ansehen' from its training data. These break the
body_card_re regex (which then matches nothing in real mails).
"""
import pytest
from unittest.mock import patch, MagicMock
from services.job_sources import pattern_learner as pl
from services import ai_provider_client as _aip_mod


def _samples_with_label(label_phrase: str, n: int = 5):
    """N mails whose body contains label_phrase before a job-URL."""
    return [
        {
            "subject": f"Test Job {i} bei TestCo",
            "body": f"Body text. {label_phrase}: https://example.com/job/{i}",
        }
        for i in range(n)
    ]


def _samples_without_label(n: int = 5):
    """N mails that don't contain ANY of the typical job-label phrases."""
    return [
        {
            "subject": f"Stellenangebot {i} bei TestCo",
            "body": f"Hier eine Stelle. Mehr Info: https://indeed.com/job/{i}",
        }
        for i in range(n)
    ]


def _mock_ai_returning(pattern_json: str):
    """Patch ai_provider_client to return the given JSON string."""
    fake_response = {"content": pattern_json}
    client = MagicMock()
    client.chat = MagicMock(return_value=fake_response)
    return client


def test_hallucinated_url_labels_removed(monkeypatch):
    """When AI returns labels that aren't in any sample, they get filtered out."""
    samples = _samples_without_label()
    # AI hallucinates two LinkedIn-style labels that don't appear in samples.
    ai_response = '''{
        "subject_pattern": {"prefix_optional": true, "prefix_keywords": [], "separator": "bei|at|@"},
        "body_card": {
            "url_labels": ["Jobangebot ansehen", "View job"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []}
    }'''
    # ai_learn_pattern does `from services import ai_provider_client as _aip`
    # inside the function — patch the source module so the local import sees it.
    monkeypatch.setattr(_aip_mod, "get_client", lambda: _mock_ai_returning(ai_response))

    # Use a placeholder user object with the minimum attrs ai_learn_pattern needs.
    user = MagicMock(id="test-user", ai_provider=None, ai_provider_model=None)
    result = pl.ai_learn_pattern(user, train_samples=samples, platform="indeed")

    assert result["body_card"]["url_labels"] == [], (
        f"Hallucinated labels not removed: {result['body_card']['url_labels']}"
    )


def test_real_url_labels_kept(monkeypatch):
    """When AI returns a label that DOES appear in samples, it's kept."""
    samples = _samples_with_label("Jobangebot ansehen")
    ai_response = '''{
        "subject_pattern": {"prefix_optional": true, "prefix_keywords": [], "separator": "bei|at|@"},
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []}
    }'''
    # ai_learn_pattern does `from services import ai_provider_client as _aip`
    # inside the function — patch the source module so the local import sees it.
    monkeypatch.setattr(_aip_mod, "get_client", lambda: _mock_ai_returning(ai_response))

    user = MagicMock(id="test-user", ai_provider=None, ai_provider_model=None)
    result = pl.ai_learn_pattern(user, train_samples=samples, platform="linkedin")

    assert "Jobangebot ansehen" in result["body_card"]["url_labels"]


def test_mixed_real_and_hallucinated(monkeypatch):
    """Real labels are kept, hallucinated ones removed (case-insensitive match)."""
    samples = _samples_with_label("View job")
    ai_response = '''{
        "subject_pattern": {"prefix_optional": true, "prefix_keywords": [], "separator": "bei|at|@"},
        "body_card": {
            "url_labels": ["Jobangebot ansehen", "view job", "Show position"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []}
    }'''
    # ai_learn_pattern does `from services import ai_provider_client as _aip`
    # inside the function — patch the source module so the local import sees it.
    monkeypatch.setattr(_aip_mod, "get_client", lambda: _mock_ai_returning(ai_response))

    user = MagicMock(id="test-user", ai_provider=None, ai_provider_model=None)
    result = pl.ai_learn_pattern(user, train_samples=samples, platform="indeed")

    labels = result["body_card"]["url_labels"]
    # "view job" matches case-insensitively against sample body "View job: ..."
    # "Jobangebot ansehen" doesn't appear → removed
    # "Show position" doesn't appear → removed
    assert "view job" in labels or "View job" in labels, f"Real label lost: {labels}"
    assert "Jobangebot ansehen" not in labels, f"Hallucinated label kept: {labels}"
    assert "Show position" not in labels, f"Hallucinated label kept: {labels}"
