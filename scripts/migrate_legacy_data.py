#!/usr/bin/env python3
"""
Migration: bewerbungen.db.bak (Legacy SQLite) → Flask-DB (SQLAlchemy).

Liest die Tabelle `bewerbungen` aus der alten data_service.py-DB und legt für
jeden Eintrag eine `Application` mit der user_id eines existierenden Users an.
Mapping (Legacy → Flask):

    firma          → company
    position       → position
    status         → status        (deutsche Werte 1:1 übernommen)
    datum          → applied_date  (ISO-Date oder NULL)
    gehalt         → salary
    ort            → location
    email          → contact_email
    quelle         → source
    link           → link
    notizen        → notes
    deleted        → deleted
    deletedAt      → deleted_at
    createdAt      → created_at
    updatedAt      → updated_at
    id             → id            (TEXT, beibehalten – sonst brechen Backup-IDs)

Usage:
    python scripts/migrate_legacy_data.py \\
        --user harald@example.com \\
        --legacy-db bewerbungen.db.bak \\
        [--dry-run] [--include-deleted]
"""
import argparse
import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from models import User, Application


def parse_date(value):
    """Legacy-Datum kann '', None, ISO oder ISO-mit-Zeit sein."""
    if not value:
        return None
    try:
        # Volle ISO-Timestamp
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])  # nur YYYY-MM-DD
        except ValueError:
            return None


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def migrate(legacy_db_path: str, user_email: str, *, dry_run: bool, include_deleted: bool) -> int:
    """Returns: Exit-Code (0=ok, sonst Fehler)."""
    if not Path(legacy_db_path).exists():
        print(f"✗ Legacy-DB nicht gefunden: {legacy_db_path}")
        return 1

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f"✗ User nicht gefunden: {user_email}")
            print("  Tipp: erst anlegen mit scripts/create_user.py")
            return 1

        legacy = sqlite3.connect(legacy_db_path)
        legacy.row_factory = sqlite3.Row
        cursor = legacy.cursor()

        where = "" if include_deleted else "WHERE deleted = 0"
        rows = cursor.execute(f"SELECT * FROM bewerbungen {where}").fetchall()
        print(f"📥 {len(rows)} Bewerbungen aus {legacy_db_path}")
        print(f"🎯 Ziel-User: {user.email} (id={user.id})")
        print()

        # ID-Kollisions-Check: nichts überschreiben
        existing_ids = {
            a.id for a in Application.query.filter_by(user_id=user.id).all()
        }

        created = 0
        skipped_existing = 0
        skipped_invalid = 0
        new_applications = []

        for r in rows:
            legacy_id = r['id']
            if legacy_id in existing_ids:
                skipped_existing += 1
                continue

            firma = (r['firma'] or '').strip()
            position = (r['position'] or '').strip()
            if not firma or not position:
                print(f"  ⚠ skip {legacy_id}: firma/position leer")
                skipped_invalid += 1
                continue

            applied_date = parse_date(r['datum'])
            created_at = parse_datetime(r['createdAt']) or datetime.utcnow()
            updated_at = parse_datetime(r['updatedAt']) or created_at
            deleted_at = parse_datetime(r['deletedAt'])

            new_app = Application(
                id=legacy_id,
                user_id=user.id,
                company=firma,
                position=position,
                status=(r['status'] or 'beworben').strip(),
                applied_date=applied_date,
                salary=(r['gehalt'] or '').strip() or None,
                location=(r['ort'] or '').strip() or None,
                contact_email=(r['email'] or '').strip() or None,
                source=(r['quelle'] or '').strip() or None,
                link=(r['link'] or '').strip() or None,
                notes=(r['notizen'] or '').strip() or None,
                deleted=bool(r['deleted']),
                deleted_at=deleted_at,
                created_at=created_at,
                updated_at=updated_at,
            )
            new_applications.append(new_app)
            created += 1

        legacy.close()

        if dry_run:
            print(f"🔎 DRY-RUN: würde {created} Bewerbungen anlegen")
            print(f"   übersprungen (bereits vorhanden): {skipped_existing}")
            print(f"   übersprungen (ungültig):          {skipped_invalid}")
            print()
            for a in new_applications[:5]:
                print(f"   - {a.company} | {a.position} | {a.status} | {a.applied_date}")
            if len(new_applications) > 5:
                print(f"   ... +{len(new_applications) - 5} weitere")
            return 0

        try:
            db.session.add_all(new_applications)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"✗ Migration fehlgeschlagen: {e}")
            return 1

        print(f"✅ {created} Bewerbungen migriert")
        print(f"   übersprungen (bereits vorhanden): {skipped_existing}")
        print(f"   übersprungen (ungültig):          {skipped_invalid}")

        # Statusverteilung als Sanity-Check
        from sqlalchemy import func
        rows = (
            db.session.query(Application.status, func.count(Application.id))
            .filter_by(user_id=user.id, deleted=False)
            .group_by(Application.status)
            .all()
        )
        print()
        print("📊 Statusverteilung nach Migration:")
        for status, count in rows:
            print(f"   {status:12s} {count}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Legacy-Bewerbungen → Flask-DB")
    parser.add_argument('--user', '-u', required=True, help='Ziel-User (email)')
    parser.add_argument('--legacy-db', '-l', default='bewerbungen.db.bak',
                       help='Pfad zur Legacy-DB (default: bewerbungen.db.bak)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Nichts schreiben, nur ausgeben was passieren würde')
    parser.add_argument('--include-deleted', action='store_true',
                       help='Auch soft-gelöschte Bewerbungen migrieren')
    args = parser.parse_args()

    sys.exit(migrate(
        args.legacy_db, args.user,
        dry_run=args.dry_run,
        include_deleted=args.include_deleted,
    ))


if __name__ == '__main__':
    main()
