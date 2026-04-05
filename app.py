#!/usr/bin/env python3
"""
Bewerbungs-Tracker Unified Web Server
Combines Frontend + All Backend Services (IMAP, Email, Data) into one Flask app
Deployable to Railway, Heroku, AWS, etc.

Features:
- Serves static frontend (index.html, CSS, JS)
- All APIs available at /api/*
- CORS enabled for all origins
- SQLite database
- Email service with encryption
- IMAP monitoring
"""

from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json
import sqlite3
import os
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
import logging

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Database setup
DB_FILE = 'bewerbungen.db'

# Port configuration (Railway/Heroku use PORT env var)
PORT = int(os.environ.get('PORT', 8080))
HOST = '0.0.0.0'  # Listen on all interfaces (required for cloud)

# Input validation
MAX_STRING_LENGTH = 10000
MAX_ID_LENGTH = 100
ALLOWED_STATUSES = {'beworben', 'interview', 'zusage', 'absage', 'ghosting', 'antwort'}
ALLOWED_QUELLEN = {'gmail', 'imap', 'manuell', 'linkedin', 'indeed', 'xing', 'website', 'empfehlung'}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# AUTHENTICATION (SIMPLIFIED - NO AUTH REQUIRED)
# ═══════════════════════════════════════════════════════

# Default user ID (all requests use this)
DEFAULT_USER_ID = "default_user"

def generate_token():
    """Generate a secure token (kept for compatibility)"""
    return secrets.token_urlsafe(32)

# ═══════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════

@contextmanager
def db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Initialize SQLite database"""
    with db_connection() as conn:
        c = conn.cursor()

        # Users table (NEW)
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            deleted INTEGER DEFAULT 0,
            deletedAt TEXT
        )''')

        # Applications table
        c.execute('''CREATE TABLE IF NOT EXISTS bewerbungen (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            firma TEXT NOT NULL,
            position TEXT,
            status TEXT,
            datum TEXT,
            gehalt TEXT,
            ort TEXT,
            email TEXT,
            quelle TEXT,
            link TEXT,
            notizen TEXT,
            createdAt TEXT,
            updatedAt TEXT,
            deleted INTEGER DEFAULT 0,
            deletedAt TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')

        # Settings table
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        # CV Comparisons table
        c.execute('''CREATE TABLE IF NOT EXISTS cv_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            result TEXT,
            cv_file TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Create indices
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_bew_user_id ON bewerbungen(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON bewerbungen(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_firma ON bewerbungen(firma)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_createdAt ON bewerbungen(createdAt)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_cv_comp_created ON cv_comparisons(created_at)')

        conn.commit()

# ═══════════════════════════════════════════════════════
# DATABASE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════

def get_all_bewerbungen(user_id=None, include_deleted=False):
    """Fetch all applications (optionally filtered by user_id)"""
    with db_connection() as conn:
        c = conn.cursor()
        if user_id:
            # Single user's bewerbungen
            if include_deleted:
                c.execute('SELECT * FROM bewerbungen WHERE user_id = ? ORDER BY createdAt DESC', (user_id,))
            else:
                c.execute('SELECT * FROM bewerbungen WHERE user_id = ? AND deleted = 0 ORDER BY createdAt DESC', (user_id,))
        else:
            # All bewerbungen (fallback, for migration)
            if include_deleted:
                c.execute('SELECT * FROM bewerbungen ORDER BY createdAt DESC')
            else:
                c.execute('SELECT * FROM bewerbungen WHERE deleted = 0 ORDER BY createdAt DESC')
        rows = [dict(row) for row in c.fetchall()]
    return rows

def get_bewerbung(id):
    """Fetch single application by ID"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM bewerbungen WHERE id = ?', (id,))
        row = c.fetchone()
    return dict(row) if row else None

def create_bewerbung(data, user_id=None):
    """Create new application"""
    bewerbung = {
        'id': data.get('id'),
        'user_id': user_id or data.get('user_id'),
        'firma': data.get('firma', ''),
        'position': data.get('position', ''),
        'status': data.get('status', 'beworben'),
        'datum': data.get('datum', ''),
        'gehalt': data.get('gehalt', ''),
        'ort': data.get('ort', ''),
        'email': data.get('email', ''),
        'quelle': data.get('quelle', ''),
        'link': data.get('link', ''),
        'notizen': data.get('notizen', ''),
        'createdAt': data.get('createdAt', datetime.now().isoformat()),
        'updatedAt': data.get('updatedAt', datetime.now().isoformat())
    }

    with db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO bewerbungen
            (id, user_id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            tuple(bewerbung.values()))
        conn.commit()

    return bewerbung

