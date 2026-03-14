#!/usr/bin/env python3
"""
Bewerbungs-Tracker – Email Service
===================================
Automatischer Versand von Email-Zusammenfassungen via SMTP
+ Automatischer Email-Monitor für Antworten auf Bewerbungen

Start: python3 email_service.py
Port: 8766 (REST API)
"""

import json
import smtplib
import sqlite3
import threading
import time
import os
import imaplib
import email
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import ssl

HOST = '127.0.0.1'
PORT = 8766
DB_FILE = 'email_config.db'

# ── Database ───────────────────────────────────────────────────────────

def init_db():
    """Initialize SQLite database for email configuration"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS email_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS email_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT,
        subject TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        error TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS email_monitoring (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_sender TEXT,
        subject TEXT,
        company_name TEXT,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        email_uid TEXT UNIQUE
    )''')

    conn.commit()
    conn.close()

def get_config(key, default=''):
    """Get configuration value from database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM email_config WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
    except Exception as e:
        print(f"Error reading config: {e}")
        return default

def set_config(key, value):
    """Save configuration value to database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO email_config (key, value) VALUES (?, ?)',
                      (key, value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def log_email(recipient, subject, status, error=''):
    """Log email send attempt"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO email_log (recipient, subject, status, error) VALUES (?, ?, ?, ?)',
                      (recipient, subject, status, error))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging email: {e}")

# ── Email Sending ──────────────────────────────────────────────────────

def send_email(recipient, subject, html_body, text_body=''):
    """Send email via SMTP"""
    try:
        smtp_host = get_config('smtp_host', 'smtp.gmail.com')
        smtp_port = int(get_config('smtp_port', '587'))
        smtp_user = get_config('smtp_user')
        smtp_pass = get_config('smtp_pass')

        if not smtp_user or not smtp_pass:
            error = "SMTP credentials not configured"
            print(f"❌ {error}")
            log_email(recipient, subject, 'failed', error)
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = recipient

        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # Send via SMTP
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()

        print(f"✅ Email versendet: {recipient}")
        log_email(recipient, subject, 'success')
        return True

    except smtplib.SMTPAuthenticationError as e:
        error = f"SMTP Authentication failed: {str(e)}"
        print(f"❌ {error}")
        log_email(recipient, subject, 'failed', error)
        return False
    except Exception as e:
        error = f"Error sending email: {str(e)}"
        print(f"❌ {error}")
        log_email(recipient, subject, 'failed', error)
        return False

# ── Schedule Check ────────────────────────────────────────────────────

def should_send_summary():
    """Check if email summary should be sent based on schedule"""
    try:
        enabled = get_config('summary_enabled') == 'true'
        if not enabled:
            return False

        frequency = get_config('summary_frequency', 'weekly')
        last_sent_str = get_config('last_sent')

        if not last_sent_str:
            return True  # Never sent before

        last_sent = datetime.fromisoformat(last_sent_str)
        now = datetime.now()

        if frequency == 'daily':
            return now.date() > last_sent.date()
        elif frequency == 'weekly':
            days_diff = (now - last_sent).days
            return days_diff >= 7
        elif frequency == 'monthly':
            return (now.year != last_sent.year or
                   now.month != last_sent.month)

        return False
    except Exception as e:
        print(f"Error checking schedule: {e}")
        return False

def check_and_send_summary(html_content='', text_content=''):
    """Check schedule and send summary if needed"""
    if not should_send_summary():
        return False

    recipient = get_config('summary_recipient')
    if not recipient:
        print("⚠️  No recipient configured for email summary")
        return False

    subject = f"📋 Bewerbungs-Tracker Zusammenfassung - {datetime.now().strftime('%d.%m.%Y')}"

    # Use provided content or default message
    if not html_content:
        html_content = """
        <html style="font-family:Arial,sans-serif;">
        <body style="background:#f5f5f5;padding:20px;">
        <div style="background:white;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;">
            <h1 style="color:#4F46E5;">📋 Bewerbungs-Tracker Zusammenfassung</h1>
            <p>Deine Bewerbungs-Zusammenfassung ist bereit.</p>
            <p>Öffne die App um die Details zu sehen: <a href="http://localhost:8080" style="color:#4F46E5;">Zur App</a></p>
        </div>
        </body>
        </html>
        """

    if send_email(recipient, subject, html_content, text_content):
        set_config('last_sent', datetime.now().isoformat())
        return True

    return False

