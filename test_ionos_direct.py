#!/usr/bin/env python3
"""
Direkter Test der IONOS SMTP/IMAP Verbindungen
(ohne HTTP-Server - für schnelle Diagnose)
"""

import smtplib
import imaplib
import ssl
import getpass
import sys

EMAIL = "harald.weiss@wolfinisoftware.de"
SMTP_HOST = "smtp.ionos.de"
SMTP_PORT = 465
IMAP_HOST = "imap.ionos.de"
IMAP_PORT = 993

def test_smtp(password):
    """Testet SMTP-Verbindung"""
    try:
        print(f"\n📨 SMTP Test: {SMTP_HOST}:{SMTP_PORT}")
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        server.login(EMAIL, password)
        print("✅ SMTP Authentifizierung erfolgreich!")
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentifizierung fehlgeschlagen: {e}")
        return False
    except Exception as e:
        print(f"❌ SMTP Fehler: {e}")
        return False

def test_imap(password):
    """Testet IMAP-Verbindung"""
    try:
        print(f"\n📥 IMAP Test: {IMAP_HOST}:{IMAP_PORT}")
        context = ssl.create_default_context()
        server = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=context, timeout=10)
        server.login(EMAIL, password)
        print("✅ IMAP Authentifizierung erfolgreich!")
        server.logout()
        return True
    except imaplib.IMAP4.error as e:
        print(f"❌ IMAP Fehler: {e}")
        return False
    except Exception as e:
        print(f"❌ IMAP Verbindungsfehler: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Direkter IONOS SMTP/IMAP Test")
    print("=" * 60)
    print(f"Email: {EMAIL}")

    password = getpass.getpass("\n🔑 IONOS-Passwort eingeben: ")
    if not password:
        print("❌ Passwort erforderlich!")
        sys.exit(1)

    smtp_ok = test_smtp(password)
    imap_ok = test_imap(password)

    print("\n" + "=" * 60)
    if smtp_ok and imap_ok:
        print("✅ Alle Tests erfolgreich!")
        print("\nDie Bewerbungs-App kann jetzt:")
        print("  • Emails versenden (Zusammenfassungen)")
        print("  • Emails abrufen (Responses monitoren)")
    else:
        print("⚠️  Einige Tests fehlgeschlagen")
        if not smtp_ok:
            print("  • SMTP: Überprüfe Passwort und Port 465")
        if not imap_ok:
            print("  • IMAP: Überprüfe Passwort und Port 993")
    print("=" * 60)
