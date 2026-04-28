"""Arbeitnow-API (kostenlos, keine Auth)."""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class ArbeitnowAdapter(JobSourceAdapter):
    URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self) -> list[FetchedJob]:
        r = requests.get(self.URL, timeout=15)
        r.raise_for_status()
        data = r.json()

        wanted_tags = set(t.lower() for t in self.config.get("tags") or [])
        require_visa = self.config.get("visa_sponsorship") is True

        jobs = []
        for item in data.get("data", []):
            tags = set(t.lower() for t in item.get("tags") or [])
            if wanted_tags and not (wanted_tags & tags):
                continue
            if require_visa and not item.get("visa_sponsorship"):
                continue

            posted = None
            if item.get("created_at"):
                try:
                    posted = datetime.fromtimestamp(int(item["created_at"]))
                except Exception:
                    pass

            jobs.append(FetchedJob(
                external_id=item.get("slug"),
                title=item.get("title", ""),
                url=item.get("url", ""),
                company=item.get("company_name"),
                location=item.get("location"),
                description=item.get("description"),
                posted_at=posted,
                raw=item,
            ))
        return jobs
