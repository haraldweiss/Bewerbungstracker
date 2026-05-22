# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Phase C: User's erfolgreiche Bewerbungen als Cover-Letter-Kontext.

Wird in api/cover_letters.py vor dem Generate-Call aufgerufen und in
CoverLetterService.generate als <successful_applications>-Block in den
user_prompt eingebunden.

Erfolgreiche Bewerbungen = status ∈ {interview, zusage}, nicht-gelöscht.
Format: company + position + notes (≤300 chars).

Siehe: docs/superpowers/specs/2026-05-22-feedback-aware-matching-design.md
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

_SUCCESS_STATES = ("interview", "zusage")


def get_user_success_context(user_id: str, limit: int = 5) -> str:
    """Returnt formatierten Erfolgs-Bewerbungs-Block für Cover-Letter-Prompt.

    Lädt die `limit` neuesten Applications des Users mit status interview
    oder zusage, sortiert nach updated_at desc. Leer-String wenn nichts.
    """
    from models import Application

    apps = (
        Application.query
        .filter(Application.user_id == user_id)
        .filter(Application.deleted == False)  # noqa: E712 (SQLAlchemy needs ==)
        .filter(Application.status.in_(_SUCCESS_STATES))
        .order_by(Application.updated_at.desc())
        .limit(limit)
        .all()
    )

    if not apps:
        return ""

    entries: list[str] = []
    for a in apps:
        notes = (a.notes or "").strip()[:300]
        line = (
            f"[{a.status}] Company: {a.company}, Position: {a.position}"
        )
        if notes:
            line += f"\n  Notiz: \"{notes}\""
        entries.append(line)

    body = "\n\n".join(entries)
    return (
        "<successful_applications>\n"
        "Frühere Bewerbungen, die zu Interview/Zusage geführt haben "
        "(NUR als Inspiration für Ton, Schwerpunkte und Themenwahl — "
        "erfinde KEINE Skills, Projekte oder Erfahrungen daraus):\n\n"
        f"{body}\n"
        "</successful_applications>"
    )
