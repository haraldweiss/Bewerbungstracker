"""Tests für StepstoneAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import responses
from services.job_sources.stepstone import StepstoneAdapter

FIX_RSS = Path(__file__).parent.parent / "fixtures" / "stepstone_rss.xml"


@responses.activate
def test_stepstone_fetch_rss():
    """RSS-only-flow für Stepstone."""
    responses.add(
        responses.GET,
        "https://www.stepstone.de/jobs.rss?q=python",
        body=FIX_RSS.read_text(),
        status=200,
        content_type="application/rss+xml",
    )
    adapter = StepstoneAdapter(config={
        "rss_url": "https://www.stepstone.de/jobs.rss?q=python",
    })
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Fullstack Entwickler (m/w/d)" in titles
    assert "DevOps Engineer" in titles


@responses.activate
def test_stepstone_dedup_excludes_existing_urls():
    """Bekannte URLs werden gefiltert."""
    responses.add(
        responses.GET,
        "https://www.stepstone.de/jobs.rss?q=python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    adapter = StepstoneAdapter(config={
        "rss_url": "https://www.stepstone.de/jobs.rss?q=python",
    })
    existing = {"https://www.stepstone.de/stellenangebote/fullstack-1234"}
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.stepstone.de/stellenangebote/devops-5678"


def test_stepstone_no_config_returns_empty():
    """Ohne config: leer."""
    adapter = StepstoneAdapter(config={})
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []


@responses.activate
def test_stepstone_rss_http_error_returns_empty():
    """RSS HTTP-Fehler → []."""
    responses.add(
        responses.GET,
        "https://www.stepstone.de/jobs.rss?q=python",
        status=500,
    )
    adapter = StepstoneAdapter(config={
        "rss_url": "https://www.stepstone.de/jobs.rss?q=python",
    })
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
