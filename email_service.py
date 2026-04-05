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
import base64
import hashlib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import ssl

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

HOST = '127.0.0.1'
PORT = 8766
DB_FILE = 'email_config.db'
MAX_REQUEST_SIZE_BYTES = 1024 * 1024  # 1MB
ENCRYPTION_KEY = None  # Will be derived from master password
CREDENTIALS_CACHE = {}  # Cache for credentials to avoid repeated DB lookups

# CORS headers configuration
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

# ── Helper Classes ─────────────────────────────────────────────────────

class IMAPConnection:
    """Helper class for establishing and managing IMAP connections"""
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
        """Establish IMAP connection with SSL/TLS support"""
        try:
            if self.port == 993:
                self.connection = imaplib.IMAP4_SSL(
                    self.host, self.port,
                    context=ssl.create_default_context()
                )
            else:
                self.connection = imaplib.IMAP4(self.host, self.port)
                self.connection.starttls()

            self.connection.login(self.user, self.password)
            return True
        except (imaplib.IMAP4.error, ConnectionError) as e:
            print(f"❌ IMAP Connection Error: {e}")
            return False

    def select_folder(self, folder='INBOX'):
        """Select a folder in the mailbox"""
        if self.connection:
            self.connection.select(folder)

    def close(self):
        """Close the IMAP connection"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass


class InputValidator:
    """Consolidate input validation logic"""
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        return email and '@' in email

    @staticmethod
    def validate_credentials(host, port, user, password):
        """Validate email credentials"""
        if not all([host, port, user, password]):
            return False, 'Missing required fields'
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                return False, 'Invalid port number'
            return True, None
        except ValueError:
            return False, 'Port must be a number'

    @staticmethod
    def validate_email_params(recipient, subject, html_body):
        """Validate email sending parameters"""
        if not recipient:
            return False, 'Missing recipient'
        if not subject:
            return False, 'Missing subject'
        if not html_body:
            return False, 'Missing email body'
        if not InputValidator.validate_email(recipient):
            return False, 'Invalid email format'
        return True, None

# ── Database ───────────────────────────────────────────────────────────

def derive_encryption_key(master_password):
    """Derive encryption key from master password using PBKDF2"""
    if not master_password:
        return None
    salt = b'bewerbungstracker_email'  # Fixed salt for consistent key derivation
    key = hashlib.pbkdf2_hmac('sha256', master_password.encode(), salt, 100000)
    return base64.urlsafe_b64encode(key[:32])  # Fernet requires 32 bytes

def _crypt_operation(data, encryption_key, operation='encrypt'):
    """Unified encryption/decryption using Fernet (AES)"""
    if not encryption_key or not Fernet:
        return data  # Return as-is if no key or cryptography library
    try:
        f = Fernet(encryption_key)
        if operation == 'encrypt':
            return f.encrypt(data.encode()).decode()
        else:  # decrypt
            return f.decrypt(data.encode()).decode()
    except Exception as e:
        op_name = 'Encryption' if operation == 'encrypt' else 'Decryption'
        print(f"❌ {op_name} error: {e}")
        return data

def encrypt_password(password, encryption_key):
    """Encrypt password using Fernet (AES)"""
    return _crypt_operation(password, encryption_key, 'encrypt')

def decrypt_password(encrypted_password, encryption_key):
    """Decrypt password using Fernet"""
    return _crypt_operation(encrypted_password, encryption_key, 'decrypt')

def init_db():
    """Initialize SQLite database for email configuration"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS email_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # Encrypted credentials table
    cursor.execute('''CREATE TABLE IF NOT EXISTS email_credentials (
        service TEXT PRIMARY KEY,
        host TEXT,
        port INTEGER,
        user TEXT,
        password TEXT,
        encrypted BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def save_credentials(service, host, port, user, password, encryption_key):
    """Save email credentials with encryption"""
    try:
        encrypted_password = encrypt_password(password, encryption_key) if encryption_key else password
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO email_credentials
                         (service, host, port, user, password, encrypted, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                      (service, host, port, user, encrypted_password, 1 if encryption_key else 0))
        conn.commit()
        conn.close()
        print(f"✅ {service.upper()} credentials saved and encrypted")
        return True
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False

def get_credentials(service, encryption_key):
    """Retrieve and decrypt email credentials (cached to avoid repeated DB lookups)"""
    # Check cache first (avoids repeated DB operations in hot path)
    cache_key = f"{service}:{encryption_key}"
    if cache_key in CREDENTIALS_CACHE:
        return CREDENTIALS_CACHE[cache_key]

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT host, port, user, password, encrypted FROM email_credentials WHERE service = ?',
                      (service,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        host, port, user, encrypted_password, is_encrypted = result

        # Decrypt password if it was encrypted
        if is_encrypted and encryption_key:
            password = decrypt_password(encrypted_password, encryption_key)
        else:
            password = encrypted_password

        creds = {'host': host, 'port': port, 'user': user, 'password': password}

        # Cache for future lookups
        CREDENTIALS_CACHE[cache_key] = creds
        return creds
    except Exception as e:
        print(f"❌ Error retrieving credentials: {e}")
        return None

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
    """Send email via SMTP using stored encrypted credentials"""
    try:
        # Try to get credentials from database first (encrypted)
        credentials = get_credentials('smtp', ENCRYPTION_KEY)

        if credentials:
            smtp_host = credentials['host']
            smtp_port = int(credentials['port'])
            smtp_user = credentials['user']
            smtp_pass = credentials['password']
        else:
            # Fallback to config table for backward compatibility
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

        # Use IMAPConnection helper for consistent connection handling
        imap_conn = IMAPConnection(imap_host, imap_port, imap_user, imap_pass)
        if not imap_conn.connect():
            return []

        imap_conn.select_folder('INBOX')
        imap = imap_conn.connection

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

        imap_conn.close()
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

class JSONHandler(BaseHTTPRequestHandler):
    """Base HTTP handler with JSON response helpers"""

    def _send_cors_headers(self):
        """Send CORS headers to allow cross-origin requests"""
        for key, value in CORS_HEADERS.items():
            self.send_header(key, value)

    def send_json(self, status_code, data):
        """Send JSON response with standard headers"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_json_ok(self, data, status_code=200):
        """Send success response (auto-wraps with 'status': 'ok')"""
        response = {'status': 'ok'}
        if isinstance(data, dict):
            response.update(data)
        else:
            response['data'] = data
        self.send_json(status_code, response)

    def send_json_error(self, message, status_code=400):
        """Send error response"""
        self.send_json(status_code, {'status': 'error', 'message': message})

class EmailServiceHandler(JSONHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _check_origin(self):
        """Verify request origin (CSRF protection - localhost only)"""
        origin = self.headers.get('Origin', '')

        # Allow localhost/127.0.0.1 only
        if origin and 'localhost' not in origin and '127.0.0.1' not in origin:
            self.send_json_error('CORS policy violation', 403)
            return False

        return True

    def _validate_credentials_input(self, service, host, port, user, password, master_password=None):
        """Validate email credentials input (shared validation for save/test)

        Returns True if valid, False otherwise (and sends error response).
        """
        # Validate service type
        if not service or service not in ['smtp', 'imap']:
            self.send_json_error('Invalid service type. Must be "smtp" or "imap"', 400)
            return False

        # Check required fields
        required_fields = [service, host, port, user, password]
        if master_password is not None:
            required_fields.append(master_password)

        if not all(required_fields):
            fields = 'service, host, port, user, password'
            if master_password is not None:
                fields += ', master_password'
            self.send_json_error(f'Missing required fields: {fields}', 400)
            return False

        # Validate port is numeric
        try:
            int(port)
        except (ValueError, TypeError):
            self.send_json_error('Invalid port number', 400)
            return False

        return True

    def do_GET(self):
        """Handle GET requests"""
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        # Extract single values from query params (parse_qs returns lists)
        params = {k: v[0] if v else '' for k, v in query_params.items()}

        try:
            # Route dispatch dictionary
            get_routes = {
                '/api/status': lambda: self.handle_status(),
                '/api/config/get': lambda: self.handle_get_config({'key': params.get('key', '')}),
                '/api/monitoring/check': lambda: self.handle_check_monitoring({})
            }

            handler = get_routes.get(path)
            if handler:
                handler()
            else:
                self.send_json_error('Not found', 404)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def do_POST(self):
        """Handle POST requests"""
        # CSRF Protection: Check origin
        if not self._check_origin():
            return

        content_length = int(self.headers.get('Content-Length', 0))

        # Security: Limit request body size (max 1MB)
        if content_length > MAX_REQUEST_SIZE_BYTES:
            self.send_json_error('Request body too large', 413)
            return

        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self.send_json_error('Invalid JSON', 400)
            return

        # Route dispatch dictionary - maps URL path to handler function
        post_routes = {
            '/api/config/save': self.handle_save_config,
            '/api/config/get': self.handle_get_config,
            '/api/credentials/save': self.handle_save_credentials,
            '/api/credentials/test': self.handle_test_credentials,
            '/api/email/send': self.handle_send_email,
            '/api/email/test': self.handle_test_email,
            '/api/status': self.handle_status,
            '/api/monitoring/enable': self.handle_enable_monitoring,
            '/api/monitoring/check': self.handle_check_monitoring,
            '/api/applications/cache': self.handle_save_applications,
        }

        # Dispatch request to appropriate handler
        handler = post_routes.get(self.path)
        if handler:
            # Handlers that accept data parameter
            if self.path != '/api/status':
                handler(data)
            else:
                handler()  # handle_status() takes no parameters
        else:
            self.send_response(404)
            self.end_headers()

    def handle_save_config(self, data):
        """Save configuration"""
        key = data.get('key')
        value = data.get('value')

        if not key:
            self.send_json_error('Missing key', 400)
            return

        success = set_config(key, str(value))
        if success:
            self.send_json_ok({'message': 'Config saved'})
        else:
            self.send_json_error('Error saving config', 500)

    def handle_get_config(self, data):
        """Get configuration"""
        key = data.get('key')

        if not key:
            self.send_json_error('Missing key', 400)
            return

        value = get_config(key)
        self.send_json_ok({'key': key, 'value': value})

    def handle_send_email(self, data):
        """Send email immediately"""
        recipient = data.get('recipient')
        subject = data.get('subject')
        html_body = data.get('html')
        text_body = data.get('text', '')

        if not all([recipient, subject, html_body]):
            self.send_json_error('Missing required fields', 400)
            return

        success = send_email(recipient, subject, html_body, text_body)
        if success:
            self.send_json_ok({'message': 'Email sent'})
        else:
            self.send_json_error('Error sending email', 500)

    def handle_test_email(self, data):
        """Send test email"""
        recipient = data.get('recipient') or get_config('summary_recipient')

        if not recipient:
            self.send_json_error('No recipient provided', 400)
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
        if success:
            self.send_json_ok({'message': 'Test email sent'})
        else:
            self.send_json_error('Error sending test email', 500)

    def handle_status(self):
        """Get service status"""
        status_data = {
            "service": "Bewerbungs-Tracker Email Service",
            "smtp_configured": bool(get_config('smtp_user')),
            "summary_enabled": get_config('summary_enabled') == 'true',
            "summary_recipient": get_config('summary_recipient'),
            "summary_frequency": get_config('summary_frequency', 'weekly'),
            "should_send_now": should_send_summary(),
            "monitoring_enabled": get_config('email_monitoring_enabled') == 'true',
            "imap_configured": bool(get_config('imap_host'))
        }
        self.send_json_ok(status_data)

    def handle_enable_monitoring(self, data):
        """Enable/disable email monitoring"""
        enabled = data.get('enabled', False)
        set_config('email_monitoring_enabled', 'true' if enabled else 'false')
        set_config('monitoring_recipient', data.get('recipient', ''))
        set_config('monitoring_notify', 'true' if data.get('notify', False) else 'false')

        self.send_json_ok({'message': 'Monitoring ' + ('enabled' if enabled else 'disabled')})

    def handle_check_monitoring(self, data):
        """Check for application responses now"""
        responses = check_and_monitor_emails()
        self.send_json_ok({'detected': len(responses), 'responses': responses})

    def handle_save_credentials(self, data):
        """Save email credentials with encryption"""
        service = data.get('service', '').lower()  # 'smtp' or 'imap'
        host = data.get('host', '')
        port = data.get('port', '')
        user = data.get('user', '')
        password = data.get('password', '')
        master_password = data.get('master_password', '')

        # Validate input
        if not self._validate_credentials_input(service, host, port, user, password, master_password):
            return

        try:
            # Derive encryption key from master password
            encryption_key = derive_encryption_key(master_password)

            if not encryption_key:
                self.send_json_error('Failed to derive encryption key from master password', 400)
                return

            # Save credentials
            success = save_credentials(service, host, int(port), user, password, encryption_key)

            if success:
                # Update global ENCRYPTION_KEY if this is the first time
                global ENCRYPTION_KEY
                if not ENCRYPTION_KEY:
                    ENCRYPTION_KEY = encryption_key

                # Clear cache for this service to ensure fresh fetch next time
                cache_key = f"{service}:{encryption_key}"
                CREDENTIALS_CACHE.pop(cache_key, None)

                self.send_json_ok({
                    'message': f'{service.upper()} credentials saved and encrypted',
                    'service': service
                })
            else:
                self.send_json_error(f'Error saving {service.upper()} credentials', 500)
        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_test_credentials(self, data):
        """Test email credentials by attempting connection"""
        service = data.get('service', '').lower()  # 'smtp' or 'imap'
        host = data.get('host', '')
        port = data.get('port', '')
        user = data.get('user', '')
        password = data.get('password', '')

        # Validate input (no master_password needed for testing)
        if not self._validate_credentials_input(service, host, port, user, password):
            return

        try:
            port_int = int(port)
            if service == 'smtp':
                # Test SMTP connection
                server = smtplib.SMTP(host, port_int, timeout=10)
                server.starttls()
                server.login(user, password)
                server.quit()
                self.send_json_ok({
                    'message': 'SMTP credentials are valid',
                    'service': 'smtp'
                })
            else:  # service == 'imap'
                # Test IMAP connection using consolidated helper
                imap_conn = IMAPConnection(host, port_int, user, password)
                if imap_conn.connect():
                    imap_conn.close()
                    self.send_json_ok({
                        'message': 'IMAP credentials are valid',
                        'service': 'imap'
                    })
                else:
                    self.send_json_error('Invalid IMAP credentials', 401)

        except smtplib.SMTPAuthenticationError:
            self.send_json_error('Authentication failed. Check your credentials.', 401)
        except imaplib.IMAP4.error as e:
            self.send_json_error(f'IMAP error: {str(e)}', 401)
        except ConnectionRefusedError:
            self.send_json_error('Connection refused. Check host and port.', 500)
        except Exception as e:
            self.send_json_error(f'Connection test failed: {str(e)}', 500)

    def handle_save_applications(self, data):
        """Save applications list for monitoring"""
        try:
            with open('applications_cache.json', 'w') as f:
                json.dump(data, f)

            app_count = len(data.get('bewerbungen', []))
            self.send_json_ok({'message': f'Cached {app_count} applications'})
        except Exception as e:
            self.send_json_error(str(e), 500)

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
