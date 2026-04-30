# Job-Sources: Xing, LinkedIn, Stepstone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drei neue Job-Sources (Xing, LinkedIn, Stepstone) mit Hybrid RSS + Aggregator-API Strategie und strikter URL-basierter Deduplication integrieren.

**Architecture:** Plugin-basiert über bestehenden `JobSourceAdapter`. Jeder Adapter fetcht parallel RSS + Aggregator-API, dedupliziert intern strikt per URL, schließt vorhandene Bewerbungen aus DB aus. Shared Helper-Module für Dedup-Logik und JSearch-Client.

**Tech Stack:** Python 3.14, Flask, SQLAlchemy, `requests`, `feedparser`, `responses` (für Tests), pytest, RapidAPI JSearch (Aggregator).

---

## File Structure

**New Files:**
- `services/job_sources/dedup.py` — Shared Dedup-Helper (DB-Query + Strict URL Match)
- `services/job_sources/jsearch_client.py` — Shared JSearch/RapidAPI-Client
- `services/job_sources/xing.py` — XingAdapter
- `services/job_sources/linkedin.py` — LinkedInAdapter
- `services/job_sources/stepstone.py` — StepstoneAdapter
- `tests/services/test_job_sources_dedup.py`
- `tests/services/test_job_sources_jsearch.py`
- `tests/services/test_job_sources_xing.py`
- `tests/services/test_job_sources_linkedin.py`
- `tests/services/test_job_sources_stepstone.py`
- `tests/fixtures/xing_rss.xml`
- `tests/fixtures/linkedin_jsearch_response.json`
- `tests/fixtures/stepstone_rss.xml`
- `tests/fixtures/jsearch_xing_response.json`

**Modified Files:**
- `services/job_sources/__init__.py` — Registry-Erweiterung (3 neue Adapter)
- `scripts/seed_job_sources.py` — 3 neue Default-Sources

---

## Task 1: Shared Dedup Helper

**Files:**
- Create: `services/job_sources/dedup.py`
- Test: `tests/services/test_job_sources_dedup.py`

- [ ] **Step 1: Write the failing test for `get_existing_job_urls`**

Datei: `tests/services/test_job_sources_dedup.py`

```python
"""Tests für shared Dedup-Helper."""
import pytest
from services.job_sources.dedup import get_existing_job_urls, deduplicate
from services.job_sources.base import FetchedJob
from models import RawJob, JobSource, Application, User
from database import db


def test_get_existing_job_urls_combines_raw_jobs_and_applications(app, db_session):
    """Returns Set aller URLs aus RawJob + Application.link."""
    user = User(id="u1", email="t@t.de", name="T")
    db_session.add(user)
    src = JobSource(name="x", type="rss", enabled=True)
    src.config = {"url": "x"}
    db_session.add(src)
    db_session.flush()

    rj = RawJob(source_id=src.id, external_id="e1",
                title="Dev", url="https://job.example/1")
    db_session.add(rj)

    app_row = Application(user_id="u1", company="C", position="P",
                          link="https://job.example/2")
    db_session.add(app_row)
    db_session.commit()

    urls = get_existing_job_urls()
    assert "https://job.example/1" in urls
    assert "https://job.example/2" in urls


def test_get_existing_job_urls_skips_null_links(app, db_session):
    """Application.link kann NULL sein — nicht in Set landen."""
    user = User(id="u2", email="x@x.de", name="X")
    db_session.add(user)
    db_session.add(Application(user_id="u2", company="C", position="P", link=None))
    db_session.commit()

    urls = get_existing_job_urls()
    assert None not in urls


def test_deduplicate_removes_in_batch_url_duplicates():
    """Dieselbe URL 2x in jobs-Liste → nur 1x im Result."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T1-dup", url="https://j.de/1"),
        FetchedJob(external_id="c", title="T2", url="https://j.de/2"),
    ]
    result = deduplicate(jobs, existing_urls=set())
    assert len(result) == 2
    assert {j.url for j in result} == {"https://j.de/1", "https://j.de/2"}


def test_deduplicate_excludes_existing_urls():
    """Jobs mit URL in existing_urls werden ausgefiltert."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T2", url="https://j.de/2"),
    ]
    result = deduplicate(jobs, existing_urls={"https://j.de/1"})
    assert len(result) == 1
    assert result[0].url == "https://j.de/2"


def test_deduplicate_preserves_order():
    """Reihenfolge der ersten Vorkommen bleibt erhalten."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T2", url="https://j.de/2"),
        FetchedJob(external_id="c", title="T1-dup", url="https://j.de/1"),
    ]
    result = deduplicate(jobs, existing_urls=set())
    assert [j.url for j in result] == ["https://j.de/1", "https://j.de/2"]
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/services/test_job_sources_dedup.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.job_sources.dedup'`

