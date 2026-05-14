# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""DB-Migration: Konvertiere 'seen' Status zu 'unbewertet' in JobMatch Tabelle.

Da das Projekt keine Alembic-Migrations nutzt, läuft dies als idempotentes
Init-Skript. Konvertiert alle existierenden 'seen' Status zu 'unbewertet'.

Usage:
    FLASK_ENV=production python scripts/migrate_seen_to_unbewertet.py

Rollback (falls nötig):
    FLASK_ENV=production python scripts/migrate_seen_to_unbewertet.py --rollback
"""
import os
import sys
import argparse
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db


def migrate_to_unbewertet():
    """Konvertiere 'seen' Status zu 'unbewertet'."""
    result = db.session.execute(
        text("UPDATE job_matches SET status = 'unbewertet' WHERE status = 'seen'")
    )
    db.session.commit()
    return result.rowcount


def rollback_to_seen():
    """Rollback: Konvertiere 'unbewertet' Status zurück zu 'seen'.

    WARNUNG: Dies rollback nur STATUS-Änderungen. Kann nicht zwischen
    'unbewertet' unterscheiden, das der User aktiv gesetzt hat vs.
    das automatisch migriert wurde.
    """
    result = db.session.execute(
        text("UPDATE job_matches SET status = 'seen' WHERE status = 'unbewertet'")
    )
    db.session.commit()
    return result.rowcount


def check_status_distribution():
    """Zeige die aktuelle Verteilung der Status in der Tabelle."""
    result = db.session.execute(
        text("""
            SELECT status, COUNT(*) as count
            FROM job_matches
            GROUP BY status
            ORDER BY count DESC
        """)
    )
    return result.fetchall()


def main():
    parser = argparse.ArgumentParser(
        description='Migrate JobMatch seen status to unbewertet'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback migration (convert unbewertet back to seen)'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check current status distribution without making changes'
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print("→ Prüfe JobMatch Status-Verteilung...")
        distribution = check_status_distribution()

        if not distribution:
            print("  ℹ Keine JobMatch-Einträge in DB gefunden")
            return

        print("  Status-Verteilung vorher:")
        for status, count in distribution:
            print(f"    - {status or '(null)'}: {count}")

        if args.check_only:
            print("✓ Nur Überprüfung, keine Änderungen gemacht.")
            return

        if args.rollback:
            print("\n→ Rollback: Konvertiere 'unbewertet' zurück zu 'seen'...")
            rows_affected = rollback_to_seen()
            print(f"✓ {rows_affected} Einträge konvertiert.")
        else:
            print("\n→ Migration: Konvertiere 'seen' zu 'unbewertet'...")
            rows_affected = migrate_to_unbewertet()
            print(f"✓ {rows_affected} Einträge konvertiert.")

        print("\n→ Prüfe Status-Verteilung nach Migration...")
        distribution = check_status_distribution()
        print("  Status-Verteilung nachher:")
        for status, count in distribution:
            print(f"    - {status or '(null)'}: {count}")

        print("\n✓ Migration abgeschlossen.")


if __name__ == '__main__':
    main()
