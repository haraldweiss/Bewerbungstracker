# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Phase A: Bridge Application.notes → JobMatch.feedback_text.

Bei Status-Wechsel einer Application auf einen terminalen Status
(absage/ghosting/interview/zusage) wird der Inhalt von Application.notes
in den verknüpften JobMatch.feedback_text gespiegelt + ein passender
Tag in JobMatch.feedback_reasons gesetzt. Der existing pre-filter
learner (services.job_matching.learner) zieht das automatisch mit.

Siehe Spec: docs/superpowers/specs/2026-05-22-feedback-aware-matching-design.md
"""
from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)

_TERMINAL_STATES = frozenset({"absage", "ghosting", "interview", "zusage"})
_STATUS_TAGS = {
    "absage": "rejected_after_apply",
    "ghosting": "rejected_after_apply",
    "interview": "positive_signal_interview",
    "zusage": "positive_signal_offer",
}


def maybe_bridge_to_feedback(application) -> bool:
    """Spiegelt Application.notes → JobMatch.feedback_text wenn relevant.

    Returns True wenn ein Match aktualisiert wurde.
    """
    if application.status not in _TERMINAL_STATES:
        return False
    notes = (application.notes or "").strip()
    if not notes:
        return False

    from models import JobMatch, User
    from database import db
    match = JobMatch.query.filter_by(
        imported_application_id=application.id
    ).first()
    if match is None:
        return False

    # Idempotency: wenn die notes schon in feedback_text drin sind, skip
    existing_text = (match.feedback_text or "").strip()
    if existing_text == notes or notes in existing_text:
        return False

    # Anhängen statt überschreiben (User kann beim Dismiss schon was hingeschrieben haben)
    if existing_text:
        match.feedback_text = (
            f"{existing_text}\n--- aus Bewerbungs-Notiz ---\n{notes}"
        ).strip()
    else:
        match.feedback_text = notes

    # Tag hinzufügen wenn noch nicht da
    tag = _STATUS_TAGS[application.status]
    existing_reasons: list = []
    if match.feedback_reasons:
        try:
            parsed = json.loads(match.feedback_reasons)
            if isinstance(parsed, list):
                existing_reasons = parsed
        except (ValueError, TypeError):
            logger.warning(
                "JobMatch %s: malformed feedback_reasons, fallback zu []",
                match.id,
            )
    if tag not in existing_reasons:
        existing_reasons.append(tag)
    match.feedback_reasons = json.dumps(existing_reasons)

    # Existing learner triggern (centroid-update). Erwartet user-Objekt, nicht user_id.
    try:
        from services.job_matching.learner import update_centroid_for_feedback
        user = User.query.get(application.user_id)
        if user is not None:
            update_centroid_for_feedback(user, match)
    except Exception as exc:
        logger.warning(
            "feedback_bridge: learner-Update fehlgeschlagen (match %s): %s",
            match.id, exc,
        )

    db.session.commit()
    return True
