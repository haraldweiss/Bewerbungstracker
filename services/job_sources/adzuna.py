"""Adzuna-API-Adapter (https://developer.adzuna.com)."""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class AdzunaAdapter(JobSourceAdapter):
    """Config:
        {"app_id":"...","app_key":"...","country":"de",
         "what":"frontend","where":"Berlin","results_per_page":50}
    """
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def fetch(self) -> list[FetchedJob]:
        c = self.config
        if not (c.get("app_id") and c.get("app_key") and c.get("country")):
            raise ValueError("Adzuna config requires app_id, app_key, country")

        url = f"{self.BASE_URL}/{c['country']}/search/1"
        params = {
            "app_id": c["app_id"],
            "app_key": c["app_key"],
            "results_per_page": c.get("results_per_page", 50),
            "what": c.get("what", ""),
            "where": c.get("where", ""),
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs = []
        for item in data.get("results", []):
            posted = None
            if item.get("created"):
                try:
                    posted = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
                except Exception:
                    pass

            jobs.append(FetchedJob(
                external_id=str(item["id"]),
                title=item.get("title", ""),
                url=item.get("redirect_url", ""),
                company=(item.get("company") or {}).get("display_name"),
                location=(item.get("location") or {}).get("display_name"),
                description=item.get("description"),
                posted_at=posted,
                raw=item,
            ))
        return jobs
