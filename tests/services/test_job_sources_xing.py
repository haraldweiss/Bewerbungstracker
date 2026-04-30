"""Tests für XingAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import responses
from services.job_sources.xing import XingAdapter

FIX_RSS = Path(__file__).parent.parent / "fixtures" / "xing_rss.xml"
FIX_JSEARCH = Path(__file__).parent.parent / "fixtures" / "jsearch_xing_response.json"


@responses.activate
def test_xing_fetch_rss_only_no_aggregator():
    """Ohne aggregator_key: nur RSS, kein API-Call."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
        content_type="application/rss+xml",
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Senior Python Developer (m/w/d)" in titles
    assert "Backend Engineer Python" in titles


@responses.activate
def test_xing_fetch_combines_rss_and_aggregator():
    """RSS + JSearch parallel — kombiniert + dedupliziert."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX_JSEARCH.read_text()),
        status=200,
    )

    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
        "aggregator_key": "fake-key",
        "query": "python",
        "location": "Germany",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    # 2 from RSS + 2 from JSearch = 4 (no overlap in fixtures)
    assert len(jobs) == 4
    urls = {j.url for j in jobs}
    assert "https://www.xing.com/jobs/python-dev-berlin-100" in urls
    assert "https://www.xing.com/jobs/12345" in urls


@responses.activate
def test_xing_dedup_excludes_existing_urls():
    """URLs aus DB werden ausgefiltert."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
    })
    existing = {"https://www.xing.com/jobs/python-dev-berlin-100"}
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.xing.com/jobs/backend-eng-200"


@responses.activate
def test_xing_fetch_without_rss_url_uses_only_aggregator():
    """Ohne rss_url: nur Aggregator wird genutzt."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX_JSEARCH.read_text()),
        status=200,
    )
    adapter = XingAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    assert all("xing.com" in j.url for j in jobs)


def test_xing_no_config_returns_empty():
    """Weder rss_url noch aggregator_key: leeres Result."""
    adapter = XingAdapter(config={})
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []


@responses.activate
def test_xing_rss_http_error_falls_back_to_aggregator():
    """RSS schlägt fehl → aggregator liefert weiter, kein crash."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        status=500,
    )
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX_JSEARCH.read_text()),
        status=200,
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
        "aggregator_key": "fake-key",
        "query": "python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    # RSS = 0 (HTTP error), agg = 2 → 2 jobs
    assert len(jobs) == 2
    assert all("xing.com/jobs/" in j.url for j in jobs)


@responses.activate
def test_xing_aggregator_error_falls_back_to_rss():
    """JSearch-Fehler → RSS-Result allein."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json={"error": "rate limit"},
        status=429,
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
        "aggregator_key": "fake-key",
        "query": "python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert len(jobs) == 2  # RSS-only


@responses.activate
def test_xing_rss_invalid_url_blocked_by_ssrf():
    """SSRF-blocked URL → leeres RSS-Result, kein crash."""
    adapter = XingAdapter(config={
        "rss_url": "http://127.0.0.1:8080/internal",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
