# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/cleanup. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

from database import db
from models import JobSource, RawJob, JobMatch
from services.tasks.registry import register


@register('cron_cleanup')
def handle_cron_cleanup(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt den Cron-cleanup-Lauf durch.

    Payload: leerer dict (cron-stages haben keine Parameter — alte RawJobs
    werden intern aus DB ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from api.jobs_cron import ARCHIVE_AFTER_DAYS

    cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)

    candidates = RawJob.query.filter(
        RawJob.created_at < cutoff,
        RawJob.crawl_status != 'archived',
    ).all()

    archived = 0
    for raw in candidates:
        active = JobMatch.query.filter(
            JobMatch.raw_job_id == raw.id,
            JobMatch.status.in_(['new', 'imported']),
        ).count()
        if active == 0:
            raw.crawl_status = 'archived'
            archived += 1

    src_cutoff = datetime.utcnow() - timedelta(days=7)
    healthy_sources = JobSource.query.filter(
        JobSource.last_error.is_(None),
        JobSource.consecutive_failures > 0,
        JobSource.updated_at < src_cutoff,
    ).all()
    for s in healthy_sources:
        s.consecutive_failures = 0

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "archived_raw_jobs": archived,
        "reset_failure_counters": len(healthy_sources),
    }