- [ ] **Step 3: Implement `dedup.py`**

Datei: `services/job_sources/dedup.py`

```python
"""Shared Dedup-Helper für Job-Sources.

Strikte URL-basierte Deduplication:
- Innerhalb einer Fetch-Batch: erste URL gewinnt
- Gegen DB: existierende RawJob.url + Application.link werden ausgeschlossen
"""
from __future__ import annotations
from typing import Iterable

from database import db
from models import RawJob, Application
from services.job_sources.base import FetchedJob


def get_existing_job_urls() -> set[str]:
    """Lädt alle bekannten Job-URLs (RawJob + Application.link).

    Wird einmal pro Fetch-Tick aufgerufen — Caching innerhalb eines Adapters.
    """
    raw_urls = db.session.query(RawJob.url).all()
    app_urls = db.session.query(Application.link).filter(
        Application.link.isnot(None)
    ).all()
    return {u[0] for u in raw_urls + app_urls if u[0]}


def deduplicate(
    jobs: Iterable[FetchedJob],
    existing_urls: set[str],
) -> list[FetchedJob]:
    """Strikte URL-Dedup: in-batch + gegen existing.

    Reihenfolge bleibt erhalten (erste Vorkommen wird behalten).
    """
    seen: set[str] = set()
    result: list[FetchedJob] = []
    for job in jobs:
        if not job.url:
            continue
        if job.url in seen or job.url in existing_urls:
            continue
        seen.add(job.url)
        result.append(job)
    return result
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/services/test_job_sources_dedup.py -v
```

Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/dedup.py tests/services/test_job_sources_dedup.py
git commit -m "feat: shared dedup helper for job sources (strict URL match)"
```

---

## Task 2: Shared JSearch Client (Aggregator-API)

**Files:**
- Create: `services/job_sources/jsearch_client.py`
- Test: `tests/services/test_job_sources_jsearch.py`
- Create: `tests/fixtures/jsearch_xing_response.json`

- [ ] **Step 1: Create test fixture**

Datei: `tests/fixtures/jsearch_xing_response.json`

```json
{
  "status": "OK",
  "request_id": "abc123",
  "data": [
    {
      "job_id": "xing-12345",
      "job_title": "Senior Python Developer",
      "employer_name": "ACME GmbH",
      "job_apply_link": "https://www.xing.com/jobs/12345",
      "job_city": "Berlin",
      "job_country": "DE",
      "job_description": "We seek a Python expert...",
      "job_publisher": "Xing",
      "job_posted_at_timestamp": 1745000000
    },
    {
      "job_id": "xing-67890",
      "job_title": "Data Engineer",
      "employer_name": "Beta AG",
      "job_apply_link": "https://www.xing.com/jobs/67890",
      "job_city": "München",
      "job_country": "DE",
      "job_description": "Big Data role...",
      "job_publisher": "Xing",
      "job_posted_at_timestamp": 1745100000
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Datei: `tests/services/test_job_sources_jsearch.py`

```python
"""Tests für JSearchClient (RapidAPI Aggregator)."""
import json
from pathlib import Path
import pytest
import responses
from services.job_sources.jsearch_client import JSearchClient

FIX = Path(__file__).parent.parent / "fixtures" / "jsearch_xing_response.json"


@responses.activate
def test_jsearch_returns_empty_without_api_key():
    """Ohne API-Key wird leeres Result zurückgegeben (kein Error)."""
    client = JSearchClient(api_key=None)
    jobs = client.search(query="python", platform="xing", location="Germany")
    assert jobs == []


@responses.activate
def test_jsearch_parses_response_to_fetched_jobs():
    """Mock-Response → korrekt geparste FetchedJob-Liste."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="python", platform="xing", location="Germany")

    assert len(jobs) == 2
    assert jobs[0].external_id == "xing-12345"
    assert jobs[0].title == "Senior Python Developer"
    assert jobs[0].company == "ACME GmbH"
    assert jobs[0].url == "https://www.xing.com/jobs/12345"
    assert jobs[0].location == "Berlin"
    assert jobs[0].posted_at is not None


@responses.activate
def test_jsearch_filters_by_publisher():
    """Nur Jobs mit publisher matching platform werden zurückgegeben."""
    mixed = {
        "data": [
            {"job_id": "1", "job_title": "T1", "job_apply_link": "u1",
             "job_publisher": "Xing", "employer_name": "A"},
            {"job_id": "2", "job_title": "T2", "job_apply_link": "u2",
             "job_publisher": "Indeed", "employer_name": "B"},
        ]
    }
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=mixed,
        status=200,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="x", platform="xing", location="DE")
    assert len(jobs) == 1
    assert jobs[0].external_id == "1"


@responses.activate
def test_jsearch_returns_empty_on_http_error():
    """Bei HTTP-Error: leere Liste, kein Crash (Resilienz)."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json={"error": "rate limit"},
        status=429,
    )
    client = JSearchClient(api_key="fake-key")
    jobs = client.search(query="x", platform="xing", location="DE")
    assert jobs == []
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/services/test_job_sources_jsearch.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.job_sources.jsearch_client'`

- [ ] **Step 4: Implement `jsearch_client.py`**

Datei: `services/job_sources/jsearch_client.py`

```python
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
        num_pages: int = 1,
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
            "num_pages": str(num_pages),
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

            posted_at = None
            ts = item.get("job_posted_at_timestamp")
            if ts:
                try:
                    posted_at = datetime.fromtimestamp(int(ts))
                except (ValueError, TypeError):
                    pass

            location_str = ", ".join(filter(None, [
                item.get("job_city"), item.get("job_country")
            ])) or None

            jobs.append(FetchedJob(
                external_id=str(item.get("job_id", "")),
                title=item.get("job_title", ""),
                url=item.get("job_apply_link", ""),
                company=item.get("employer_name"),
                location=location_str,
                description=item.get("job_description"),
                posted_at=posted_at,
                raw=item,
            ))
        return jobs
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/services/test_job_sources_jsearch.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/jsearch_client.py tests/services/test_job_sources_jsearch.py tests/fixtures/jsearch_xing_response.json
git commit -m "feat: JSearch RapidAPI client for job aggregator integration"
```

---

## Task 3: XingAdapter

**Files:**
- Create: `services/job_sources/xing.py`
- Test: `tests/services/test_job_sources_xing.py`
- Create: `tests/fixtures/xing_rss.xml`

- [ ] **Step 1: Create RSS fixture**

Datei: `tests/fixtures/xing_rss.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Xing Jobs — Python Berlin</title>
    <link>https://www.xing.com/jobs</link>
    <description>Job results</description>
    <item>
      <title>Senior Python Developer (m/w/d)</title>
      <link>https://www.xing.com/jobs/python-dev-berlin-100</link>
      <guid>xing-100</guid>
      <description>Python role at ACME...</description>
      <category>Berlin</category>
      <pubDate>Mon, 28 Apr 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Backend Engineer Python</title>
      <link>https://www.xing.com/jobs/backend-eng-200</link>
      <guid>xing-200</guid>
      <description>Backend role at Beta...</description>
      <category>München</category>
      <pubDate>Tue, 29 Apr 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write the failing tests**

Datei: `tests/services/test_job_sources_xing.py`

```python
"""Tests für XingAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import responses
from services.job_sources.xing import XingAdapter

FIX_RSS = Path(__file__).parent.parent / "fixtures" / "xing_rss.xml"
FIX_JSEARCH = Path(__file__).parent.parent / "fixtures" / "jsearch_xing_response.json"


@responses.activate
def test_xing_fetch_rss_only_no_aggregator():
    """Ohne aggregator_key: nur RSS, kein API-Call."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
        content_type="application/rss+xml",
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Senior Python Developer (m/w/d)" in titles
    assert "Backend Engineer Python" in titles


@responses.activate
def test_xing_fetch_combines_rss_and_aggregator():
    """RSS + JSearch parallel — kombiniert + dedupliziert."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX_JSEARCH.read_text()),
        status=200,
    )

    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
        "aggregator_key": "fake-key",
        "query": "python",
        "location": "Germany",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    # 2 from RSS + 2 from JSearch = 4 (no overlap in fixtures)
    assert len(jobs) == 4
    urls = {j.url for j in jobs}
    assert "https://www.xing.com/jobs/python-dev-berlin-100" in urls
    assert "https://www.xing.com/jobs/12345" in urls


@responses.activate
def test_xing_dedup_excludes_existing_urls():
    """URLs aus DB werden ausgefiltert."""
    responses.add(
        responses.GET,
        "https://www.xing.com/jobs/feed/python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    adapter = XingAdapter(config={
        "rss_url": "https://www.xing.com/jobs/feed/python",
    })
    existing = {"https://www.xing.com/jobs/python-dev-berlin-100"}
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.xing.com/jobs/backend-eng-200"


@responses.activate
def test_xing_fetch_without_rss_url_uses_only_aggregator():
    """Ohne rss_url: nur Aggregator wird genutzt."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX_JSEARCH.read_text()),
        status=200,
    )
    adapter = XingAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
    })
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    assert all("xing.com" in j.url for j in jobs)


