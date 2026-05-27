# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /matches/score-bulk. Logik aus api/jobs_user.py extrahiert."""
from __future__ import annotations

from typing import Callable, Optional

from database import db
from models import User, JobMatch
from services.tasks.registry import register


@register('claude_match_bulk')
def handle_claude_match_bulk(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Bulk-Claude-Match für eine Liste Match-IDs.

    Payload:
        user_id (str)
        match_ids (list[int])

    Returns: gleiches dict wie früher synchroner Endpoint —
        scored, skipped_budget, errors, forbidden, not_found
    """
    from services.job_matching.claude_utils import _run_claude_match_for, _get_anthropic_client
    from services import ai_provider_client, cost_tracker

    user = User.query.get(payload['user_id'])
    if user is None:
        raise ValueError(f"user_id {payload['user_id']!r} nicht gefunden")

    ids = payload.get('match_ids') or []
    if not isinstance(ids, list) or not ids:
        raise ValueError("match_ids muss nicht-leere Liste sein")

    matches = JobMatch.query.filter(JobMatch.id.in_(ids)).all()
    found_ids = {m.id for m in matches}
    not_found = [i for i in ids if i not in found_ids]

    forbidden = [m.id for m in matches if m.user_id != user.id]
    own = [m for m in matches if m.user_id == user.id]

    # Im Service-Modus brauchen wir keinen lokalen Anthropic-Key.
    if ai_provider_client.is_enabled():
        client = None
    else:
        client = _get_anthropic_client()
        if client is None:
            raise RuntimeError("Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt")

    scored = []
    skipped_budget = []
    errors = []

    total = len(own) or 1
    for i, m in enumerate(own):
        if progress_cb:
            progress_cb(int(i * 100 / total), f'{i}/{total}')

        # Budget-Check vor jedem Match (kann sich mid-loop ändern durch flush in Helper)
        if cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget.append(m.id)
            continue
        try:
            success = _run_claude_match_for(client, user, m)
            if success:
                scored.append({"id": m.id, "match_score": m.match_score})
            else:
                # Helper returnt False bei drei Gründen — disambiguieren:
                if m.match_score is not None:
                    # Schon bewertet (idempotent path)
                    scored.append({"id": m.id, "match_score": m.match_score})
                elif cost_tracker.user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
                    # Budget mid-call erschöpft
                    skipped_budget.append(m.id)
                else:
                    # Claude-Error (Helper hat schon geloggt)
                    errors.append({"id": m.id, "error": "Claude-Bewertung fehlgeschlagen"})
        except Exception as e:
            errors.append({"id": m.id, "error": str(e)})

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "scored": scored,
        "skipped_budget": skipped_budget,
        "errors": errors,
        "forbidden": forbidden,
        "not_found": not_found,
    }
