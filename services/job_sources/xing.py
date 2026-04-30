"""Xing Job-Source Adapter (RSS + JSearch Aggregator)."""
from __future__ import annotations
import logging
import requests
import feedparser
from datetime import datetime
from time import mktime

from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.dedup import get_existing_job_urls, deduplicate
from services.job_sources.jsearch_client import JSearchClient

logger = logging.getLogger(__name__)

PLATFORM = "xing"


class XingAdapter(JobSourceAdapter):
    """Hybrid: RSS-Feed + JSearch-Aggregator-API.

    Config-Schema:
        {
            "rss_url": "https://www.xing.com/jobs/feed/...",  # optional
            "aggregator_key": "RAPIDAPI_KEY",                 # optional
            "query": "python",                                # für aggregator
            "location": "Germany"                             # für aggregator
        }

    Beide Quellen sind optional — wenn keine konfiguriert ist, []-Result.
    """

    def fetch(self) -> list[FetchedJob]:
        rss_jobs = self._fetch_rss()
        agg_jobs = self._fetch_aggregator()
        combined = rss_jobs + agg_jobs

        existing = get_existing_job_urls()
        deduped = deduplicate(combined, existing)
        logger.info(
            f"Xing: rss={len(rss_jobs)} agg={len(agg_jobs)} "
            f"combined={len(combined)} after_dedup={len(deduped)}"
        )
        return deduped

    def _fetch_rss(self) -> list[FetchedJob]:
        url = self.config.get("rss_url")
        if not url:
            return []
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            parsed = feedparser.parse(r.text)
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Xing RSS error: {e}")
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
            jobs.append(FetchedJob(
                external_id=str(external_id),
                title=e.title,
                url=e.link,
                description=getattr(e, 'description', None),
                location=getattr(e, 'category', None),
                posted_at=posted_at,
                raw=dict(e),
            ))
        return jobs

    def _fetch_aggregator(self) -> list[FetchedJob]:
        key = self.config.get("aggregator_key")
        if not key:
            return []
        client = JSearchClient(api_key=key)
        return client.search(
            query=self.config.get("query", "python"),
            platform=PLATFORM,
            location=self.config.get("location", "Germany"),
        )