# ── Email Monitoring ──────────────────────────────────────────────────

def fetch_imap_emails():
    """Fetch recent emails from IMAP for monitoring"""
    try:
        imap_host = get_config('imap_host')
        imap_port = get_config('imap_port', '993')
        imap_user = get_config('imap_user')
        imap_pass = get_config('imap_pass')

        if not imap_host or not imap_user or not imap_pass:
            return []

        # Connect to IMAP
        if imap_port == '993':
            imap = imaplib.IMAP4_SSL(imap_host, int(imap_port), context=ssl.create_default_context())
        else:
            imap = imaplib.IMAP4(imap_host, int(imap_port))
            imap.starttls()

        imap.login(imap_user, imap_pass)
        imap.select('INBOX')

        # Fetch emails from last 7 days
        since_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
        status, messages = imap.search(None, f'SINCE {since_date}')

        emails = []
        for msg_id in messages[0].split():
            status, msg_data = imap.fetch(msg_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])

            emails.append({
                'uid': msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                'from': msg.get('From', ''),
                'subject': msg.get('Subject', ''),
                'date': msg.get('Date', ''),
            })

        imap.close()
        imap.logout()
        return emails

    except Exception as e:
        print(f"❌ IMAP fetch error: {e}")
        return []

def get_applications_list():
    """Get list of applications from the Bewerbungstracker app"""
    try:
        # Try to read from localStorage backup if available
        apps_file = 'applications_cache.json'
        if os.path.exists(apps_file):
            with open(apps_file, 'r') as f:
                data = json.load(f)
                return data.get('bewerbungen', [])
    except Exception as e:
        print(f"Note: Could not load applications cache: {e}")
    return []

def normalize_company_name(name):
    """Normalize company name for matching"""
    if not name:
        return ""
    return name.lower().strip().replace('gmbh', '').replace('ag', '').replace('ltd', '').replace('inc', '')

def check_email_for_application(email_data, applications):
    """Check if email is a response to an application"""
    from_sender = email_data.get('from', '').lower()
    subject = email_data.get('subject', '').lower()

    matched_app = None

    for app in applications:
        company_name = app.get('firma', '')
        if not company_name:
            continue

        # Check if sender or subject contains company name
        normalized_company = normalize_company_name(company_name)

        if normalized_company and normalized_company in from_sender:
            matched_app = app
            break
        if normalized_company and normalized_company in subject:
            matched_app = app
            break

        # Check for common sender domains if email is from company
        parts = from_sender.split('@')
        if len(parts) > 1:
            domain = parts[1]
            if normalized_company.replace(' ', '') in domain:
                matched_app = app
                break

    return matched_app

