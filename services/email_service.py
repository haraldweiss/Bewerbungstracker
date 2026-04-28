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
