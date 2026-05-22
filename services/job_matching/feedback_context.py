# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Phase B: User-Feedback-Historie als Prompt-Kontext für AI-Match.

Wird in api/jobs_cron.py vor dem AI-Match-Call aufgerufen und in
claude_matcher._build_user_message als <user_feedback_history>-Block
eingebunden.

Siehe: docs/superpowers/specs/2026-05-22-feedback-aware-matching-design.md
"""
from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)


def get_user_feedback_context(user_id: str, limit: int = 10) -> str:
    """Returnt formatierten Feedback-History-Block für AI-Prompt.

    Lädt die `limit` neuesten JobMatch-Einträge mit feedback_text und/oder
    feedback_reasons, sortiert nach updated_at desc. Leer-String wenn nichts.
    """
    from models import JobMatch
    from sqlalchemy import or_

    matches = (
        JobMatch.query
        .filter(JobMatch.user_id == user_id)
        .filter(or_(
            JobMatch.feedback_text.isnot(None),
            JobMatch.feedback_reasons.isnot(None),
        ))
        .order_by(JobMatch.updated_at.desc())
        .limit(limit)
        .all()
    )

    entries: list[str] = []
    for m in matches:
        text = (m.feedback_text or "").strip()
        tags: list[str] = []
        if m.feedback_reasons:
            try:
                parsed = json.loads(m.feedback_reasons)
                if isinstance(parsed, list):
                    tags = [str(t) for t in parsed if isinstance(t, str)]
            except (ValueError, TypeError):
                logger.debug(
                    "JobMatch %s: malformed feedback_reasons, skipping tags",
                    m.id,
                )
        if not text and not tags:
            continue
        tag_str = f"[{', '.join(tags)}]" if tags else "[no-tags]"
        if text:
            entries.append(f'{tag_str} "{text[:300]}"')
        else:
            entries.append(tag_str)

    if not entries:
        return ""

    body = "\n".join(entries)
    return (
        "<user_feedback_history>\n"
        "Bisheriges Feedback des Users zu früheren Job-Vorschlägen "
        "(neueste zuerst, Format `[tags] \"text\"`):\n\n"
        f"{body}\n\n"
        "Nutze diese Historie als Kontext: passt der aktuelle Job zu den "
        "positiven Signalen (positive_signal_*) und vermeidet die in "
        "rejected_after_apply genannten Gründe?\n"
        "</user_feedback_history>"
    )