def log_monitoring_email(email_data, company_name, status):
    """Log detected application response email"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('''INSERT OR IGNORE INTO email_monitoring
                        (from_sender, subject, company_name, status, email_uid)
                        VALUES (?, ?, ?, ?, ?)''',
                      (email_data.get('from'),
                       email_data.get('subject'),
                       company_name,
                       status,
                       email_data.get('uid')))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging monitoring email: {e}")

def check_and_monitor_emails():
    """Check for application responses and notify"""
    if not get_config('email_monitoring_enabled') == 'true':
        return

    print("📧 Checking for application responses...")

    # Fetch recent emails
    recent_emails = fetch_imap_emails()
    applications = get_applications_list()

    detected_responses = []

    for email_data in recent_emails:
        matched_app = check_email_for_application(email_data, applications)

        if matched_app:
            log_monitoring_email(email_data, matched_app.get('firma'), 'detected')
            detected_responses.append({
                'company': matched_app.get('firma'),
                'from': email_data.get('from'),
                'subject': email_data.get('subject')
            })
            print(f"✅ Application response detected from: {matched_app.get('firma')}")

    # Send notification if responses found
    if detected_responses and get_config('monitoring_notify') == 'true':
        notify_monitoring_results(detected_responses)

    return detected_responses

def notify_monitoring_results(responses):
    """Send notification about detected responses"""
    count = len(responses)
    companies = ', '.join([r['company'] for r in responses[:3]])

    subject = f"🎯 {count} Antwort(en) auf Bewerbung(en) erkannt!"
    html_body = f"""
    <html style="font-family:Arial,sans-serif;">
    <body style="background:#f5f5f5;padding:20px;">
    <div style="background:white;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;">
        <h1 style="color:#10B981;margin-bottom:10px;">🎯 Neue Antworten erkannt!</h1>
        <p style="color:#333;margin-bottom:10px;">Es wurden <strong>{count}</strong> neue Antwort(en) auf deine Bewerbung(en) erkannt:</p>
        <ul style="color:#333;">
            {chr(10).join([f'<li><strong>{r["company"]}</strong><br><small style="color:#666;">{r["from"]}</small></li>' for r in responses])}
        </ul>
        <p style="color:#666;margin-top:20px;">Öffne die App um alle Details zu sehen: <a href="http://localhost:8080" style="color:#10B981;text-decoration:none;"><strong>Zur App →</strong></a></p>
    </div>
    </body>
    </html>
    """

    recipient = get_config('monitoring_recipient') or get_config('summary_recipient')
    if recipient:
        send_email(recipient, subject, html_body)

# ── HTTP Handler ───────────────────────────────────────────────────────

class EmailServiceHandler(BaseHTTPRequestHandler):
    def _check_origin(self):
        """Verify request origin (CSRF protection)"""
        origin = self.headers.get('Origin', '')
        host = self.headers.get('Host', '')

        # Allow localhost/127.0.0.1 only
        if origin and 'localhost' not in origin and '127.0.0.1' not in origin:
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'CORS policy violation'}).encode())
            return False

        return True

    def do_POST(self):
        """Handle POST requests"""
        # CSRF Protection: Check origin
        if not self._check_origin():
            return

        content_length = int(self.headers.get('Content-Length', 0))

        # Security: Limit request body size (max 1MB)
        if content_length > 1024 * 1024:
            self.send_response(413)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'Request body too large'}).encode())
            return

        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode())
            return

        # Route based on path
        if self.path == '/api/config/save':
            self.handle_save_config(data)
        elif self.path == '/api/config/get':
            self.handle_get_config(data)
        elif self.path == '/api/email/send':
            self.handle_send_email(data)
        elif self.path == '/api/email/test':
            self.handle_test_email(data)
        elif self.path == '/api/status':
            self.handle_status()
        elif self.path == '/api/monitoring/enable':
            self.handle_enable_monitoring(data)
        elif self.path == '/api/monitoring/check':
            self.handle_check_monitoring(data)
        elif self.path == '/api/applications/cache':
            self.handle_save_applications(data)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_save_config(self, data):
        """Save configuration"""
        key = data.get('key')
        value = data.get('value')

        if not key:
            self.send_error(400, "Missing key")
            return

        success = set_config(key, str(value))

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok" if success else "error",
            "message": "Config saved" if success else "Error saving config"
        }).encode())

    def handle_get_config(self, data):
        """Get configuration"""
        key = data.get('key')

        if not key:
            self.send_error(400, "Missing key")
            return

        value = get_config(key)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "key": key,
            "value": value
        }).encode())

    def handle_send_email(self, data):
        """Send email immediately"""
        recipient = data.get('recipient')
        subject = data.get('subject')
        html_body = data.get('html')
        text_body = data.get('text', '')

        if not all([recipient, subject, html_body]):
            self.send_error(400, "Missing required fields")
            return

        success = send_email(recipient, subject, html_body, text_body)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok" if success else "error",
            "message": "Email sent" if success else "Error sending email"
        }).encode())

    def handle_test_email(self, data):
        """Send test email"""
        recipient = data.get('recipient') or get_config('summary_recipient')

        if not recipient:
            self.send_error(400, "No recipient provided")
            return

        test_html = """
        <html style="font-family:Arial,sans-serif;">
        <body style="background:#f5f5f5;padding:20px;">
        <div style="background:white;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
            <h1 style="color:#4F46E5;margin-bottom:10px;">✅ Test Email erfolgreich!</h1>
            <p style="color:#333;margin-bottom:10px;">Wenn du diese Email erhältst, funktioniert dein SMTP-Setup korrekt.</p>
            <p style="color:#666;">Deine Bewerbungs-Zusammenfassungen werden automatisch an diese Adresse versendet.</p>
            <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0;">
            <p style="color:#999;font-size:12px;">Bewerbungs-Tracker Email Service</p>
        </div>
        </body>
        </html>
        """

        success = send_email(recipient, "✅ Bewerbungs-Tracker Test Email", test_html)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok" if success else "error",
            "message": "Test email sent" if success else "Error sending test email"
        }).encode())

    def handle_status(self):
        """Get service status"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        status = {
            "status": "ok",
            "service": "Bewerbungs-Tracker Email Service",
            "smtp_configured": bool(get_config('smtp_user')),
            "summary_enabled": get_config('summary_enabled') == 'true',
            "summary_recipient": get_config('summary_recipient'),
            "summary_frequency": get_config('summary_frequency', 'weekly'),
            "should_send_now": should_send_summary(),
            "monitoring_enabled": get_config('email_monitoring_enabled') == 'true',
            "imap_configured": bool(get_config('imap_host'))
        }

        self.wfile.write(json.dumps(status).encode())

    def handle_enable_monitoring(self, data):
        """Enable/disable email monitoring"""
        enabled = data.get('enabled', False)
        set_config('email_monitoring_enabled', 'true' if enabled else 'false')
        set_config('monitoring_recipient', data.get('recipient', ''))
        set_config('monitoring_notify', 'true' if data.get('notify', False) else 'false')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "message": "Monitoring " + ("enabled" if enabled else "disabled")
        }).encode())

    def handle_check_monitoring(self, data):
        """Check for application responses now"""
        responses = check_and_monitor_emails()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "detected": len(responses),
            "responses": responses
        }).encode())

    def handle_save_applications(self, data):
        """Save applications list for monitoring"""
        try:
            with open('applications_cache.json', 'w') as f:
                json.dump(data, f)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": f"Cached {len(data.get('bewerbungen', []))} applications"
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "message": str(e)
            }).encode())

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

