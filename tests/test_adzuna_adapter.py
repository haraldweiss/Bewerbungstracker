# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the resilient Adzuna adapter.

Background: Adzuna's API returns 5xx for results_per_page=50 on some
queries, intermittently 5xx on others, and is sometimes slow (>15s).
The adapter must clamp page size, retry on 5xx, and skip empty params.
"""
import json
import pytest
import requests
from unittest.mock import patch, MagicMock, call


from services.job_sources.adzuna import AdzunaAdapter


def _ok_response(jobs=None):
    """A mock requests.Response that looks OK with the given jobs."""
    m = MagicMock(spec=requests.Response)
    m.status_code = 200
    m.json.return_value = {"results": jobs or []}
    m.raise_for_status.return_value = None
    return m


def _err_response(status=500):
    """A mock requests.Response that simulates an HTTP error."""
    m = MagicMock(spec=requests.Response)
    m.status_code = status
    err = requests.HTTPError(f"{status} Server Error")
    err.response = m
    m.raise_for_status.side_effect = err
    return m


BASE_CONFIG = {
    "app_id": "test-id",
    "app_key": "test-key",
    "country": "de",
    "what": "python",
    "where": "Berlin",
}


def test_default_results_per_page_is_20():
    """Adapter sends results_per_page=20 by default (not 50)."""
    cfg = {**BASE_CONFIG}  # no results_per_page set
    cfg.pop("what", None)
    cfg["what"] = "python"
    adapter = AdzunaAdapter(cfg)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response()
        adapter.fetch()
    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["results_per_page"] == 20


def test_results_per_page_clamped_at_30():
    """Config requesting >30 results gets clamped to 30 (Adzuna 5xx threshold)."""
    cfg = {**BASE_CONFIG, "results_per_page": 50}
    adapter = AdzunaAdapter(cfg)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response()
        adapter.fetch()
    assert mock_get.call_args.kwargs["params"]["results_per_page"] == 30


def test_empty_what_is_omitted():
    """Empty/missing `what` is not sent as `what=` (Adzuna prefers it absent)."""
    cfg = {**BASE_CONFIG, "what": ""}
    adapter = AdzunaAdapter(cfg)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response()
        adapter.fetch()
    sent_params = mock_get.call_args.kwargs["params"]
    assert "what" not in sent_params


def test_empty_where_is_omitted():
    """Empty/missing `where` is not sent (was a source of 500s)."""
    cfg = {**BASE_CONFIG, "where": ""}
    adapter = AdzunaAdapter(cfg)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response()
        adapter.fetch()
    sent_params = mock_get.call_args.kwargs["params"]
    assert "where" not in sent_params


def test_timeout_is_30s():
    """Adapter uses 30s timeout (Adzuna can be slow)."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response()
        adapter.fetch()
    assert mock_get.call_args.kwargs["timeout"] == 30


def test_retries_on_500_then_succeeds():
    """First 500 triggers retry; second attempt returns 200."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get, \
         patch("services.job_sources.adzuna.time.sleep") as mock_sleep:
        mock_get.side_effect = [_err_response(500), _ok_response()]
        jobs = adapter.fetch()
    assert jobs == []
    assert mock_get.call_count == 2
    # 1 retry => 1 sleep call (we don't sleep before the first attempt)
    assert mock_sleep.call_count == 1


def test_retries_on_timeout_then_succeeds():
    """ReadTimeout triggers retry."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get, \
         patch("services.job_sources.adzuna.time.sleep"):
        mock_get.side_effect = [requests.Timeout("timed out"), _ok_response()]
        jobs = adapter.fetch()
    assert mock_get.call_count == 2


def test_retries_3_times_total_then_raises():
    """After 3 failed attempts the adapter raises HTTPError (preserving
    behavior for upstream error-handling/last_error storage)."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get, \
         patch("services.job_sources.adzuna.time.sleep"):
        mock_get.side_effect = [_err_response(503)] * 3
        with pytest.raises(requests.HTTPError):
            adapter.fetch()
    assert mock_get.call_count == 3


def test_4xx_not_retried():
    """4xx errors (auth, bad request) raise immediately without retry."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get, \
         patch("services.job_sources.adzuna.time.sleep") as mock_sleep:
        mock_get.return_value = _err_response(401)
        with pytest.raises(requests.HTTPError):
            adapter.fetch()
    assert mock_get.call_count == 1
    assert mock_sleep.call_count == 0


def test_backoff_intervals():
    """Sleep durations between retries are [2s, 5s]."""
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get, \
         patch("services.job_sources.adzuna.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _err_response(500),
            _err_response(500),
            _ok_response(),
        ]
        adapter.fetch()
    # Two retries, two sleep calls.
    sleeps = [c.args[0] for c in mock_sleep.call_args_list]
    assert sleeps == [2, 5]


def test_existing_config_still_validated():
    """Missing app_id/app_key/country still raises ValueError (no regression)."""
    with pytest.raises(ValueError):
        AdzunaAdapter({}).fetch()
    with pytest.raises(ValueError):
        AdzunaAdapter({"app_id": "x"}).fetch()


def test_job_parsing_unchanged():
    """The fetched-job structure is unchanged (regression for upstream code)."""
    job_data = {
        "id": 12345,
        "title": "Python Dev",
        "redirect_url": "https://example.com/job/12345",
        "company": {"display_name": "TestCo"},
        "location": {"display_name": "Berlin"},
        "description": "A test job",
        "created": "2026-05-20T10:00:00Z",
    }
    adapter = AdzunaAdapter(BASE_CONFIG)
    with patch("services.job_sources.adzuna.requests.get") as mock_get:
        mock_get.return_value = _ok_response([job_data])
        jobs = adapter.fetch()
    assert len(jobs) == 1
    j = jobs[0]
    assert j.external_id == "12345"
    assert j.title == "Python Dev"
    assert j.url == "https://example.com/job/12345"
    assert j.company == "TestCo"
    assert j.location == "Berlin"
