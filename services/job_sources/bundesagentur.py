"""Bundesagentur Jobsuche-API (offiziell, kostenlos).

Doku: https://jobsuche.api.bund.dev/
"""
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob


class BundesagenturAdapter(JobSourceAdapter):
    """Config:
        {"was":"Frontend","wo":"10115","umkreis":25,"arbeitszeit":"vollzeit"}
    """
    URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
    HEADERS = {"X-API-Key": "jobboerse-jobsuche"}

    def fetch(self) -> list[FetchedJob]:
        params = {
            "was": self.config.get("was", ""),
            "wo": self.config.get("wo", ""),
            "umkreis": self.config.get("umkreis", 25),
            "size": 50,
        }
        if self.config.get("arbeitszeit"):
            params["arbeitszeit"] = self.config["arbeitszeit"]

        r = requests.get(self.URL, params=params, headers=self.HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        jobs = []
        for item in data.get("stellenangebote", []):
            posted = None
            if item.get("aktuelleVeroeffentlichungsdatum"):
                try:
                    posted = datetime.fromisoformat(item["aktuelleVeroeffentlichungsdatum"])
                except Exception:
                    pass

            ort = item.get("arbeitsort") or {}
            location = ", ".join(filter(None, [
                ort.get("plz"), ort.get("ort"), ort.get("region")
            ]))

            external_url = item.get("externeUrl") or \
                f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{item['refnr']}"

            jobs.append(FetchedJob(
                external_id=item["refnr"],
                title=item.get("titel") or item.get("beruf", ""),
                url=external_url,
                company=item.get("arbeitgeber"),
                location=location,
                description=None,
                posted_at=posted,
                raw=item,
            ))
        return jobs
