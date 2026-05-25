#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Löscht User mit email_confirmed=0, die älter als N Tage sind.

Schützt vor DB-Bloat durch Bot-Registrierungen. Token-Records (FK) werden
mitgelöscht.

Nutzung:
    venv/bin/python scripts/cleanup_unconfirmed_users.py [--days 7] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Pfad-Setup damit das Script aus dem Repo-Root lauffähig ist.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import User, EmailConfirmationToken


def cleanup(days: int, dry_run: bool) -> int:
    """Returns Anzahl gelöschter User."""
    threshold = datetime.utcnow() - timedelta(days=days)
    q = User.query.filter(
        User.email_confirmed == False,  # noqa: E712 (SQLAlchemy-Idiom)
        User.is_active == False,        # noqa: E712
        User.is_admin == False,         # noqa: E712  Defense-in-depth: nie Admins löschen
        User.created_at < threshold,
    )
    victims = q.all()
    print(f"[{datetime.utcnow().isoformat()}Z] Threshold: created_at < {threshold.isoformat()}Z ({days}d)")
    print(f"Kandidaten: {len(victims)}")
    for u in victims:
        print(f"  - {u.email}  created={u.created_at}")
    if dry_run or not victims:
        print("dry-run oder leer — keine Änderungen.")
        return 0
    # FK-Cleanup: Tokens vorher löschen
    for u in victims:
        n = EmailConfirmationToken.query.filter_by(user_id=u.id).delete()
        if n:
            print(f"  → {n} Tokens für {u.email} gelöscht")
        db.session.delete(u)
    db.session.commit()
    print(f"✓ {len(victims)} User gelöscht.")
    return len(victims)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=7,
                        help='Lösche User älter als N Tage (default: 7)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Nur ausgeben, nichts löschen.')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        cleanup(args.days, args.dry_run)


if __name__ == '__main__':
    main()
