# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/url-health-check. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Optional
from urllib.parse import urlparse

from database import db
from models import RawJob
from services.tasks.registry import register

logger = logging.getLogger(__name__)


@register('cron_url_health_check')
def handle_cron_url_health_check(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Batch-URL-Check für RawJobs.

    Payload: leerer dict (cron-stages haben keine Parameter — kandidaten
    werden intern aus DB ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from api.jobs_cron import (
        URL_HEALTH_BATCH_SIZE, URL_HEALTH_RECHECK_INTERVAL_HOURS,
        URL_HEALTH_MAX_AGE_DAYS, URL_HEALTH_PER_DOMAIN_DELAY_S,
    )
    from services import url_health_check as _url_health_check_mod

    now = datetime.utcnow()
    age_cutoff = now - timedelta(days=URL_HEALTH_MAX_AGE_DAYS)
    recheck_cutoff = now - timedelta(hours=URL_HEALTH_RECHECK_INTERVAL_HOURS)

    # Älteste-zuletzt-geprüfte zuerst (NULL = nie geprüft kommt vor).
    candidates = (
        RawJob.query
        .filter(
            RawJob.crawl_status.notin_(['archived', 'marked_for_deletion']),
            RawJob.created_at >= age_cutoff,
            db.or_(
                RawJob.url_last_checked_at.is_(None),
                RawJob.url_last_checked_at < recheck_cutoff,
            ),
        )
        .order_by(
            db.case(
                (RawJob.url_last_checked_at.is_(None), 0),
                else_=1,
            ),
            RawJob.url_last_checked_at.asc(),
        )
        .limit(URL_HEALTH_BATCH_SIZE)
        .all()
    )

    checked = 0
    marked = 0
    ok = 0
    skipped_no_url = 0
    last_call_per_domain: dict[str, float] = {}
    # Hard-Cap auf Total-Run-Time — konservativ auf 150s.
    run_deadline = time.time() + 150.0

    for raw in candidates:
        if time.time() > run_deadline:
            logger.info("url-health-check: deadline reached at %d/%d, deferring rest",
                        checked, len(candidates))
            break
        url = (raw.url or '').strip()
        if not url:
            skipped_no_url += 1
            continue

        # Per-Domain-Throttle
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ''
        if domain:
            last = last_call_per_domain.get(domain, 0.0)
            wait = URL_HEALTH_PER_DOMAIN_DELAY_S - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            last_call_per_domain[domain] = time.time()

        status_label, http_code = _url_health_check_mod.check_url(url)
        was_marked = _url_health_check_mod.update_raw_job_health(
            raw, status_label, http_code,
        )
        checked += 1
        if was_marked:
            marked += 1
            logger.info(
                'url-health-check: raw_id=%s marked_for_deletion (%s code=%s url=%s)',
                raw.id, status_label, http_code, url[:80],
            )
        if status_label == 'ok':
            ok += 1

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        'checked': checked, 'marked': marked, 'ok': ok,
        'skipped_no_url': skipped_no_url,
    }
