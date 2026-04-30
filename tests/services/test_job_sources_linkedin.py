"""Tests für LinkedInAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import responses
from services.job_sources.linkedin import LinkedInAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "linkedin_jsearch_response.json"


@responses.activate
def test_linkedin_fetch_via_aggregator():
    """LinkedIn: aggregator-only flow."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = LinkedInAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
        "location": "Germany",
    })
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Staff Engineer" in titles
    assert "Engineering Manager" in titles
    assert all("linkedin.com" in j.url for j in jobs)


@responses.activate
def test_linkedin_dedup_excludes_existing_urls():
    """Existierende URLs werden ausgefiltert."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = LinkedInAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
    })
    existing = {"https://www.linkedin.com/jobs/view/aaa"}
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/bbb"


def test_linkedin_no_config_returns_empty():
    """Ohne aggregator_key und ohne rss_url: leer."""
    adapter = LinkedInAdapter(config={})
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []


@responses.activate
def test_linkedin_aggregator_error_returns_empty():
    """JSearch-Fehler → []."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json={"error": "rate limit"},
        status=429,
    )
    adapter = LinkedInAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
    })
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
