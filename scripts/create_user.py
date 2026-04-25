#!/usr/bin/env python3
"""
User-Helper für non-interaktive Account-Anlage.

Legt einen User mit Envelope-Encryption (Per-User-Salt + verschlüsseltem DEK)
an, optional als Admin und/oder mit umgangener Email-Bestätigung. Nützlich für
Bootstrapping (z.B. um danach `migrate_legacy_data.py` auszuführen) und
Disaster-Recovery.

Usage:
    python scripts/create_user.py --email harald@example.com --password XXX
    python scripts/create_user.py --email a@b.de -p XXX --admin --auto-confirm
"""
import argparse
import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from models import User
from auth_service import AuthService
from services.encryption_service import EncryptionService


def create_user(
    email: str,
    password: str,
    *,
    is_admin: bool = False,
    auto_confirm: bool = False,
    is_active: bool = False,
) -> bool:
    app = create_app()
    with app.app_context():
        if User.query.filter_by(email=email).first():
            print(f"✗ User existiert bereits: {email}")
            return False

        salt, encrypted_dek, _dek = EncryptionService.create_user_keys(password)
        user = User(
            email=email,
            password_hash=AuthService.hash_password(password),
            email_confirmed=auto_confirm,
            is_active=is_active or auto_confirm,  # auto-confirm impliziert active
            is_admin=is_admin,
            encryption_salt=salt,
            encrypted_data_key=encrypted_dek,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"✗ DB-Fehler: {e}")
            return False

        print(f"✓ User angelegt: {email}")
        print(f"   id          = {user.id}")
        print(f"   admin       = {user.is_admin}")
        print(f"   confirmed   = {user.email_confirmed}")
        print(f"   active      = {user.is_active}")
        return True


def main():
    parser = argparse.ArgumentParser(description="User non-interaktiv anlegen")
    parser.add_argument('--email', '-e', required=True, help='Email-Adresse')
    parser.add_argument(
        '--password', '-p',
        help='Passwort (wenn weggelassen: getpass-Prompt)',
    )
    parser.add_argument('--admin', action='store_true', help='Als Admin anlegen')
    parser.add_argument(
        '--auto-confirm', action='store_true',
        help='Email-Confirmation überspringen + Account direkt aktiv',
    )
    args = parser.parse_args()

    if '@' not in args.email or '.' not in args.email:
        print(f"✗ Ungültiges Email-Format: {args.email}")
        sys.exit(1)

    password = args.password or getpass.getpass("Passwort: ")
    if len(password) < 8:
        print("✗ Passwort muss mindestens 8 Zeichen haben")
        sys.exit(1)

    ok = create_user(
        email=args.email,
        password=password,
        is_admin=args.admin,
        auto_confirm=args.auto_confirm,
    )
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
