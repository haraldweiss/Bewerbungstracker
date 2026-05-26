# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/notify. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

from database import db
from models import User, RawJob, JobMatch
from services.tasks.registry import register


@register('cron_notify')
def handle_cron_notify(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt den Cron-notify-Lauf durch.

    Payload: leerer dict (cron-stages haben keine Parameter — kandidaten
    werden intern aus DB ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from api.jobs_cron import (
        MAX_NOTIFICATIONS_PER_TICK, HARD_TIME_LIMIT_SEC,
    )
    from services.job_matching.notifier import send_match_notification

    started = time.time()

    candidates = (db.session.query(JobMatch, RawJob, User)
                  .join(RawJob, RawJob.id == JobMatch.raw_job_id)
                  .join(User, User.id == JobMatch.user_id)
                  .filter(JobMatch.notified_at.is_(None),
                          JobMatch.status == 'new',
                          JobMatch.match_score.isnot(None))
                  .all())

    notified = 0
    for match, raw, user in candidates:
        if notified >= MAX_NOTIFICATIONS_PER_TICK:
            break
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break
        if match.match_score < user.job_notification_threshold:
            continue

        send_match_notification(
            user_id=user.id, title=raw.title, company=raw.company,
            score=match.match_score, url=raw.url,
        )
        match.notified_at = datetime.utcnow()
        notified += 1

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {"notified": notified, "duration_sec": round(time.time() - started, 2)}
