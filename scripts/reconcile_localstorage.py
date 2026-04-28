#!/usr/bin/env python3
"""
Reconciler: localStorage-Snapshot → Flask-DB.

Hintergrund: Frontend hat während eines Zeitraums Bewerbungen mit lokal
generierten UUIDs angelegt; PATCH-Requests an /api/applications/<UUID> liefern
404, weil die Flask-DB Legacy-IDs (bew_…) nutzt. Dieses Skript:

  1) Liest einen localStorage-JSON-Export (Array von Bewerbungen mit Feldern
     id, firma, position, status, datum, gehalt, ort, email, quelle, link,
     notizen, createdAt, updatedAt).
  2) Matcht jede gegen die Flask-DB nach (company, position, applied_date).
  3) Falls Match: UPDATE der mutable Felder (status, salary, location,
     contact_email, source, link, notes), DB-ID bleibt erhalten.
  4) Falls kein Match: INSERT mit der UUID aus dem localStorage.
  5) Liefert eine Diff-Zusammenfassung; --dry-run schreibt nichts.

Usage:
    python scripts/reconcile_localstorage.py \\
        --user harald.weiss@wolfinisoftware.de \\
        --json /tmp/localstorage_apps.json \\
        --dry-run
"""
import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from models import User, Application


# Felder, die wir aus localStorage übernehmen (deutsch → englisch).
FIELD_MAP = {
    'status': 'status',
    'gehalt': 'salary',
    'ort': 'location',
    'email': 'contact_email',
    'quelle': 'source',
    'link': 'link',
    'notizen': 'notes',
}


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def normalize(value):
    """Leere Strings → None, sonst gestripped."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def reconcile(json_path: str, user_email: str, *, dry_run: bool) -> int:
    if not Path(json_path).exists():
        print(f"✗ JSON nicht gefunden: {json_path}")
        return 1

    with open(json_path) as f:
        ls_apps = json.load(f)

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f"✗ User nicht gefunden: {user_email}")
            return 1

        print(f"📥 {len(ls_apps)} Bewerbungen aus localStorage")
        print(f"🎯 Ziel-User: {user.email} (id={user.id})")
        print()

        # Indexieren der bestehenden DB-Records nach (company, position, applied_date)
        db_apps = Application.query.filter_by(user_id=user.id).all()
        index = {}
        for a in db_apps:
            key = (a.company.lower(), a.position.lower(), a.applied_date)
            index[key] = a

        updates = []   # (db_app, dict_of_changes)
        inserts = []   # list of dicts to INSERT
        unchanged = 0

        for ls in ls_apps:
            firma = normalize(ls.get('firma'))
            position = normalize(ls.get('position'))
            applied = parse_date(ls.get('datum'))
            if not firma or not position:
                print(f"⚠ skip ungültig: {ls.get('id')} ({firma!r}, {position!r})")
                continue

            key = (firma.lower(), position.lower(), applied)
            existing = index.get(key)

            if existing:
                changes = {}
                for ls_key, db_field in FIELD_MAP.items():
                    new_val = normalize(ls.get(ls_key))
                    old_val = getattr(existing, db_field)
                    if (new_val or '') != (old_val or ''):
                        changes[db_field] = (old_val, new_val)
                if changes:
                    updates.append((existing, changes))
                else:
                    unchanged += 1
            else:
                inserts.append({
                    'id': ls['id'],  # behalten – ist ja UUID, wenn neu
                    'company': firma,
                    'position': position,
                    'status': normalize(ls.get('status')) or 'beworben',
                    'applied_date': applied,
                    'salary': normalize(ls.get('gehalt')),
                    'location': normalize(ls.get('ort')),
                    'contact_email': normalize(ls.get('email')),
                    'source': normalize(ls.get('quelle')),
                    'link': normalize(ls.get('link')),
                    'notes': normalize(ls.get('notizen')),
                    'created_at': parse_datetime(ls.get('createdAt')) or datetime.utcnow(),
                    'updated_at': parse_datetime(ls.get('updatedAt')) or datetime.utcnow(),
                })

        # Reporting
        print(f"  unchanged   : {unchanged}")
        print(f"  to-update   : {len(updates)}")
        print(f"  to-insert   : {len(inserts)}")
        print()

        if updates:
            print("── UPDATES ──────────────────────────────────────────────────")
            for app_obj, changes in updates:
                print(f"  {app_obj.company} | {app_obj.position}")
                for field, (old, new) in changes.items():
                    o = (old or '')[:60] + ('…' if old and len(old) > 60 else '')
                    n = (new or '')[:60] + ('…' if new and len(new) > 60 else '')
                    print(f"      {field:14s}: {o!r}  →  {n!r}")
            print()

        if inserts:
            print("── INSERTS ──────────────────────────────────────────────────")
            for ins in inserts:
                print(f"  {ins['company']} | {ins['position']} | {ins['status']} | {ins['applied_date']}")
            print()

        if dry_run:
            print("🔎 DRY-RUN – keine Änderungen geschrieben.")
            return 0

        # APPLY
        for app_obj, changes in updates:
            for field, (_, new) in changes.items():
                setattr(app_obj, field, new)
            app_obj.updated_at = datetime.utcnow()

        for ins in inserts:
            db.session.add(Application(user_id=user.id, **ins))

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"✗ Reconcile fehlgeschlagen: {e}")
            return 1

        print(f"✅ {len(updates)} updates + {len(inserts)} inserts geschrieben.")

        # Sanity-Counts
        from sqlalchemy import func
        total = Application.query.filter_by(user_id=user.id, deleted=False).count()
        rows = (
            db.session.query(Application.status, func.count(Application.id))
            .filter_by(user_id=user.id, deleted=False)
            .group_by(Application.status)
            .all()
        )
        print()
        print(f"📊 Total aktive Bewerbungen: {total}")
        for status, count in rows:
            print(f"   {status:12s} {count}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="localStorage → Flask-DB Reconciler")
    parser.add_argument('--user', '-u', required=True)
    parser.add_argument('--json', '-j', required=True, help='Pfad zum localStorage-JSON-Export')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    sys.exit(reconcile(args.json, args.user, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
