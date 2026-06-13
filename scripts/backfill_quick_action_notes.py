#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Backfill: reichert nackte Quick-Action-Notizen um Firma/Position/Link an.

Alte Quick-Actions (company_rejected / already_applied) erzeugten nur
`Quick-Action <action> aus JobMatch #<id>` ohne Stellenlink/Kontext. Dieses
Skript löst über die Match-ID den RawJob auf, setzt `Application.link` (falls
leer) und schreibt die selbsterklärende Notiz neu (siehe
`quick_actions._quick_action_note`). Nicht mehr auflösbare Matches werden
übersprungen.

Usage:
    python scripts/backfill_quick_action_notes.py --check   # Dry-run
    python scripts/backfill_quick_action_notes.py           # anwenden
"""
import argparse
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import Application, JobMatch, RawJob
from services.job_matching.quick_actions import _quick_action_note
from services.job_sources.url_resolver import resolve_original_url

_NOTE_RE = re.compile(r"Quick-Action\s+(\w+)\s+aus JobMatch #(\d+)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Dry-run: nur anzeigen")
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = (Application.query
                .filter(Application.notes.like("Quick-Action%aus JobMatch #%"))
                .order_by(Application.id)
                .all())
        print(f"Bare Quick-Action-Notizen: {len(rows)}")

        changed = 0
        for a in rows:
            mobj = _NOTE_RE.search(a.notes or "")
            if not mobj:
                continue
            action, mid = mobj.group(1), int(mobj.group(2))
            m = db.session.get(JobMatch, mid)
            raw = db.session.get(RawJob, m.raw_job_id) if m else None
            if raw is None:
                print(f"  #{a.id}: Match/RawJob #{mid} weg — übersprungen")
                continue
            link = resolve_original_url(raw.url)
            new_note = _quick_action_note(action, raw, m, link)
            if a.notes != new_note or (link and a.link != link):
                changed += 1
                print(f"  #{a.id} {raw.company or '?'}: "
                      f"link={'gesetzt' if not a.link else 'vorhanden'}")
                if not args.check:
                    if link and not a.link:
                        a.link = link
                    a.notes = new_note
            if args.sleep:
                time.sleep(args.sleep)

        if args.check:
            print(f"\n[DRY-RUN] {changed} Notiz(en) würden aktualisiert. Ohne --check anwenden.")
        else:
            db.session.commit()
            print(f"\n✓ {changed} Notiz(en) aktualisiert.")


if __name__ == "__main__":
    main()
