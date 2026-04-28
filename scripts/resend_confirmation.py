#!/usr/bin/env python3
"""
Resend Confirmation Email für einen User, der seine Bestätigungs-Mail nicht
bekommen hat (z.B. weil MAIL_* zum Anlegezeitpunkt nicht konfiguriert war).

Generiert ein neues Token (24h gültig), löscht alte Tokens für den User und
versendet die Mail erneut.

Usage:
    python scripts/resend_confirmation.py --email anubclaw@gmail.com
"""
import argparse
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from database import db
from models import User, EmailConfirmationToken
from services.email_service import send_confirmation_email


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirmation-Email erneut versenden")
    parser.add_argument("--email", "-e", required=True)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=args.email.lower().strip()).first()
        if not user:
            print(f"✗ User nicht gefunden: {args.email}")
            return 1

        if user.email_confirmed:
            print(f"ℹ️  {user.email} hat Email bereits bestätigt – kein Resend nötig.")
            return 0

        # Alte Tokens für diesen User entfernen
        EmailConfirmationToken.query.filter_by(user_id=user.id).delete()

        # Neues Token
        token = secrets.token_urlsafe(32)
        token_record = EmailConfirmationToken(
            token=token,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(token_record)
        db.session.commit()

        app_url = app.config.get("APP_URL", "https://bewerbungen.wolfinisoftware.de")
        link = f"{app_url}/api/auth/confirm-email?token={token}"

        sent = send_confirmation_email(user.email, link)
        if sent:
            print(f"✅ Bestätigungs-Email an {user.email} versendet.")
            print(f"   Link (für Notfall-Test): {link}")
            return 0

        print(f"✗ Email-Versand fehlgeschlagen. Token bleibt gültig (24h):")
        print(f"   {link}")
        print("   → Diesen Link manuell an den User schicken, oder MAIL_* in .env prüfen.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
