import pytest
from services.ssrf_guard import is_url_safe_for_rss, SSRFError, validate_rss_url


def test_blocks_localhost():
    assert is_url_safe_for_rss("http://localhost/feed") is False
    assert is_url_safe_for_rss("http://127.0.0.1/feed") is False

def test_blocks_private_ranges():
    assert is_url_safe_for_rss("http://192.168.1.1/feed") is False
    assert is_url_safe_for_rss("http://10.0.0.5/feed") is False
    assert is_url_safe_for_rss("http://169.254.169.254/feed") is False

def test_allows_public_url():
    assert is_url_safe_for_rss("https://example.com/feed.xml") is True
    assert is_url_safe_for_rss("https://www.stepstone.de/rss") is True

def test_blocks_invalid_url():
    assert is_url_safe_for_rss("not-a-url") is False
    assert is_url_safe_for_rss("file:///etc/passwd") is False
    assert is_url_safe_for_rss("ftp://example.com/feed") is False

def test_validate_raises_for_unsafe():
    with pytest.raises(SSRFError):
        validate_rss_url("http://localhost/x")
