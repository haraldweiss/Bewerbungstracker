"""Shared RSS-Parser-Logic für Job-Adapter."""
from __future__ import annotations
import logging
import requests
import feedparser
from datetime import datetime
from time import mktime

from services.job_sources.base import FetchedJob
from services.ssrf_guard import validate_rss_url

logger = logging.getLogger(__name__)


def fetch_rss_jobs(url: str, source_label: str = "rss") -> list[FetchedJob]:
    """Lädt + parst einen RSS-Feed zu FetchedJob[].

    SSRF-Guard erzwungen. Bei HTTP/Parse-Fehler: leere Liste.
    Identischer Output für RssAdapter und alle Hybrid-Adapter.
    """
    if not url:
        return []
    try:
        validate_rss_url(url)
    except Exception as e:
        logger.warning(f"{source_label} RSS SSRF-rejected: {e}")
        return []
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        parsed = feedparser.parse(r.text)
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"{source_label} RSS error: {e}")
        return []

    if parsed.bozo and not parsed.entries:
        logger.warning(f"{source_label} RSS parse failed: {parsed.bozo_exception}")
        return []

    jobs: list[FetchedJob] = []
    for e in parsed.entries:
        posted_at = None
        if hasattr(e, 'published_parsed') and e.published_parsed:
            posted_at = datetime.fromtimestamp(mktime(e.published_parsed))
        external_id = (
            getattr(e, 'id', None)
            or getattr(e, 'guid', None)
            or e.link
        )
        description = (
            getattr(e, 'description', None)
            or getattr(e, 'summary', None)
        )
        jobs.append(FetchedJob(
            external_id=str(external_id),
            title=getattr(e, 'title', ''),
            url=e.link,
            description=description,
            location=getattr(e, 'category', None),
            posted_at=posted_at,
            raw=dict(e),
        ))
    return jobs
