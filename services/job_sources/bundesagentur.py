"""Bundesagentur Jobsuche-API (offiziell, kostenlos).

Doku: https://jobsuche.api.bund.dev/

## Detail-Fetch-Strategie

Das Listing-Endpoint `/v4/jobs` liefert NUR Header-Metadaten (titel, beruf,
arbeitsort, refnr) — KEINE Beschreibung. Der Pre-Filter wäre ohne Description
quasi blind (nur Titel-Match).

Lösung: Detail-Endpoint `/v4/jobdetails/<base64-refnr>` pro Job nachladen.
Bei 50 Jobs sequenziell ~50s — sprengt das Cron-Tick-Time-Budget. Daher
**parallel via ThreadPoolExecutor** (10 concurrent), bringt Total auf ~5s.

Bei timeout/Fehler einzelner Detail-Calls: Job wird trotzdem mit
`description=None` zurückgegeben, fällt durch Pre-Filter — kein Hard-Fail.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from services.job_sources.base import JobSourceAdapter, FetchedJob


URL_LISTING = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
URL_DETAILS = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}


def _fetch_detail(refnr: str, session: requests.Session) -> dict | None:
    """Holt das Detail-Dokument für eine refnr. Returns None bei Fehler."""
    try:
        encoded = base64.b64encode(refnr.encode("utf-8")).decode("ascii")
        r = session.get(f"{URL_DETAILS}/{encoded}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _employment_tags(detail: dict) -> list[str]:
    """Extrahiert die Anstellungs-Eigenschaften aus den arbeitszeit*-Flags
    + vertragsdauer für den Pre-Filter / Frontend-Anzeige.
    """
    tags = []
    if detail.get("arbeitszeitVollzeit"):
        tags.append("vollzeit")
    if any(detail.get(k) for k in (
        "arbeitszeitTeilzeitVormittag", "arbeitszeitTeilzeitNachmittag",
        "arbeitszeitTeilzeitFlexibel", "arbeitszeitTeilzeitAbend",
    )):
        tags.append("teilzeit")
    if detail.get("arbeitszeitSchichtNachtWochenende"):
        tags.append("schicht")
    if detail.get("istGeringfuegigeBeschaeftigung"):
        tags.append("minijob")

    vd = (detail.get("vertragsdauer") or "").upper()
    if vd == "UNBEFRISTET":
        tags.append("unbefristet")
    elif vd == "BEFRISTET":
        tags.append("befristet")
    return tags


def _location_from_detail(detail: dict, fallback_listing: dict) -> str:
    """Bei mehreren Standorten alle joinen — wichtig fürs Region-Matching
    (Pre-Filter sucht nach PLZ-Präfixen im Location-String).
    """
    locs = detail.get("stellenlokationen") or []
    if locs:
        parts = []
        for loc in locs:
            adr = loc.get("adresse") or {}
            piece = ", ".join(filter(None, [adr.get("plz"), adr.get("ort"), adr.get("region")]))
            if piece:
                parts.append(piece)
        if parts:
            return " | ".join(parts)
    # Fallback: arbeitsort aus Listing
    ort = fallback_listing.get("arbeitsort") or {}
    return ", ".join(filter(None, [ort.get("plz"), ort.get("ort"), ort.get("region")]))


class BundesagenturAdapter(JobSourceAdapter):
    """Config:
        {"was":"Frontend","wo":"10115","umkreis":25,"arbeitszeit":"vollzeit"}

    Optional:
        {"max_details": 30}  — wenn Detail-Fetch zu langsam, weniger Jobs
                              voll-anreichern (Default: alle bis Listing-Limit).
    """
    URL = URL_LISTING
    HEADERS = HEADERS
    DETAIL_PARALLELISM = 10
    DEFAULT_MAX_DETAILS = 50

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
        listing = r.json().get("stellenangebote", [])

        max_details = int(self.config.get("max_details", self.DEFAULT_MAX_DETAILS))
        listing_to_enrich = listing[:max_details]

        # Parallele Detail-Fetches via Threading. requests.Session reuses
        # die TCP-Verbindung über Calls hinweg — nochmal ~30% Speed-Up.
        details_by_refnr = {}
        if listing_to_enrich:
            with requests.Session() as session, \
                 ThreadPoolExecutor(max_workers=self.DETAIL_PARALLELISM) as executor:
                future_to_ref = {
                    executor.submit(_fetch_detail, item["refnr"], session): item["refnr"]
                    for item in listing_to_enrich
                }
                for future in as_completed(future_to_ref):
                    refnr = future_to_ref[future]
                    detail = future.result()
                    if detail:
                        details_by_refnr[refnr] = detail

        jobs = []
        for item in listing_to_enrich:
            refnr = item["refnr"]
            detail = details_by_refnr.get(refnr)

            posted = None
            date_str = item.get("aktuelleVeroeffentlichungsdatum")
            if date_str:
                try:
                    posted = datetime.fromisoformat(date_str)
                except Exception:
                    pass

            external_url = item.get("externeUrl") or \
                f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"

            if detail:
                title = (
                    detail.get("stellenangebotsTitel")
                    or item.get("titel")
                    or item.get("beruf", "")
                )
                description = detail.get("stellenangebotsBeschreibung")
                location = _location_from_detail(detail, item)
                # Anstellungsart-Tags ans Ende der Description hängen, damit
                # der Pre-Filter sie als Tokens findet ("vollzeit", "remote"
                # etc.) und Claude sie im Prompt sieht.
                tags = _employment_tags(detail)
                if tags:
                    description = (description or "") + "\n\n[Anstellungsart: " + ", ".join(tags) + "]"
                raw = {**item, "_detail": detail}
            else:
                title = item.get("titel") or item.get("beruf", "")
                description = None
                ort = item.get("arbeitsort") or {}
                location = ", ".join(filter(None, [ort.get("plz"), ort.get("ort"), ort.get("region")]))
                raw = item

            jobs.append(FetchedJob(
                external_id=refnr,
                title=title,
                url=external_url,
                company=item.get("arbeitgeber"),
                location=location,
                description=description,
                posted_at=posted,
                raw=raw,
            ))
        return jobs
