#!/usr/bin/env python3
"""
IONOS Email Setup für Bewerbungs-Tracker
Konfiguriert SMTP (Versand) und IMAP (Abruf) mit verschlüsselten Credentials
"""

import requests
import json
import getpass
import sys

EMAIL = "harald.weiss@wolfinisoftware.de"
SMTP_HOST = "smtp.ionos.de"
SMTP_PORT = 465
IMAP_HOST = "imap.ionos.de"
IMAP_PORT = 993

# Email Service läuft auf Port 8766
API_URL = "http://127.0.0.1:8766"

def save_credentials(service, host, port, user, password, master_password):
    """Speichert Credentials über API mit Verschlüsselung"""
    url = f"{API_URL}/api/credentials/save"
    payload = {
        "service": service,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "master_password": master_password
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"✅ {service.upper()}: {data.get('message', 'erfolgreich gespeichert')}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ Fehler: Email Service läuft nicht auf Port 8766")
        print("   Starte zuerst: python3 email_service.py")
        return False
    except Exception as e:
        print(f"❌ {service.upper()} Fehler: {e}")
        return False

def test_credentials(service, host, port, user, password):
    """Testet die Credentials"""
    url = f"{API_URL}/api/credentials/test"
    payload = {
        "service": service,
        "host": host,
        "port": port,
        "user": user,
        "password": password
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        if response.status_code == 200:
            print(f"✅ {service.upper()} Test erfolgreich: {data.get('message')}")
            return True
        else:
            print(f"❌ {service.upper()} Test fehlgeschlagen: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Verbindungsfehler: {e}")
        return False

def main():
    print("=" * 60)
    print("🔧 IONOS Email Setup für Bewerbungs-Tracker")
    print("=" * 60)
    print(f"\n📧 Email: {EMAIL}")
    print(f"🔒 SMTP: {SMTP_HOST}:{SMTP_PORT}")
    print(f"📨 IMAP: {IMAP_HOST}:{IMAP_PORT}\n")

    # IONOS-Passwort abfragen
    ionos_password = getpass.getpass("🔑 IONOS-Passwort eingeben: ")
    if not ionos_password:
        print("❌ Passwort erforderlich!")
        return False

    # Master-Passwort für Verschlüsselung
    print("\n🔐 Verschlüsselung konfigurieren:")
    master_password = getpass.getpass("Master-Passwort eingeben (für lokale Verschlüsselung): ")
    if not master_password:
        print("❌ Master-Passwort erforderlich!")
        return False

    master_password_confirm = getpass.getpass("Master-Passwort bestätigen: ")
    if master_password != master_password_confirm:
        print("❌ Passwörter stimmen nicht überein!")
        return False

    print("\n⏳ Konfiguriere Credentials...\n")

    # SMTP speichern
    if not save_credentials("smtp", SMTP_HOST, SMTP_PORT, EMAIL, ionos_password, master_password):
        return False

    # IMAP speichern
    if not save_credentials("imap", IMAP_HOST, IMAP_PORT, EMAIL, ionos_password, master_password):
        return False

    # Optional: Credentials testen
    print("\n🧪 Teste Verbindungen...\n")
    smtp_ok = test_credentials("smtp", SMTP_HOST, SMTP_PORT, EMAIL, ionos_password)
    imap_ok = test_credentials("imap", IMAP_HOST, IMAP_PORT, EMAIL, ionos_password)

    if smtp_ok and imap_ok:
        print("\n" + "=" * 60)
        print("✅ IONOS Email Setup erfolgreich abgeschlossen!")
        print("=" * 60)
        print("\n📝 Nächste Schritte:")
        print("1. Email-Versand testen: POST /api/email/test")
        print("2. Monitoring aktivieren: POST /api/monitoring/enable")
        print("3. Zusammenfassungen konfigurieren: POST /api/config/save")
        return True
    else:
        print("\n⚠️  Einige Tests fehlgeschlagen. Überprüfe deine Credentials.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
