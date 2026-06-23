# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/crawl-source. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

from database import db
from models import JobSource, RawJob, JobMatch
from services.tasks.registry import register


@register('cron_crawl_source')
def handle_cron_crawl_source(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt den Cron-crawl-source-Lauf durch.

    Payload: leerer dict (cron-stages haben keine Parameter — Source-Auswahl
    wird intern via _select_due_source ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from api.jobs_cron import (
        _select_due_source, _eligible_users_for_source,
        MAX_NEW_JOBS_PER_TICK, HARD_TIME_LIMIT_SEC, AUTO_DISABLE_FAILURE_COUNT,
    )
    from services.job_sources import get_adapter
    from services.job_sources.url_resolver import normalize_url

    started = time.time()
    src = _select_due_source()
    if src is None:
        return {"source_id": None, "reason": "no_source_due"}

    src.last_crawled_at = datetime.utcnow()

    try:
        adapter = get_adapter(src.type, src.config)
        fetched = adapter.fetch()
    except Exception as e:
        src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
        src.consecutive_failures += 1
        if src.consecutive_failures >= AUTO_DISABLE_FAILURE_COUNT:
            src.enabled = False
        db.session.commit()
        return {
            "source_id": src.id,
            "error": src.last_error,
            "consecutive_failures": src.consecutive_failures,
            "auto_disabled": not src.enabled,
        }

    src.last_error = None
    src.consecutive_failures = 0

    eligible_users = _eligible_users_for_source(src)
    new_jobs = 0
    matches_created = 0

    if progress_cb:
        progress_cb(10, f'fetched {len(fetched)} jobs, processing')

    for fj in fetched[:MAX_NEW_JOBS_PER_TICK]:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        existing = RawJob.query.filter_by(source_id=src.id, external_id=fj.external_id).first()
        if existing:
            continue

        raw = RawJob(
            source_id=src.id,
            external_id=fj.external_id,
            title=fj.title,
            company=fj.company,
            location=fj.location,
            url=normalize_url(fj.url),
            description=fj.description,
            posted_at=fj.posted_at,
            crawl_status='raw',
        )
        raw.raw_payload = {
            k: v for k, v in fj.raw.items()
            if isinstance(v, (str, int, float, bool, type(None), list, dict))
        }
        db.session.add(raw)
        db.session.flush()
        new_jobs += 1

        for user in eligible_users:
            db.session.add(JobMatch(
                raw_job_id=raw.id, user_id=user.id, status='new'
            ))
            matches_created += 1

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "source_id": src.id,
        "new_jobs": new_jobs,
        "matches_created": matches_created,
        "duration_sec": round(time.time() - started, 2),
    }
