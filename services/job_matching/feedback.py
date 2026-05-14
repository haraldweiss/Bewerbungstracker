# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Standard-Feedback-Gründe für Job-Ablehnung/Annahme.

Erweiterbar ohne Migration — Validation prüft nur gegen diese Liste.
"""

from __future__ import annotations
import json

FEEDBACK_REASONS = {
    'wrong_location':   'Falscher Ort',
    'salary_too_low':   'Gehalt zu niedrig',
    'missing_skills':   'Fehlende Skills',
    'wrong_industry':   'Falsche Branche',
    'overqualified':    'Überqualifiziert',
    'underqualified':   'Unterqualifiziert',
    'wrong_seniority':  'Falsches Level',
    'other':            'Sonstiges',
}

MAX_REASONS_PER_FEEDBACK = 5
MAX_FEEDBACK_TEXT_CHARS = 500


def validate_reasons(reasons) -> list[str]:
    """Filtert ungültige Reasons + dedup + cappe auf max 5."""
    if not reasons:
        return []
    seen = set()
    result = []
    for r in reasons:
        if r in FEEDBACK_REASONS and r not in seen:
            seen.add(r)
            result.append(r)
            if len(result) >= MAX_REASONS_PER_FEEDBACK:
                break
    return result


def increment_reason_counts(profile, reasons: list[str]) -> None:
    """Inkrementiere reason_counts-JSON auf profile."""
    try:
        counts = json.loads(profile.reason_counts) if profile.reason_counts else {}
    except (ValueError, TypeError):
        counts = {}
    for r in reasons:
        counts[r] = counts.get(r, 0) + 1
    profile.reason_counts = json.dumps(counts)
