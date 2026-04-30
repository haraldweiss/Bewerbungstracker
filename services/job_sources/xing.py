"""Xing Job-Source Adapter (RSS + JSearch Aggregator)."""
from __future__ import annotations
import logging

from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.dedup import get_existing_job_urls, deduplicate
from services.job_sources.jsearch_client import JSearchClient
from services.job_sources.rss_parser import fetch_rss_jobs

logger = logging.getLogger(__name__)

PLATFORM = "xing"


class XingAdapter(JobSourceAdapter):
    """Hybrid: RSS-Feed + JSearch-Aggregator-API.

    Config-Schema:
        {
            "rss_url": "https://www.xing.com/jobs/feed/...",  # optional
            "aggregator_key": "RAPIDAPI_KEY",                 # optional
            "query": "python",                                # für aggregator (required wenn aggregator_key gesetzt)
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
        return fetch_rss_jobs(self.config.get("rss_url"), source_label="Xing")

    def _fetch_aggregator(self) -> list[FetchedJob]:
        key = self.config.get("aggregator_key")
        query = self.config.get("query")
        if not key or not query:
            return []
        client = JSearchClient(api_key=key)
        return client.search(
            query=query,
            platform=PLATFORM,
            location=self.config.get("location", "Germany"),
        )