# ── Background Scheduler ──────────────────────────────────────────────

def background_scheduler():
    """Background thread that checks summaries and monitors emails"""
    print("📧 Email Service Scheduler gestartet")

    check_interval = 300  # 5 minutes
    monitoring_interval = 1800  # 30 minutes for application responses

    last_monitoring_check = 0

    while True:
        try:
            current_time = time.time()

            # Check for email summaries (every 5 minutes)
            if should_send_summary():
                print("⏰ Zeit für Email-Zusammenfassung!")
                check_and_send_summary()

            # Check for application responses (every 30 minutes)
            if current_time - last_monitoring_check >= monitoring_interval:
                check_and_monitor_emails()
                last_monitoring_check = current_time

            # Check every 5 minutes
            time.sleep(check_interval)

        except Exception as e:
            print(f"❌ Scheduler error: {e}")
            time.sleep(check_interval)

# ── Main ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()

    # Start background scheduler
    scheduler = threading.Thread(target=background_scheduler, daemon=True)
    scheduler.start()

    # Start HTTP server
    server = HTTPServer((HOST, PORT), EmailServiceHandler)
    print(f"📧 Bewerbungs-Tracker Email Service")
    print(f"🌐 Läuft auf http://{HOST}:{PORT}")
    print(f"💾 Datenbank: {DB_FILE}")
    print(f"⏸️  Zum Beenden: Strg+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Email Service gestoppt")
        server.shutdown()
