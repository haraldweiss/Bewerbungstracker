"""Tests für den in-memory KeyCache (DEK-Storage mit TTL)."""

import time
import pytest

from services.key_cache import KeyCache


def test_put_and_get():
    cache = KeyCache(ttl_seconds=60)
    cache.put("user-1", b"secret-dek")
    assert cache.get("user-1") == b"secret-dek"


def test_get_missing_returns_none():
    cache = KeyCache(ttl_seconds=60)
    assert cache.get("nope") is None


def test_evict_removes_entry():
    cache = KeyCache(ttl_seconds=60)
    cache.put("u", b"k")
    cache.evict("u")
    assert cache.get("u") is None


def test_clear_removes_all():
    cache = KeyCache(ttl_seconds=60)
    cache.put("a", b"1")
    cache.put("b", b"2")
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_ttl_expiry():
    cache = KeyCache(ttl_seconds=1)
    cache.put("u", b"k")
    time.sleep(1.1)
    # Erwartung: Eintrag abgelaufen, get gibt None zurück und löscht intern
    assert cache.get("u") is None


def test_cleanup_expired_returns_count():
    cache = KeyCache(ttl_seconds=1)
    cache.put("a", b"1")
    cache.put("b", b"2")
    time.sleep(1.1)
    cache.put("c", b"3")  # frisch
    removed = cache.cleanup_expired()
    assert removed == 2
    assert cache.get("c") == b"3"


def test_thread_safe_concurrent_writes():
    """Smoke-Test: viele gleichzeitige Schreibzugriffe lassen den Cache intakt."""
    import threading

    cache = KeyCache(ttl_seconds=60)

    def writer(i):
        for j in range(50):
            cache.put(f"user-{i}-{j}", bytes([i, j]))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Stichprobe: einige der eingetragenen Keys sind lesbar
    assert cache.get("user-0-0") == bytes([0, 0])
    assert cache.get("user-9-49") == bytes([9, 49])
