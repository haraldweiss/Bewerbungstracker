# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Einmal-Cleanup: technische Fehlbewertungen (ohne menschliches Urteil) zur Neubewertung zurückstellen.

Usage:
    python scripts/reeval_technical_failures.py            # Dry-run
    python scripts/reeval_technical_failures.py --apply    # schreibt (mit JSON-Backup)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from database import db
from models import JobMatch


def select_candidates():
    """Verworfene/neue Matches mit technischer Fehlbegründung, ohne menschliches feedback_reasons."""
    return (JobMatch.query
            .filter(JobMatch.match_reasoning.like('Bewertung fehlgeschlagen%'),
                    JobMatch.feedback_reasons.is_(None))
            .all())


def reset_match(m: JobMatch) -> None:
    """Stellt einen Match auf retriable: status='new', Score/Reasoning geleert, eval_attempts=1."""
    if m.status == 'dismissed':
        m.status = 'new'
    m.match_score = None
    m.match_reasoning = None
    m.missing_skills = []
    m.notified_at = None
    m.eval_attempts = 1


def main() -> None:
    apply = '--apply' in sys.argv
    from app import create_app
    app = create_app()
    with app.app_context():
        rows = select_candidates()
        print(f"Technische Fehlschläge ohne menschliches Urteil: {len(rows)}")
        for m in rows:
            print(f"  match {m.id}: status={m.status} score={m.match_score} "
                  f"feedback_text={m.feedback_text!r}")
        if not apply:
            print("\n(DRY-RUN — nichts geändert. Mit --apply ausführen.)")
            return
        backup = [{'id': m.id, 'status': m.status, 'match_score': m.match_score,
                   'match_reasoning': m.match_reasoning, 'feedback_text': m.feedback_text,
                   'eval_attempts': m.eval_attempts} for m in rows]
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        path = f"/tmp/reeval_backup_{ts}.json"
        with open(path, 'w') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
        for m in rows:
            reset_match(m)
        db.session.commit()
        print(f"\nAPPLIED: {len(rows)} Matches zurückgestellt. Backup: {path}")


if __name__ == '__main__':
    main()
