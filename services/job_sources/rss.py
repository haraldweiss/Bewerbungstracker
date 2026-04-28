"""RSS/Atom-Feed Adapter."""
import requests
import feedparser
from datetime import datetime
from time import mktime

from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.ssrf_guard import validate_rss_url


class RssAdapter(JobSourceAdapter):
    """Liest beliebige RSS/Atom-Feeds.

    Config-Schema:
        {"url": "https://example.com/feed.xml"}
    """

    def fetch(self) -> list[FetchedJob]:
        url = self.config.get("url")
        if not url:
            raise ValueError("RSS config requires 'url'")

        validate_rss_url(url)

        r = requests.get(url, timeout=15)
        r.raise_for_status()
        parsed = feedparser.parse(r.text)
        if parsed.bozo and parsed.entries == []:
            raise RuntimeError(f"RSS-Parse-Fehler: {parsed.bozo_exception}")

        jobs = []
        for e in parsed.entries:
            posted_at = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                posted_at = datetime.fromtimestamp(mktime(e.published_parsed))

            external_id = getattr(e, 'id', None) or getattr(e, 'guid', None) or e.link
            jobs.append(FetchedJob(
                external_id=str(external_id),
                title=e.title,
                url=e.link,
                description=getattr(e, 'description', None) or getattr(e, 'summary', None),
                location=getattr(e, 'category', None),
                posted_at=posted_at,
                raw=dict(e),
            ))
        return jobs