def update_bewerbung(id, data):
    """Update existing application"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM bewerbungen WHERE id = ?', (id,))
        current = dict(c.fetchone() or {})

        updated = {**current}
        updated.update(data)
        updated['updatedAt'] = datetime.now().isoformat()

        c.execute('''UPDATE bewerbungen SET
            firma=?, position=?, status=?, datum=?, gehalt=?, ort=?,
            email=?, quelle=?, link=?, notizen=?, updatedAt=?
            WHERE id=?''',
            (updated['firma'], updated['position'], updated['status'], updated['datum'],
             updated['gehalt'], updated['ort'], updated['email'], updated['quelle'],
             updated['link'], updated['notizen'], updated['updatedAt'], id))

        conn.commit()

    return updated

def delete_bewerbung(id):
    """Soft delete application"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE bewerbungen SET deleted = 1, deletedAt = ? WHERE id = ?',
                  (datetime.now().isoformat(), id))
        conn.commit()
        affected = c.rowcount
    return affected > 0

def get_deleted_bewerbungen():
    """Fetch deleted applications"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM bewerbungen WHERE deleted = 1 ORDER BY deletedAt DESC')
        rows = [dict(row) for row in c.fetchall()]
    return rows

def recover_bewerbung(id):
    """Recover deleted application"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE bewerbungen SET deleted = 0, deletedAt = NULL, updatedAt = ? WHERE id = ?',
                  (datetime.now().isoformat(), id))
        conn.commit()
        affected = c.rowcount
    return affected > 0

def permanently_delete_bewerbung(id):
    """Permanently delete application"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM bewerbungen WHERE id = ?', (id,))
        conn.commit()
        affected = c.rowcount
    return affected > 0

def get_settings():
    """Get all settings"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT key, value FROM settings')
        settings = {}
        for key, value in c.fetchall():
            try:
                settings[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                settings[key] = value
    return settings

def set_settings_bulk(settings_dict):
    """Set multiple settings"""
    with db_connection() as conn:
        c = conn.cursor()
        for key, value in settings_dict.items():
            value_json = json.dumps(value) if not isinstance(value, str) else value
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                      (key, value_json))
        conn.commit()

def export_data(include_deleted=False):
    """Export all data for backup"""
    return {
        'bewerbungen': get_all_bewerbungen(include_deleted=include_deleted),
        'settings': get_settings(),
        'exportedAt': datetime.now().isoformat()
    }

