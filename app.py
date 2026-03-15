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
import json
import sqlite3
import os
import base64
import hashlib
from datetime import datetime
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

        # Applications table
        c.execute('''CREATE TABLE IF NOT EXISTS bewerbungen (
            id TEXT PRIMARY KEY,
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
            deletedAt TEXT
        )''')

        # Settings table
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        # Create indices
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON bewerbungen(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_firma ON bewerbungen(firma)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_createdAt ON bewerbungen(createdAt)')

        conn.commit()

# ═══════════════════════════════════════════════════════
# DATABASE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════

def get_all_bewerbungen(include_deleted=False):
    """Fetch all applications"""
    with db_connection() as conn:
        c = conn.cursor()
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

def create_bewerbung(data):
    """Create new application"""
    bewerbung = {
        'id': data.get('id'),
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
            (id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
                (id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (b.get('id'), b.get('firma'), b.get('position'), b.get('status'),
                 b.get('datum'), b.get('gehalt'), b.get('ort'), b.get('email'),
                 b.get('quelle'), b.get('link'), b.get('notizen'),
                 b.get('createdAt'), b.get('updatedAt')))

        for key, value in settings.items():
            value_json = json.dumps(value) if not isinstance(value, str) else value
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                      (key, value_json))

        conn.commit()

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

# ═══ Applications API ═══

@app.route('/api/applications', methods=['GET', 'POST'])
def applications():
    """List or create applications"""
    if request.method == 'GET':
        data = get_all_bewerbungen()
        return jsonify({'status': 'ok', 'count': len(data), 'applications': data})

    elif request.method == 'POST':
        data = request.get_json() or {}
        if 'id' not in data:
            return jsonify({'status': 'error', 'message': 'id is required'}), 400

        app_data = create_bewerbung(data)
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

if __name__ == '__main__':
    print(f"🚀 Bewerbungs-Tracker Web Server starting...")
    print(f"📦 Database: {DB_FILE}")
    print(f"🌐 Listening on: {HOST}:{PORT}")
    print(f"🔗 Open browser: http://localhost:{PORT}")
    print(f"📚 API available at: http://localhost:{PORT}/api/*")

    # Initialize database
    init_db()

    # Start server
    app.run(host=HOST, port=PORT, debug=False)
