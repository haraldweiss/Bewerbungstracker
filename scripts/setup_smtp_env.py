#!/usr/bin/env python3
"""
Konfiguriert die MAIL_*-Variablen in /var/www/bewerbungen/.env interaktiv.

Hintergrund: Manche Markdown-Renderer wandeln URLs/Email-Adressen in
Klammer-Links um, sobald man Befehle aus dem Browser kopiert. Resultat:
".env" enthält dann z.B. `MAIL_SERVER=[smtp.ionos.de](http://...)` statt
des reinen Werts. Dieses Skript umgeht das Problem, indem die Werte
hartkodiert im Skript stehen und das Passwort interaktiv via getpass
abgefragt wird – kein Copy-Paste nötig.

Usage:
    venv/bin/python scripts/setup_smtp_env.py
    # Optional: andere Werte
    venv/bin/python scripts/setup_smtp_env.py \\
        --server smtp.gmail.com --port 587 \\
        --username you@gmail.com
"""
import argparse
import getpass
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="SMTP-Config in .env schreiben")
    parser.add_argument("--env-file", default="/var/www/bewerbungen/.env")
    parser.add_argument("--server", default="smtp.ionos.de")
    parser.add_argument("--port", type=int, default=465)
    parser.add_argument("--username", default="harald.weiss@wolfinisoftware.de")
    parser.add_argument(
        "--sender",
        default=None,
        help="Default sender-Adresse (default: --username)",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Nach dem Schreiben `systemctl restart bewerbungen` ausführen",
    )
    args = parser.parse_args()

    env_file = Path(args.env_file)
    sender = args.sender or args.username

    if os.geteuid() != 0:
        print("✗ Bitte als root ausführen (sudo).", file=sys.stderr)
        return 1

    print(f"SMTP-Config für {env_file}")
    print(f"  Server  : {args.server}")
    print(f"  Port    : {args.port}")
    print(f"  Username: {args.username}")
    print(f"  Sender  : {sender}")
    print()
    password = getpass.getpass("Passwort (nicht sichtbar): ")
    if not password:
        print("✗ Passwort erforderlich.", file=sys.stderr)
        return 1
    confirm = getpass.getpass("Passwort bestätigen      : ")
    if password != confirm:
        print("✗ Passwörter stimmen nicht überein.", file=sys.stderr)
        return 1

    # Bestehende MAIL_*-Zeilen entfernen (auch Markdown-zerstörte wie [MAIL_…)
    if env_file.exists():
        old_lines = env_file.read_text().splitlines()
    else:
        old_lines = []

    cleaned = []
    removed = 0
    for line in old_lines:
        stripped = line.lstrip()
        if stripped.startswith("MAIL_") or stripped.startswith("[MAIL_"):
            removed += 1
            continue
        cleaned.append(line)

    # Trailing leere Zeilen abräumen, dann frischen Block anhängen
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    cleaned.append("")
    cleaned.append("# SMTP – konfiguriert via scripts/setup_smtp_env.py")
    cleaned.append(f"MAIL_SERVER={args.server}")
    cleaned.append(f"MAIL_PORT={args.port}")
    cleaned.append(f"MAIL_USERNAME={args.username}")
    cleaned.append(f"MAIL_PASSWORD={password}")
    cleaned.append(f"MAIL_DEFAULT_SENDER={sender}")
    cleaned.append("")

    env_file.write_text("\n".join(cleaned))
    env_file.chmod(0o600)
    print(f"✓ {env_file} geschrieben (mode 600), {removed} alte MAIL_*-Zeile(n) entfernt.")

    if args.restart:
        ret = os.system("systemctl restart bewerbungen")
        if ret != 0:
            print("✗ systemctl restart fehlgeschlagen", file=sys.stderr)
            return 1
        print("✓ bewerbungen.service neu gestartet.")
    else:
        print("ℹ️  systemctl restart bewerbungen   # nicht vergessen!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