def import_data(bewerbungen, settings):
    """Import data"""
    with db_connection() as conn:
        c = conn.cursor()
        for b in bewerbungen:
            c.execute('''INSERT OR REPLACE INTO bewerbungen
                (id, user_id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (b.get('id'), b.get('user_id'), b.get('firma'), b.get('position'), b.get('status'),
                 b.get('datum'), b.get('gehalt'), b.get('ort'), b.get('email'),
                 b.get('quelle'), b.get('link'), b.get('notizen'),
                 b.get('createdAt'), b.get('updatedAt')))

        for key, value in settings.items():
            value_json = json.dumps(value) if not isinstance(value, str) else value
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                      (key, value_json))

        conn.commit()

# ═══════════════════════════════════════════════════════
# USER MANAGEMENT FUNCTIONS
# ═══════════════════════════════════════════════════════

def create_user(username, password, email='', is_admin=0):
    """Create a new user"""
    user_id = f'user_{uuid.uuid4().hex[:12]}'
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    now = datetime.now().isoformat()

    with db_connection() as conn:
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO users (id, username, password_hash, email, is_admin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (user_id, username, password_hash, email, is_admin, now, now))
            conn.commit()
            return {'id': user_id, 'username': username, 'email': email, 'is_admin': is_admin, 'created_at': now}
        except sqlite3.IntegrityError:
            return None

def get_user(user_id):
    """Get user by ID"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, email, is_admin, created_at FROM users WHERE id = ? AND deleted = 0', (user_id,))
        row = c.fetchone()
    return dict(row) if row else None

def get_user_by_username(username):
    """Get user by username (includes password_hash for auth)"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash, email, is_admin FROM users WHERE username = ? AND deleted = 0', (username,))
        row = c.fetchone()
    return dict(row) if row else None

def get_all_users():
    """Get all non-deleted users"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, email, is_admin, created_at FROM users WHERE deleted = 0 ORDER BY created_at DESC')
        rows = [dict(row) for row in c.fetchall()]
    return rows

def update_user(user_id, data):
    """Update user"""
    with db_connection() as conn:
        c = conn.cursor()
        now = datetime.now().isoformat()

        # Build update query dynamically
        updates = []
        values = []
        for key in ['username', 'email', 'is_admin']:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])

        if 'password' in data:
            updates.append('password_hash = ?')
            values.append(generate_password_hash(data['password'], method='pbkdf2:sha256'))

        if not updates:
            return get_user(user_id)

        updates.append('updated_at = ?')
        values.append(now)
        values.append(user_id)

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        c.execute(query, values)
        conn.commit()

    return get_user(user_id)

def delete_user(user_id):
    """Soft-delete user"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET deleted = 1, deletedAt = ? WHERE id = ?',
                  (datetime.now().isoformat(), user_id))
        conn.commit()
        return c.rowcount > 0

def authenticate_user(username, password):
    """Authenticate user and return user data"""
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return {
            'user_id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'is_admin': user['is_admin']
        }
    return None

# ═══════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════

@app.route('/')
def index():
    """Serve the frontend"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('.', path)

# ═══ Authentication API (SIMPLIFIED - ALWAYS RETURNS 200 OK) ═══

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint (simplified - always returns success)"""
    return jsonify({
        'status': 'ok',
        'token': generate_token(),
        'user_id': DEFAULT_USER_ID,
        'username': 'user',
        'is_admin': 1,
        'message': 'Login successful'
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout endpoint (simplified - always returns success)"""
    return jsonify({'status': 'ok', 'message': 'Logged out'}), 200

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status (simplified - always returns authenticated)"""
    return jsonify({
        'status': 'ok',
        'user_id': DEFAULT_USER_ID,
        'username': 'user',
        'email': '',
        'is_admin': 1,
        'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
    }), 200

# ═══ Admin User Management API (PUBLIC - NO AUTH REQUIRED) ═══

@app.route('/api/admin/users', methods=['GET'])
def list_users():
    """List all users (public)"""
    users = get_all_users()
    return jsonify({'status': 'ok', 'count': len(users), 'users': users})

@app.route('/api/admin/users', methods=['POST'])
def create_new_user():
    """Create new user (public)"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    is_admin = 1 if data.get('is_admin') else 0

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400

    user = create_user(username, password, email, is_admin)
    if not user:
        return jsonify({'status': 'error', 'message': 'Username already exists'}), 409

    return jsonify({'status': 'ok', 'user': user}), 201

@app.route('/api/admin/users/<user_id>', methods=['PUT'])
def update_user_endpoint(user_id):
    """Update user (public)"""
    data = request.get_json() or {}
    updated = update_user(user_id, data)

    if not updated:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    return jsonify({'status': 'ok', 'user': updated})

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def delete_user_endpoint(user_id):
    """Delete user (public)"""
    if delete_user(user_id):
        return jsonify({'status': 'ok', 'message': 'User deleted'})
    return jsonify({'status': 'error', 'message': 'User not found'}), 404

# ═══ Applications API ═══

@app.route('/api/applications', methods=['GET', 'POST'])
def applications():
    """List or create applications (uses default_user)"""
    user_id = DEFAULT_USER_ID

    if request.method == 'GET':
        # Get only this user's applications
        data = get_all_bewerbungen(user_id=user_id)
        return jsonify({'status': 'ok', 'count': len(data), 'applications': data})

    elif request.method == 'POST':
        data = request.get_json() or {}
        if 'id' not in data:
            return jsonify({'status': 'error', 'message': 'id is required'}), 400

        # Create application for this user
        app_data = create_bewerbung(data, user_id=user_id)
        return jsonify({'status': 'ok', 'application': app_data}), 201

@app.route('/api/applications/<app_id>', methods=['GET', 'PUT', 'DELETE'])
def application(app_id):
    """Get, update, or delete a single application"""
    if request.method == 'GET':
        app_data = get_bewerbung(app_id)
        if app_data:
            return jsonify({'status': 'ok', 'application': app_data})
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

    elif request.method == 'PUT':
        data = request.get_json() or {}
        updated = update_bewerbung(app_id, data)
        return jsonify({'status': 'ok', 'application': updated})

    elif request.method == 'DELETE':
        permanent = request.args.get('permanent') == 'true'
        if permanent:
            if permanently_delete_bewerbung(app_id):
                return jsonify({'status': 'ok', 'message': 'Permanently deleted'})
        else:
            if delete_bewerbung(app_id):
                return jsonify({'status': 'ok', 'message': 'Deleted (recoverable)'})
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.route('/api/applications/deleted', methods=['GET'])
def deleted_applications():
    """Get deleted applications"""
    data = get_deleted_bewerbungen()
    return jsonify({'status': 'ok', 'count': len(data), 'deleted': data})

@app.route('/api/applications/<app_id>/recover', methods=['POST'])
def recover_application(app_id):
    """Recover a deleted application"""
    if recover_bewerbung(app_id):
        app_data = get_bewerbung(app_id)
        return jsonify({'status': 'ok', 'message': 'Recovered', 'application': app_data})
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

# ═══ Settings API ═══

@app.route('/api/settings', methods=['GET', 'PUT'])
def settings():
    """Get or update settings"""
    if request.method == 'GET':
        data = get_settings()
        return jsonify({'status': 'ok', 'settings': data})

    elif request.method == 'PUT':
        data = request.get_json() or {}
        set_settings_bulk(data)
        settings_data = get_settings()
        return jsonify({'status': 'ok', 'settings': settings_data})

# ═══ Import/Export API ═══

@app.route('/api/import', methods=['POST'])
def import_endpoint():
    """Import data"""
    data = request.get_json() or {}
    bewerbungen = data.get('bewerbungen', [])
    settings = data.get('settings', {})
    import_data(bewerbungen, settings)
    return jsonify({'status': 'ok', 'message': f'Imported {len(bewerbungen)} applications'})

@app.route('/api/export', methods=['GET'])
def export_endpoint():
    """Export data"""
    data = export_data()
    return jsonify({'status': 'ok', **data})

# ═══ CV Comparison Endpoints ═══

@app.route('/api/cv-comparison/save', methods=['POST'])
def save_cv_comparison():
    """Save CV comparison result"""
    data = request.get_json()
    title = data.get('title', 'Untitled Comparison')
    result = data.get('result', '')
    cv_file = data.get('cv_file', 'unknown')

    if not result:
        return jsonify({'status': 'error', 'message': 'Result is required'}), 400

    with db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO cv_comparisons (title, result, cv_file, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (title, result, cv_file, datetime.now().isoformat()))
        conn.commit()
        comparison_id = c.lastrowid

    return jsonify({'status': 'ok', 'id': comparison_id, 'message': 'Comparison saved'})

@app.route('/api/cv-comparison/list', methods=['GET'])
def list_cv_comparisons():
    """List all CV comparisons"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, title, cv_file, created_at FROM cv_comparisons ORDER BY created_at DESC')
        comparisons = [{'id': row[0], 'title': row[1], 'cv_file': row[2], 'created_at': row[3]}
                      for row in c.fetchall()]
    return jsonify({'status': 'ok', 'comparisons': comparisons})

@app.route('/api/cv-comparison/<int:comp_id>', methods=['GET'])
def get_cv_comparison(comp_id):
    """Get a specific CV comparison"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, title, result, cv_file, created_at FROM cv_comparisons WHERE id = ?', (comp_id,))
        row = c.fetchone()

    if not row:
        return jsonify({'status': 'error', 'message': 'Comparison not found'}), 404

    return jsonify({'status': 'ok', 'comparison': {
        'id': row[0], 'title': row[1], 'result': row[2], 'cv_file': row[3], 'created_at': row[4]
    }})

@app.route('/api/cv-comparison/<int:comp_id>', methods=['DELETE'])
def delete_cv_comparison(comp_id):
    """Delete a CV comparison"""
    with db_connection() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM cv_comparisons WHERE id = ?', (comp_id,))
        conn.commit()
        if c.rowcount == 0:
            return jsonify({'status': 'error', 'message': 'Comparison not found'}), 404

    return jsonify({'status': 'ok', 'message': 'Comparison deleted'})

@app.route('/api/cv-comparison/export', methods=['POST'])
def export_cv_comparison():
    """Export CV comparison as file"""
    data = request.get_json()
    comp_id = data.get('id')

    with db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT title, result, created_at FROM cv_comparisons WHERE id = ?', (comp_id,))
        row = c.fetchone()

    if not row:
        return jsonify({'status': 'error', 'message': 'Comparison not found'}), 404

    return jsonify({'status': 'ok', 'comparison': {
        'title': row[0], 'result': row[1], 'created_at': row[2]
    }})

# ═══ Status/Health Check ═══

@app.route('/api/status', methods=['GET'])
def status():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'Bewerbungs-Tracker',
        'version': '4.3',
        'timestamp': datetime.now().isoformat()
    })

# ═══════════════════════════════════════════════════════
# INITIALIZATION & STARTUP
# ═══════════════════════════════════════════════════════

# Initialize database on startup (works with gunicorn and app.run)
@app.before_request
def initialize_db():
    """Initialize database on first request"""
    if not hasattr(app, '_db_initialized'):
        init_db()
        app._db_initialized = True

# Also initialize on startup for faster first request
try:
    init_db()
    print(f"✅ Database initialized at startup")
except Exception as e:
    print(f"⚠️ Database initialization warning: {e}")

if __name__ == '__main__':
    print(f"🚀 Bewerbungs-Tracker Web Server starting...")
    print(f"📦 Database: {DB_FILE}")
    print(f"🌐 Listening on: {HOST}:{PORT}")
    print(f"🔗 Open browser: http://localhost:{PORT}")
    print(f"📚 API available at: http://localhost:{PORT}/api/*")

    # Start server
    app.run(host=HOST, port=PORT, debug=False)
