#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Backfill: löst Tracking-/Redirect-Links bestehender Bewerbungen zum Original auf.

E-Mail-Job-Quellen (StepStone/LinkedIn/Indeed) speicherten bisher den
Tracking-Redirect als `Application.link` (z.B. `click.stepstone.de/f/a/…`).
Dieses Skript ersetzt ihn — wo möglich — durch den echten Stellenlink (siehe
`services/job_sources/url_resolver`). Best-effort: was sich nicht auflösen lässt,
bleibt unverändert.

Usage:
    python scripts/backfill_application_links.py --check     # Dry-run: nur anzeigen
    python scripts/backfill_application_links.py             # anwenden
    python scripts/backfill_application_links.py --limit 50 --sleep 0.2
"""
import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import Application
from services.job_sources.url_resolver import resolve_original_url

# Nur diese Tracker-Marker lösen einen (ggf. Netz-)Resolve aus — saubere Links
# bleiben komplett unangetastet (kein unnötiger HTTP-Call).
_TRACKER_MARKERS = (
    "click.stepstone.", "sl.stepstone.", "/comm/jobs/view/",
    "cts.indeed.", "/rc/clk", "/pagead/clk", "utm_", "trackingId",
    "/v2/magiclink",  # StepStone-Magic-Links → öffentliche Anzeigen-URL entpacken
)


def _is_candidate(link) -> bool:
    return bool(link) and any(mark in link for mark in _TRACKER_MARKERS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Dry-run: nur anzeigen")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.2,
                        help="Sekunden zwischen Resolves (Rate-Limit für Redirect-Calls)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = (Application.query
                .filter(Application.link.isnot(None))
                .order_by(Application.id)
                .all())
        candidates = [a for a in rows if _is_candidate(a.link)]
        if args.limit:
            candidates = candidates[:args.limit]
        print(f"Kandidaten (Tracker-Link): {len(candidates)} von {len(rows)} mit Link")

        changed = 0
        for a in candidates:
            old = a.link
            new = resolve_original_url(old)
            if new and new != old:
                changed += 1
                print(f"  #{a.id} {a.company or '?'}:")
                print(f"      alt: {old[:90]}")
                print(f"      neu: {new[:90]}")
                if not args.check:
                    a.link = new
            if args.sleep:
                time.sleep(args.sleep)

        if args.check:
            print(f"\n[DRY-RUN] {changed} Bewerbung(en) würden aktualisiert. "
                  f"Ohne --check anwenden.")
        else:
            db.session.commit()
            print(f"\n✓ {changed} Bewerbung(en) aktualisiert.")


if __name__ == "__main__":
    main()
