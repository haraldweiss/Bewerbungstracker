"""Tests für JSearchClient (RapidAPI Aggregator)."""
import json
from pathlib import Path
import pytest
import responses
from services.job_sources.jsearch_client import JSearchClient

FIX = Path(__file__).parent.parent / "fixtures" / "jsearch_xing_response.json"


@responses.activate
def test_jsearch_returns_empty_without_api_key():
    """Ohne API-Key wird leeres Result zurückgegeben (kein Error)."""
    client = JSearchClient(api_key=None)
    jobs = client.search(query="python", platform="xing", location="Germany")
    assert jobs == []


@responses.activate
def test_jsearch_parses_response_to_fetched_jobs():
    """Mock-Response → korrekt geparste FetchedJob-Liste."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="python", platform="xing", location="Germany")

    assert len(jobs) == 2
    assert jobs[0].external_id == "xing-12345"
    assert jobs[0].title == "Senior Python Developer"
    assert jobs[0].company == "ACME GmbH"
    assert jobs[0].url == "https://www.xing.com/jobs/12345"
    assert jobs[0].location == "Berlin"
    assert jobs[0].posted_at is not None


@responses.activate
def test_jsearch_filters_by_publisher():
    """Nur Jobs mit publisher matching platform werden zurückgegeben."""
    mixed = {
        "data": [
            {"job_id": "1", "job_title": "T1", "job_apply_link": "u1",
             "job_publisher": "Xing", "employer_name": "A"},
            {"job_id": "2", "job_title": "T2", "job_apply_link": "u2",
             "job_publisher": "Indeed", "employer_name": "B"},
        ]
    }
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=mixed,
        status=200,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="x", platform="xing", location="DE")
    assert len(jobs) == 1
    assert jobs[0].external_id == "1"


@responses.activate
def test_jsearch_returns_empty_on_http_error():
    """Bei HTTP-Error: leere Liste, kein Crash (Resilienz)."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json={"error": "rate limit"},
        status=429,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="x", platform="xing", location="DE")
    assert jobs == []
