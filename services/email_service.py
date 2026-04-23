"""Email sending service for Bewerbungstracker"""

from flask_mail import Mail, Message
from flask import current_app, url_for
import os

mail = Mail()


def init_email(app):
    """Initialize email with Flask app"""
    mail.init_app(app)


def send_confirmation_email(user_email: str, confirmation_link: str) -> bool:
    """Send email confirmation link to user"""
    try:
        subject = "📋 Email-Bestätigung - Bewerbungs-Tracker"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>Willkommen bei Bewerbungs-Tracker! 📋</h2>
                <p>Bitte bestätigen Sie Ihre Email-Adresse, um Ihr Konto zu aktivieren.</p>
                <p>
                    <a href="{confirmation_link}" style="background-color: #4F46E5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Email bestätigen
                    </a>
                </p>
                <p>Oder kopieren Sie diesen Link: <br><code>{confirmation_link}</code></p>
                <p>Dieser Link ist 24 Stunden gültig.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker</p>
            </body>
        </html>
        """

        msg = Message(
            subject=subject,
            recipients=[user_email],
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@bewerbungstracker.de')
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def send_approval_notification(user_email: str) -> bool:
    """Notify user that their account has been approved"""
    try:
        subject = "✓ Konto genehmigt - Bewerbungs-Tracker"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>Konto genehmigt! ✓</h2>
                <p>Ihr Konto wurde vom Administrator genehmigt. Sie können sich jetzt anmelden.</p>
                <p>
                    <a href="{current_app.config.get('APP_URL', 'https://bewerbungen.wolfinisoftware.de')}/login" style="background-color: #10B981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Anmelden
                    </a>
                </p>
                <hr>
                <p style="color: #666; font-size: 12px;">Bewerbungs-Tracker</p>
            </body>
        </html>
        """

        msg = Message(
            subject=subject,
            recipients=[user_email],
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@bewerbungstracker.de')
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
