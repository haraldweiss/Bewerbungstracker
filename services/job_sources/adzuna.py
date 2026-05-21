# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Adzuna-API-Adapter (https://developer.adzuna.com).

Resilient gegen Adzuna-Flakeyness:
- results_per_page=50 löst bei manchen Queries HTTP 500 aus (interne
  Adzuna-Timeouts) — wir clampen auf 30.
- Empty `what`/`where` als Query-Param sind auch eine Quelle für 500er
  — bei Leer-Werten Param weglassen.
- 5xx und Timeouts sind transient → 3 Versuche mit Backoff [0,2,5]s.
- Timeout 30s (Adzuna braucht bei manchen Queries 20+s auch im Erfolgsfall).
"""
import logging
import time
import requests
from datetime import datetime

from services.job_sources.base import JobSourceAdapter, FetchedJob

logger = logging.getLogger(__name__)

# Hard caps für Adzuna's bekannte Probleme. Siehe Memory:
# incident_adzuna_500_on_large_pagesize_2026_05_21.
_MAX_RESULTS_PER_PAGE = 30
_DEFAULT_RESULTS_PER_PAGE = 20
_REQUEST_TIMEOUT_SECONDS = 30
_RETRY_BACKOFF_SECONDS = [2, 5]  # 3 Versuche total: 1×sofort + 2 retries


class AdzunaAdapter(JobSourceAdapter):
    """Config:
        {"app_id":"...","app_key":"...","country":"de",
         "what":"frontend","where":"Berlin","results_per_page":20}

    `what` und `where` sind optional — leer/fehlend = nicht senden.
    `results_per_page` Default 20, hartes Max 30 (höher → Adzuna 5xx).
    """
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def fetch(self) -> list[FetchedJob]:
        c = self.config
        if not (c.get("app_id") and c.get("app_key") and c.get("country")):
            raise ValueError("Adzuna config requires app_id, app_key, country")

        rpp = int(c.get("results_per_page", _DEFAULT_RESULTS_PER_PAGE))
        if rpp > _MAX_RESULTS_PER_PAGE:
            logger.warning(
                "Adzuna: results_per_page=%d -> clamped to %d (höhere Werte "
                "lösen häufig HTTP 500 aus).", rpp, _MAX_RESULTS_PER_PAGE,
            )
            rpp = _MAX_RESULTS_PER_PAGE

        url = f"{self.BASE_URL}/{c['country']}/search/1"
        params = {
            "app_id": c["app_id"],
            "app_key": c["app_key"],
            "results_per_page": rpp,
        }
        what = c.get("what") or ""
        where = c.get("where") or ""
        if what:
            params["what"] = what
        if where:
            params["where"] = where

        r = self._get_with_retry(url, params)
        data = r.json()

        jobs = []
        for item in data.get("results", []):
            posted = None
            if item.get("created"):
                try:
                    posted = datetime.fromisoformat(
                        item["created"].replace("Z", "+00:00")
                    )
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

    def _get_with_retry(self, url, params) -> requests.Response:
        last_exc = None
        # 3 Versuche total: ohne Sleep, dann 2s, dann 5s
        for attempt, sleep_before in enumerate([0] + _RETRY_BACKOFF_SECONDS, start=1):
            if sleep_before:
                time.sleep(sleep_before)
            try:
                r = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            except requests.Timeout as exc:
                last_exc = exc
                logger.warning("Adzuna Timeout (Versuch %d/3): %s", attempt, exc)
                continue
            if r.status_code >= 500:
                last_exc = requests.HTTPError(
                    f"{r.status_code} Server Error", response=r,
                )
                logger.warning(
                    "Adzuna HTTP %d (Versuch %d/3) url=%s",
                    r.status_code, attempt, _sanitized_url(url, params),
                )
                continue
            # 4xx oder 2xx: nicht retryen — raise oder return.
            r.raise_for_status()
            return r
        # Alle Versuche fehlgeschlagen.
        raise last_exc if last_exc else RuntimeError("Adzuna: kein Response")


def _sanitized_url(url: str, params: dict) -> str:
    """URL mit Params, aber ohne app_key (Log-Hygiene)."""
    safe = {k: ("***" if k == "app_key" else v) for k, v in params.items()}
    qs = "&".join(f"{k}={v}" for k, v in safe.items())
    return f"{url}?{qs}"