def test_xing_no_config_returns_empty():
    """Weder rss_url noch aggregator_key: leeres Result."""
    adapter = XingAdapter(config={})
    with patch("services.job_sources.xing.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/services/test_job_sources_xing.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.job_sources.xing'`

- [ ] **Step 4: Implement `xing.py`**

Datei: `services/job_sources/xing.py`

```python
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
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/services/test_job_sources_xing.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/xing.py tests/services/test_job_sources_xing.py tests/fixtures/xing_rss.xml
git commit -m "feat: XingAdapter with hybrid RSS + JSearch aggregator"
```

---

## Task 4: LinkedInAdapter

**Files:**
- Create: `services/job_sources/linkedin.py`
- Test: `tests/services/test_job_sources_linkedin.py`
- Create: `tests/fixtures/linkedin_jsearch_response.json`

> **Note:** LinkedIn bietet **kein offizielles Public-RSS** — der Adapter ist primär aggregator-basiert. `rss_url` bleibt aber konfigurierbar (z.B. für RSSHub-Drittanbieter).

- [ ] **Step 1: Create JSearch fixture for LinkedIn**

Datei: `tests/fixtures/linkedin_jsearch_response.json`

```json
{
  "status": "OK",
  "data": [
    {
      "job_id": "linkedin-aaa",
      "job_title": "Staff Engineer",
      "employer_name": "TechCorp",
      "job_apply_link": "https://www.linkedin.com/jobs/view/aaa",
      "job_city": "Berlin",
      "job_country": "DE",
      "job_publisher": "LinkedIn",
      "job_posted_at_timestamp": 1745200000
    },
    {
      "job_id": "linkedin-bbb",
      "job_title": "Engineering Manager",
      "employer_name": "Gamma Inc",
      "job_apply_link": "https://www.linkedin.com/jobs/view/bbb",
      "job_city": "Hamburg",
      "job_country": "DE",
      "job_publisher": "LinkedIn",
      "job_posted_at_timestamp": 1745300000
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Datei: `tests/services/test_job_sources_linkedin.py`

```python
"""Tests für LinkedInAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import responses
from services.job_sources.linkedin import LinkedInAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "linkedin_jsearch_response.json"


@responses.activate
def test_linkedin_fetch_via_aggregator():
    """LinkedIn: aggregator-only flow."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = LinkedInAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
        "location": "Germany",
    })
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Staff Engineer" in titles
    assert "Engineering Manager" in titles
    assert all("linkedin.com" in j.url for j in jobs)


