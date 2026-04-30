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
