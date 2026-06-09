# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Email sending service – nutzt Flask-Mail mit SMTP-Credentials aus .env.

Robust gegen Service-Restart (kein Master-Passwort nötig). Der separate
email_service.py-Daemon (Port 8766) kümmert sich nur noch um IMAP-Monitoring
für Bewerbungs-Antworten, NICHT mehr um Confirmation-Mail-Versand.
"""

import os
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask_mail import Mail
from flask import current_app

logger = logging.getLogger(__name__)

# Flask-Mail bleibt initialisierbar (für Tests / app.config-Konsistenz).
mail = Mail()


def init_email(app):
    mail.init_app(app)


def _send_via_smtp(recipient: str, subject: str, html_body: str) -> bool:
    """Direkter SMTP-Versand mit Credentials aus app.config (.env-vars)."""
    cfg = current_app.config
    host = cfg.get('MAIL_SERVER')
    port = int(cfg.get('MAIL_PORT', 0))
    user = cfg.get('MAIL_USERNAME')
    password = cfg.get('MAIL_PASSWORD')
    sender = cfg.get('MAIL_DEFAULT_SENDER', user)

    if not (host and port and user and password):
        logger.error(
            "SMTP-Konfiguration unvollständig (MAIL_SERVER/PORT/USERNAME/PASSWORD).")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ctx) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(user, password)
                server.send_message(msg)
        logger.info("Email an %s gesendet (subject=%s)", recipient, subject)
        return True
    except Exception as e:
        logger.error("SMTP-Versand fehlgeschlagen an %s: %s", recipient, e)
        return False


def send_confirmation_email(user_email: str, confirmation_link: str) -> bool:
    """Bestätigungs-Email mit Aktivierungs-Link an den User."""
    subject = "📋 Konto aktivieren – Bewerbungs-Tracker"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Willkommen bei Bewerbungs-Tracker! 📋</h2>
            <p>Ein Konto für <strong>{user_email}</strong> wurde angelegt. Bitte
               bestätigen Sie Ihre Email-Adresse, um sich einloggen zu können.</p>
            <p>
                <a href="{confirmation_link}" style="background-color: #4F46E5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Konto aktivieren
                </a>
            </p>
            <p>Falls der Button nicht funktioniert, kopieren Sie diesen Link:<br>
               <code style="font-size: 12px;">{confirmation_link}</code></p>
            <p>Der Link ist 24 Stunden gültig.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker</p>
        </body>
    </html>
    """
    return _send_via_smtp(user_email, subject, html_body)


def send_admin_new_user_notification(new_user_email: str, ip: str = '', user_agent: str = '') -> bool:
    """Notification an den Admin (env ADMIN_NOTIFICATION_EMAIL) wenn ein neuer
    User sich registriert. No-op wenn ADMIN_NOTIFICATION_EMAIL nicht gesetzt."""
    import os
    admin_email = os.getenv('ADMIN_NOTIFICATION_EMAIL', '').strip()
    if not admin_email:
        return False
    subject = f"🆕 Neue Registrierung: {new_user_email}"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Neue User-Registrierung</h2>
            <p>Email: <strong>{new_user_email}</strong></p>
            <p>IP: <code>{ip or 'unbekannt'}</code></p>
            <p>User-Agent: <code style="font-size:11px;">{(user_agent or 'unbekannt')[:200]}</code></p>
            <hr>
            <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker · Admin-Notification</p>
        </body>
    </html>
    """
    return _send_via_smtp(admin_email, subject, html_body)


def send_approval_notification(user_email: str) -> bool:
    """Notification dass Account vom Admin freigeschaltet wurde."""
    app_url = current_app.config.get('APP_URL', 'https://bewerbungen.wolfinisoftware.de')
    subject = "✓ Konto freigeschaltet – Bewerbungs-Tracker"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Konto freigeschaltet! ✓</h2>
            <p>Ihr Konto wurde vom Administrator freigeschaltet. Sie können sich jetzt anmelden.</p>
            <p>
                <a href="{app_url}" style="background-color: #10B981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Zur App
                </a>
            </p>
            <hr>
            <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker</p>
        </body>
    </html>
    """
    return _send_via_smtp(user_email, subject, html_body)


def send_password_reset_email(user_email: str, reset_link: str) -> bool:
    """Passwort-Reset-Link per E-Mail."""
    subject = "Passwort zurücksetzen – Bewerbungs-Tracker"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Passwort zurücksetzen</h2>
            <p>Hallo,</p>
            <p>Klicke auf den folgenden Link, um ein neues Passwort zu setzen (gültig 1 Stunde):</p>
            <p>
                <a href="{reset_link}" style="background-color: #3B82F6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Passwort zurücksetzen
                </a>
            </p>
            <p style="margin-top: 20px;"><small>Falls du keinen Reset angefordert hast, ignoriere diese Email.</small></p>
            <hr>
            <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker</p>
        </body>
    </html>
    """
    return _send_via_smtp(user_email, subject, html_body)
