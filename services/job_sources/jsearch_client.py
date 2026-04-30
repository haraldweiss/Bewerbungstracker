"""JSearch (RapidAPI) Client für Multi-Source Job Aggregation.

Free-Tier: 2500 Requests/Monat.
Doc: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
from __future__ import annotations
import logging
from datetime import datetime
import requests

from services.job_sources.base import FetchedJob

logger = logging.getLogger(__name__)

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"


class JSearchClient:
    """Wrapper für JSearch RapidAPI Endpoint.

    Ohne api_key: alle search()-Aufrufe liefern []. Damit Adapter
    ohne API-Konfiguration nicht failen.
    """

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def search(
        self,
        query: str,
        platform: str,
        location: str = "Germany",
    ) -> list[FetchedJob]:
        """Sucht auf JSearch nach Jobs, filtert per Publisher = platform.

        platform: "xing" | "linkedin" | "stepstone" — wird gegen
        job_publisher (case-insensitive) geprüft.
        """
        if not self.api_key:
            logger.info(f"JSearch: kein API-Key, skipping platform={platform}")
            return []

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": JSEARCH_HOST,
        }
        params = {
            "query": f"{query} {location}",
            "page": "1",
            "num_pages": "1",
        }

        try:
            r = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"JSearch error platform={platform}: {e}")
            return []

        platform_lower = platform.lower()
        jobs: list[FetchedJob] = []
        for item in data.get("data", []):
            publisher = (item.get("job_publisher") or "").lower()
            if platform_lower not in publisher:
                continue

            job_id = item.get("job_id")
            if not job_id:
                logger.warning(
                    f"JSearch: skipping item without job_id: {item.get('job_title', '?')}"
                )
                continue

            posted_at = None
            ts = item.get("job_posted_at_timestamp")
            if ts:
                try:
                    # JSearch liefert Unix-Epoch (UTC). Wir matchen das
                    # naive-UTC Pattern aus arbeitnow.py für Konsistenz.
                    posted_at = datetime.fromtimestamp(int(ts))
                except (ValueError, TypeError):
                    pass

            location_str = item.get("job_city") or item.get("job_country") or None

            jobs.append(FetchedJob(
                external_id=str(job_id),
                title=item.get("job_title", ""),
                url=item.get("job_apply_link", ""),
                company=item.get("employer_name"),
                location=location_str,
                description=item.get("job_description"),
                posted_at=posted_at,
                raw=item,
            ))
        return jobs
