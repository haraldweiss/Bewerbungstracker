# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/claude-match. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import or_

from database import db
from models import User, JobMatch
from services import cost_tracker
from services.tasks.registry import register


@register('cron_claude_match')
def handle_cron_claude_match(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt den Cron-claude-match-Lauf durch.

    Payload: leerer dict (cron-stages haben keine Parameter — alle User mit
    pending matches werden intern aus DB ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from services.job_matching.claude_utils import (
        _run_claude_match_for, _get_anthropic_client,
        AUTO_CLAUDE_THRESHOLD, HARD_TIME_LIMIT_SEC,
        MATCH_MAX_EVAL_ATTEMPTS, _retry_backoff_hours,
    )
    from services import ai_provider_client

    started = time.time()

    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key.
    if not ai_provider_client.is_enabled():
        client = _get_anthropic_client()
        if client is None:
            raise RuntimeError(
                "Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt"
            )
    else:
        client = None

    matched = 0
    skipped_budget = 0

    users_with_pending = (db.session.query(User)
                          .join(JobMatch, JobMatch.user_id == User.id)
                          .filter(JobMatch.match_score.is_(None),
                                  JobMatch.status.in_(['new', 'seen']),
                                  JobMatch.eval_attempts < MATCH_MAX_EVAL_ATTEMPTS,
                                  or_(JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
                                      JobMatch.eval_attempts >= 1))
                          .distinct().all())

    total_users = len(users_with_pending)
    if progress_cb:
        progress_cb(5, f'{total_users} users with pending matches')

    for idx, user in enumerate(users_with_pending):
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget += 1
            continue

        now = datetime.utcnow()
        candidates = (JobMatch.query
                      .filter(JobMatch.user_id == user.id,
                              JobMatch.match_score.is_(None),
                              JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,
                              JobMatch.status == 'new',
                              JobMatch.eval_attempts < MATCH_MAX_EVAL_ATTEMPTS)
                      .order_by(JobMatch.prefilter_score.desc())
                      .limit(user.job_claude_budget_per_tick).all())

        retry_raw = (JobMatch.query
                     .filter(JobMatch.user_id == user.id,
                             JobMatch.match_score.is_(None),
                             JobMatch.eval_attempts.between(1, MATCH_MAX_EVAL_ATTEMPTS - 1),
                             JobMatch.status.in_(['new', 'seen']),
                             or_(JobMatch.prefilter_score < AUTO_CLAUDE_THRESHOLD,
                                 JobMatch.prefilter_score.is_(None)),
                             JobMatch.updated_at < now - timedelta(hours=1))
                     .order_by(JobMatch.eval_attempts.asc())
                     .all())
        retry = [m for m in retry_raw
                 if (m.updated_at or now) < now - timedelta(hours=_retry_backoff_hours(m.eval_attempts))]
        candidates = candidates + retry[:user.job_claude_budget_per_tick]

        for match in candidates:
            if time.time() - started > HARD_TIME_LIMIT_SEC:
                break
            if _run_claude_match_for(client, user, match):
                matched += 1
            else:
                if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
                    break

        db.session.commit()

        if progress_cb and total_users > 0:
            pct = 5 + int(90 * (idx + 1) / total_users)
            progress_cb(pct, f'user {idx + 1}/{total_users} done, matched={matched}')

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "matched": matched,
        "skipped_budget": skipped_budget,
        "duration_sec": round(time.time() - started, 2),
    }
