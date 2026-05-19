# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""URL-Health-Check fuer Job-URLs.

Wird vom Cron-Endpoint /api/jobs/url-health-check taeglich aufgerufen.
Markiert RawJobs als 'marked_for_deletion' bei:
  - 404/410 (permanent weg) - sofort
  - 3x sukzessive Connection-Fails (timeout/5xx/connection_error) - Strike-Logik

State-Transitions in update_raw_job_health() - alle Mutationen passieren
dort, nicht im Caller (testbar in isolation).
"""
from __future__ import annotations
import logging
from datetime import datetime
from urllib.parse import urlparse

import requests

from services.ssrf_guard import is_url_safe_for_rss

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3  # 3 Strikes vor mark
HTTP_TIMEOUT_S = 5


def check_url(url: str, timeout: int = HTTP_TIMEOUT_S) -> tuple[str, int | None]:
    """HTTP HEAD mit Redirect-Follow. Returns (status_label, http_code).

    status_label in: 'ok' | '404' | '410' | '5xx' | 'timeout' |
                     'connection_error' | 'invalid_url'

    Tracker-URLs werden mit allow_redirects=True automatisch verfolgt
    - der finale HTTP-Code bestimmt das Ergebnis.
    """
    # Basic URL validation
    if not isinstance(url, str) or not url.strip():
        return "invalid_url", None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "invalid_url", None
    # SSRF-Guard: blockt private/lokale IPs
    if not is_url_safe_for_rss(url):
        return "invalid_url", None

    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "BewerbungstrackerHealthCheck/1.0"},
        )
    except requests.Timeout:
        return "timeout", None
    except requests.ConnectionError:
        return "connection_error", None
    except requests.RequestException:
        return "connection_error", None

    code = resp.status_code
    if 200 <= code < 400:
        return "ok", code
    if code == 404:
        return "404", code
    if code == 410:
        return "410", code
    if 500 <= code < 600:
        return "5xx", code
    # 4xx other than 404/410 - treat as connection_error (could be 403, 429)
    return "connection_error", code


def update_raw_job_health(raw_job, status_label: str, http_code: int | None) -> bool:
    """Apply state-transition rules to raw_job. Mutates in-place.

    Returns True if 'marked_for_deletion' was just triggered (caller can
    log/audit).
    """
    raw_job.url_check_status = status_label
    raw_job.url_last_checked_at = datetime.utcnow()

    if status_label == "ok":
        raw_job.url_check_failures = 0
        return False

    # Permanent-gone signals: mark sofort
    if status_label in ("404", "410"):
        raw_job.crawl_status = "marked_for_deletion"
        return True

    # Connection failures: increment counter
    raw_job.url_check_failures = (raw_job.url_check_failures or 0) + 1
    if raw_job.url_check_failures >= FAILURE_THRESHOLD:
        raw_job.crawl_status = "marked_for_deletion"
        return True

    return False
