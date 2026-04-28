"""DB-Migration für Job-Discovery (Phase A).

Da das Projekt keine Alembic-Migrations nutzt, läuft dies als idempotentes
Init-Skript. db.create_all() legt neue Tabellen an, ALTER TABLE für
Erweiterungen bestehender Tabellen.

Usage:
    FLASK_ENV=production python scripts/migrate_job_discovery.py
"""
import os
import sys
from sqlalchemy import inspect, text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db


NEW_USER_COLUMNS = [
    ("job_discovery_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("job_discovery_requested_at", "DATETIME"),
    ("job_notification_threshold", "INTEGER NOT NULL DEFAULT 80"),
    ("job_claude_budget_per_tick", "INTEGER NOT NULL DEFAULT 5"),
    ("job_daily_budget_cents", "INTEGER NOT NULL DEFAULT 50"),
    ("job_language_filter", 'TEXT DEFAULT \'["de","en"]\''),
    ("job_region_filter", "TEXT"),
]


def add_column_if_missing(table: str, column: str, type_def: str):
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns(table)]
    if column not in cols:
        with db.engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {type_def}'))
        print(f"  + {table}.{column}")
    else:
        print(f"  = {table}.{column} (existiert bereits)")


def main():
    app = create_app()
    with app.app_context():
        print("→ Erstelle neue Tabellen (job_sources, raw_jobs, job_matches)...")
        db.create_all()

        print("→ Erweitere users-Tabelle...")
        for col, type_def in NEW_USER_COLUMNS:
            add_column_if_missing('users', col, type_def)

        print("→ Erweitere api_calls-Tabelle...")
        add_column_if_missing('api_calls', 'key_owner', "VARCHAR(20) NOT NULL DEFAULT 'server'")

        print("✓ Migration abgeschlossen.")


if __name__ == '__main__':
    main()
