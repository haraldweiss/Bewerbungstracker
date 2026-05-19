"""Unit-Tests fuer URL-Health-Check-Service."""
from unittest.mock import patch, MagicMock
import pytest


def test_check_url_returns_ok_for_2xx():
    from services.url_health_check import check_url
    fake_resp = MagicMock(status_code=200, is_redirect=False)
    with patch("requests.head", return_value=fake_resp) as m:
        status, code = check_url("https://example.com/job/1")
    assert status == "ok"
    assert code == 200
    m.assert_called_once()


def test_check_url_returns_ok_for_3xx_after_follow():
    from services.url_health_check import check_url
    # requests with allow_redirects=True returns the FINAL response after the chain
    fake_resp = MagicMock(status_code=200)
    with patch("requests.head", return_value=fake_resp):
        status, code = check_url("https://example.com/redirect")
    assert status == "ok"


def test_check_url_returns_404():
    from services.url_health_check import check_url
    fake_resp = MagicMock(status_code=404)
    with patch("requests.head", return_value=fake_resp):
        status, code = check_url("https://example.com/gone")
    assert status == "404"
    assert code == 404


def test_check_url_returns_410():
    from services.url_health_check import check_url
    fake_resp = MagicMock(status_code=410)
    with patch("requests.head", return_value=fake_resp):
        status, code = check_url("https://example.com/gone")
    assert status == "410"


def test_check_url_returns_5xx():
    from services.url_health_check import check_url
    fake_resp = MagicMock(status_code=503)
    with patch("requests.head", return_value=fake_resp):
        status, code = check_url("https://example.com/server-down")
    assert status == "5xx"
    assert code == 503


def test_check_url_returns_timeout():
    import requests
    from services.url_health_check import check_url
    with patch("services.url_health_check.is_url_safe_for_rss", return_value=True), \
         patch("requests.head", side_effect=requests.Timeout()):
        status, code = check_url("https://slow.example.com/")
    assert status == "timeout"
    assert code is None


def test_check_url_returns_connection_error():
    import requests
    from services.url_health_check import check_url
    with patch("services.url_health_check.is_url_safe_for_rss", return_value=True), \
         patch("requests.head", side_effect=requests.ConnectionError()):
        status, code = check_url("https://nodns.example.com/")
    assert status == "connection_error"


def test_check_url_returns_invalid_url():
    from services.url_health_check import check_url
    status, code = check_url("not a url")
    assert status == "invalid_url"
    assert code is None


def test_check_url_rejects_ssrf_unsafe_url():
    """SSRF-Guard greift: localhost-URL wird rejected."""
    from services.url_health_check import check_url
    status, code = check_url("http://127.0.0.1/admin")
    assert status == "invalid_url"


# -- update_raw_job_health --------------------------------------------------

def _make_raw_job(failures=0, status='active'):
    """Minimal RawJob-like Mock."""
    rj = MagicMock()
    rj.url_check_failures = failures
    rj.crawl_status = status
    rj.url_check_status = None
    rj.url_last_checked_at = None
    return rj


def test_update_health_ok_resets_failure_counter():
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=2)
    marked = update_raw_job_health(rj, "ok", 200)
    assert marked is False
    assert rj.url_check_failures == 0
    assert rj.url_check_status == "ok"
    assert rj.url_last_checked_at is not None
    assert rj.crawl_status == "active"   # unchanged


def test_update_health_404_marks_immediately():
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=0)
    marked = update_raw_job_health(rj, "404", 404)
    assert marked is True
    assert rj.crawl_status == "marked_for_deletion"
    assert rj.url_check_status == "404"


def test_update_health_410_marks_immediately():
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=0)
    marked = update_raw_job_health(rj, "410", 410)
    assert marked is True
    assert rj.crawl_status == "marked_for_deletion"


def test_update_health_timeout_increments_failures_no_mark():
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=0)
    marked = update_raw_job_health(rj, "timeout", None)
    assert marked is False
    assert rj.url_check_failures == 1
    assert rj.crawl_status == "active"


def test_update_health_third_failure_marks():
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=2)
    marked = update_raw_job_health(rj, "5xx", 503)
    assert marked is True
    assert rj.url_check_failures == 3
    assert rj.crawl_status == "marked_for_deletion"


def test_update_health_ok_after_failures_resets_and_does_not_mark():
    """Counter reset bei Erfolg - kein 'erinnerter' Strike."""
    from services.url_health_check import update_raw_job_health
    rj = _make_raw_job(failures=2)
    marked = update_raw_job_health(rj, "ok", 200)
    assert marked is False
    assert rj.url_check_failures == 0
    assert rj.crawl_status == "active"