@responses.activate
def test_linkedin_dedup_excludes_existing_urls():
    """Existierende URLs werden ausgefiltert."""
    responses.add(
        responses.GET,
        "https://jsearch.p.rapidapi.com/search",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = LinkedInAdapter(config={
        "aggregator_key": "fake-key",
        "query": "python",
    })
    existing = {"https://www.linkedin.com/jobs/view/aaa"}
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/bbb"


def test_linkedin_no_config_returns_empty():
    """Ohne aggregator_key und ohne rss_url: leer."""
    adapter = LinkedInAdapter(config={})
    with patch("services.job_sources.linkedin.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/services/test_job_sources_linkedin.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `linkedin.py`**

Datei: `services/job_sources/linkedin.py`

```python
"""LinkedIn Job-Source Adapter.

LinkedIn hat kein offizielles RSS — primär Aggregator-API.
rss_url kann aber als Drittanbieter-Feed (z.B. RSSHub) konfiguriert werden.
"""
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

PLATFORM = "linkedin"


class LinkedInAdapter(JobSourceAdapter):
    """Hybrid: optional RSS (Drittanbieter) + JSearch Aggregator."""

    def fetch(self) -> list[FetchedJob]:
        rss_jobs = self._fetch_rss()
        agg_jobs = self._fetch_aggregator()
        combined = rss_jobs + agg_jobs

        existing = get_existing_job_urls()
        deduped = deduplicate(combined, existing)
        logger.info(
            f"LinkedIn: rss={len(rss_jobs)} agg={len(agg_jobs)} "
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
            logger.warning(f"LinkedIn RSS error: {e}")
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
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/services/test_job_sources_linkedin.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/linkedin.py tests/services/test_job_sources_linkedin.py tests/fixtures/linkedin_jsearch_response.json
git commit -m "feat: LinkedInAdapter with JSearch aggregator (no public RSS)"
```

---

## Task 5: StepstoneAdapter

**Files:**
- Create: `services/job_sources/stepstone.py`
- Test: `tests/services/test_job_sources_stepstone.py`
- Create: `tests/fixtures/stepstone_rss.xml`

- [ ] **Step 1: Create RSS fixture**

Datei: `tests/fixtures/stepstone_rss.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Stepstone Job-Suche</title>
    <link>https://www.stepstone.de</link>
    <description>Job-Feeds</description>
    <item>
      <title>Fullstack Entwickler (m/w/d)</title>
      <link>https://www.stepstone.de/stellenangebote/fullstack-1234</link>
      <guid>stepstone-1234</guid>
      <description>Fullstack-Position bei XYZ AG</description>
      <category>Frankfurt</category>
      <pubDate>Wed, 30 Apr 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>DevOps Engineer</title>
      <link>https://www.stepstone.de/stellenangebote/devops-5678</link>
      <guid>stepstone-5678</guid>
      <description>DevOps-Rolle</description>
      <category>Köln</category>
      <pubDate>Wed, 30 Apr 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write the failing tests**

Datei: `tests/services/test_job_sources_stepstone.py`

```python
"""Tests für StepstoneAdapter."""
import json
from pathlib import Path
from unittest.mock import patch
import responses
from services.job_sources.stepstone import StepstoneAdapter

FIX_RSS = Path(__file__).parent.parent / "fixtures" / "stepstone_rss.xml"


@responses.activate
def test_stepstone_fetch_rss():
    """RSS-only-flow für Stepstone."""
    responses.add(
        responses.GET,
        "https://www.stepstone.de/jobs.rss?q=python",
        body=FIX_RSS.read_text(),
        status=200,
        content_type="application/rss+xml",
    )
    adapter = StepstoneAdapter(config={
        "rss_url": "https://www.stepstone.de/jobs.rss?q=python",
    })
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert "Fullstack Entwickler (m/w/d)" in titles
    assert "DevOps Engineer" in titles


@responses.activate
def test_stepstone_dedup_excludes_existing_urls():
    """Bekannte URLs werden gefiltert."""
    responses.add(
        responses.GET,
        "https://www.stepstone.de/jobs.rss?q=python",
        body=FIX_RSS.read_text(),
        status=200,
    )
    adapter = StepstoneAdapter(config={
        "rss_url": "https://www.stepstone.de/jobs.rss?q=python",
    })
    existing = {"https://www.stepstone.de/stellenangebote/fullstack-1234"}
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=existing):
        jobs = adapter.fetch()

    assert len(jobs) == 1
    assert jobs[0].url == "https://www.stepstone.de/stellenangebote/devops-5678"


def test_stepstone_no_config_returns_empty():
    """Ohne config: leer."""
    adapter = StepstoneAdapter(config={})
    with patch("services.job_sources.stepstone.get_existing_job_urls", return_value=set()):
        jobs = adapter.fetch()
    assert jobs == []
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/services/test_job_sources_stepstone.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `stepstone.py`**

Datei: `services/job_sources/stepstone.py`

```python
"""Stepstone Job-Source Adapter (RSS + JSearch Aggregator)."""
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

PLATFORM = "stepstone"


class StepstoneAdapter(JobSourceAdapter):
    """Hybrid: RSS-Feed + JSearch Aggregator.

    Config-Schema:
        {
            "rss_url": "https://www.stepstone.de/jobs.rss?q=...",
            "aggregator_key": "...",
            "query": "...",
            "location": "Germany"
        }
    """

    def fetch(self) -> list[FetchedJob]:
        rss_jobs = self._fetch_rss()
        agg_jobs = self._fetch_aggregator()
        combined = rss_jobs + agg_jobs

        existing = get_existing_job_urls()
        deduped = deduplicate(combined, existing)
        logger.info(
            f"Stepstone: rss={len(rss_jobs)} agg={len(agg_jobs)} "
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
            logger.warning(f"Stepstone RSS error: {e}")
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
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/services/test_job_sources_stepstone.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/stepstone.py tests/services/test_job_sources_stepstone.py tests/fixtures/stepstone_rss.xml
git commit -m "feat: StepstoneAdapter with hybrid RSS + JSearch aggregator"
```

---

## Task 6: Registry Update

**Files:**
- Modify: `services/job_sources/__init__.py:1-19`

- [ ] **Step 1: Read the current registry**

```bash
cat services/job_sources/__init__.py
```

Expected output (current):
```python
from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
from services.job_sources.adzuna import AdzunaAdapter
from services.job_sources.bundesagentur import BundesagenturAdapter
from services.job_sources.arbeitnow import ArbeitnowAdapter


def get_adapter(source_type: str, config: dict) -> JobSourceAdapter:
    registry = {
        "rss": RssAdapter,
        "adzuna": AdzunaAdapter,
        "bundesagentur": BundesagenturAdapter,
        "arbeitnow": ArbeitnowAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    return cls(config)
```

- [ ] **Step 2: Replace with extended registry**

Datei: `services/job_sources/__init__.py` (full content):

```python
from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
from services.job_sources.adzuna import AdzunaAdapter
from services.job_sources.bundesagentur import BundesagenturAdapter
from services.job_sources.arbeitnow import ArbeitnowAdapter
from services.job_sources.xing import XingAdapter
from services.job_sources.linkedin import LinkedInAdapter
from services.job_sources.stepstone import StepstoneAdapter


def get_adapter(source_type: str, config: dict) -> JobSourceAdapter:
    registry = {
        "rss": RssAdapter,
        "adzuna": AdzunaAdapter,
        "bundesagentur": BundesagenturAdapter,
        "arbeitnow": ArbeitnowAdapter,
        "xing": XingAdapter,
        "linkedin": LinkedInAdapter,
        "stepstone": StepstoneAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    return cls(config)
```

- [ ] **Step 3: Verify all existing tests still pass**

```bash
pytest tests/services/ -v
```

Expected: PASS (alle vorhandenen + neuen Tests)

- [ ] **Step 4: Verify get_adapter resolves new types**

```bash
python -c "from services.job_sources import get_adapter; print(type(get_adapter('xing', {})).__name__); print(type(get_adapter('linkedin', {})).__name__); print(type(get_adapter('stepstone', {})).__name__)"
```

Expected output:
```
XingAdapter
LinkedInAdapter
StepstoneAdapter
```

- [ ] **Step 5: Commit**

```bash
git add services/job_sources/__init__.py
git commit -m "feat: register Xing/LinkedIn/Stepstone adapters in job_sources registry"
```

---

## Task 7: Seed-Script Erweiterung

**Files:**
- Modify: `scripts/seed_job_sources.py:20-36`

- [ ] **Step 1: Update DEFAULTS list**

Datei: `scripts/seed_job_sources.py` — **Replace the `DEFAULTS = [...]` block** mit:

```python
import os

DEFAULTS = [
    {
        "name": "Bundesagentur — Frontend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Frontend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Bundesagentur — Backend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Backend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Arbeitnow — Remote Tech",
        "type": "arbeitnow",
        "config": {"tags": ["javascript", "python", "remote"]},
    },
    {
        "name": "Xing — Python Berlin",
        "type": "xing",
        "config": {
            "rss_url": os.getenv("XING_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "python developer",
            "location": "Germany",
        },
    },
    {
        "name": "LinkedIn — Engineering Berlin",
        "type": "linkedin",
        "config": {
            "rss_url": os.getenv("LINKEDIN_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "software engineer",
            "location": "Germany",
        },
    },
    {
        "name": "Stepstone — Tech Berlin",
        "type": "stepstone",
        "config": {
            "rss_url": os.getenv("STEPSTONE_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "developer",
            "location": "Germany",
        },
    },
]
```

> **Note:** `os` ist im File schon importiert. Kein neuer Import nötig.

- [ ] **Step 2: Run seed script (dry test against dev DB)**

```bash
python scripts/seed_job_sources.py
```

Expected output (etwa):
```
= Bundesagentur — Frontend Entwickler Berlin (existiert bereits)
= Bundesagentur — Backend Entwickler Berlin (existiert bereits)
= Arbeitnow — Remote Tech (existiert bereits)
+ Xing — Python Berlin
+ LinkedIn — Engineering Berlin
+ Stepstone — Tech Berlin
✓ Seed abgeschlossen.
```

- [ ] **Step 3: Verify in DB**

```bash
python -c "from app import create_app; from models import JobSource; app=create_app(); ctx=app.app_context(); ctx.push(); print([(s.name, s.type, s.enabled) for s in JobSource.query.filter(JobSource.type.in_(['xing','linkedin','stepstone'])).all()])"
```

Expected: 3 Rows mit type=xing/linkedin/stepstone, enabled=True.

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_job_sources.py
git commit -m "feat: seed Xing/LinkedIn/Stepstone job sources via env-vars"
```

---

## Task 8: Manual End-to-End Validation

**Files:** None (manual checks)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/services/ -v
```

Expected: ALL PASS — keine bestehenden Tests gebrochen.

- [ ] **Step 2: Trigger cron tick locally**

```bash
# Falls CRON_TOKEN gesetzt ist:
curl -X POST http://localhost:5000/api/cron/tick \
  -H "X-Cron-Token: ${CRON_TOKEN}"
```

Expected: 200 OK, JSON-Response mit Source-Stats inkl. `xing`, `linkedin`, `stepstone`.

- [ ] **Step 3: Check logs for new adapters**

```bash
tail -100 logs/app.log | grep -E "Xing|LinkedIn|Stepstone"
```

Expected log-pattern (ähnlich):
```
INFO Xing: rss=12 agg=5 combined=17 after_dedup=15
INFO LinkedIn: rss=0 agg=8 combined=8 after_dedup=7
INFO Stepstone: rss=20 agg=3 combined=23 after_dedup=20
```

- [ ] **Step 4: Inspect RawJob table**

```bash
python -c "
from app import create_app
from models import RawJob, JobSource
app = create_app()
with app.app_context():
    for t in ['xing', 'linkedin', 'stepstone']:
        sources = JobSource.query.filter_by(type=t).all()
        for s in sources:
            count = RawJob.query.filter_by(source_id=s.id).count()
            print(f'{t}: {s.name} → {count} raw jobs')
"
```

Expected: Counts > 0 für Sources mit gültiger Config (rss_url oder aggregator_key gesetzt).

- [ ] **Step 5: Verify no duplicate URLs across new sources**

```bash
python -c "
from app import create_app
from models import RawJob, JobSource
from sqlalchemy import func
app = create_app()
with app.app_context():
    duplicates = (RawJob.query
        .with_entities(RawJob.url, func.count(RawJob.id).label('cnt'))
        .group_by(RawJob.url)
        .having(func.count(RawJob.id) > 1)
        .all())
    print(f'Duplicate URLs across sources: {len(duplicates)}')
    for url, cnt in duplicates[:5]:
        print(f'  {cnt}× {url}')
"
```

Expected: Idealerweise `0`. Falls > 0: Konflikt zwischen Sources, ggf. Strategie für Cross-Source-Dedup verfeinern (out-of-scope für diesen Plan).

- [ ] **Step 6: Final commit (if any tweaks)**

Wenn alle Steps grün sind: keine weiteren Commits nötig. Sonst: kleinere Fixes committen.

---

## Self-Review Notes

**Spec Coverage:**
- ✅ Architecture (Hybrid RSS + Aggregator) → Tasks 3, 4, 5
- ✅ Strict URL Deduplication → Task 1 (shared dedup)
- ✅ Existing Applications excluded → Task 1 (`get_existing_job_urls`)
- ✅ No DB schema changes → confirmed
- ✅ Backward compatible → Task 6 erweitert nur registry
- ✅ Tests per adapter (RSS + aggregator + dedup) → Tasks 3, 4, 5
- ✅ Seed-Script erweitert → Task 7
- ✅ Manual validation → Task 8

**Type Consistency Check:**
- `JSearchClient.search(query, platform, location)` — used identically in xing.py, linkedin.py, stepstone.py ✓
- `get_existing_job_urls()` — same signature in all 3 adapters ✓
- `deduplicate(jobs, existing_urls)` — same signature ✓
- `FetchedJob` schema — used consistently ✓

**Notes for Implementation:**
- LinkedIn hat kein offizielles Public-RSS — Adapter-Code unterstützt aber `rss_url` (z.B. RSSHub) wenn konfiguriert, sonst skip.
- `responses` library wird für Test-Mocking benutzt (siehe bestehende `test_job_sources_arbeitnow.py`).
- DB-Tests (`test_job_sources_dedup.py`) brauchen `app` und `db_session` Fixtures — diese existieren bereits in der Test-Suite.
- Cross-Source-Dedup (z.B. derselbe Job auf Xing und LinkedIn mit unterschiedlichen URLs) ist **nicht** Teil dieses Plans — strikte Variante per User-Wunsch.
