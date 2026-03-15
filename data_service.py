#!/usr/bin/env python3
"""
Bewerbungs-Tracker Data Service
Persistent SQLite storage for applications and settings
API on port 8767 (localhost only)
"""

import json
import sqlite3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# Database file in current directory
DB_FILE = 'bewerbungen.db'

# Input validation constants
MAX_STRING_LENGTH = 10000
MAX_ID_LENGTH = 100
MAX_LIMIT = 10000
MAX_REQUEST_SIZE_BYTES = 1024 * 1024  # 1MB
ALLOWED_STATUSES = {'beworben', 'interview', 'zusage', 'absage', 'ghosting', 'antwort'}
ALLOWED_QUELLEN = {'gmail', 'imap', 'manuell', 'linkedin', 'indeed', 'xing', 'website', 'empfehlung'}

# CORS headers configuration
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

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

class DataService:
    def __init__(self):
        self.db_file = DB_FILE
        self.init_db()

    def validate_id(self, id_val):
        """Validate application ID. Raises ValueError if invalid."""
        if not id_val or not isinstance(id_val, str):
            raise ValueError('Invalid ID: must be non-empty string')
        if len(id_val) > MAX_ID_LENGTH:
            raise ValueError(f'Invalid ID: max {MAX_ID_LENGTH} chars')

    def validate_string(self, value, field_name):
        """Validate string fields. Raises ValueError if too long."""
        if value is not None and len(str(value)) > MAX_STRING_LENGTH:
            raise ValueError(f'{field_name} too long: max {MAX_STRING_LENGTH} chars')

    def validate_bewerbung(self, data):
        """Validate application data. Raises ValueError if invalid."""
        if not data.get('firma'):
            raise ValueError('firma is required')
        self.validate_string(data.get('firma'), 'firma')
        self.validate_string(data.get('position'), 'position')
        self.validate_string(data.get('notizen'), 'notizen')

        if data.get('status') and data.get('status') not in ALLOWED_STATUSES:
            raise ValueError(f'Invalid status: {data.get("status")}')
        if data.get('quelle') and data.get('quelle') not in ALLOWED_QUELLEN:
            raise ValueError(f'Invalid quelle: {data.get("quelle")}')

    def validate_pagination(self, limit, offset):
        """Validate pagination parameters"""
        try:
            limit = int(limit) if limit else 1000
            offset = int(offset) if offset else 0

            if limit < 0 or limit > MAX_LIMIT:
                raise ValueError(f'Limit must be 0-{MAX_LIMIT}')
            if offset < 0:
                raise ValueError('Offset must be >= 0')

            return limit, offset
        except (TypeError, ValueError) as e:
            raise ValueError(f'Invalid pagination: {str(e)}')

    def init_db(self):
        """Initialize SQLite database with required tables"""
        with db_connection() as conn:
            c = conn.cursor()

            # Applications table (with soft delete support)
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

            # Settings table (key-value pairs)
            c.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')

            # Create indices for performance
            c.execute('CREATE INDEX IF NOT EXISTS idx_status ON bewerbungen(status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_firma ON bewerbungen(firma)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_createdAt ON bewerbungen(createdAt)')

            conn.commit()

    def get_all_bewerbungen(self, include_deleted=False):
        """Fetch all applications (excluding deleted by default), ordered by createdAt DESC"""
        with db_connection() as conn:
            c = conn.cursor()
            if include_deleted:
                c.execute('SELECT * FROM bewerbungen ORDER BY createdAt DESC')
            else:
                c.execute('SELECT * FROM bewerbungen WHERE deleted = 0 ORDER BY createdAt DESC')
            rows = [dict(row) for row in c.fetchall()]
        return rows

    def get_bewerbung(self, id):
        """Fetch single application by ID"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM bewerbungen WHERE id = ?', (id,))
            row = c.fetchone()
        return dict(row) if row else None

    def create_bewerbung(self, data):
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

    def update_bewerbung(self, id, data):
        """Update existing application"""
        with db_connection() as conn:
            c = conn.cursor()

            # Get current values
            c.execute('SELECT * FROM bewerbungen WHERE id = ?', (id,))
            current = dict(c.fetchone() or {})

            # Merge with updates
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

    def delete_bewerbung(self, id):
        """Soft delete application (mark as deleted, don't remove from DB)"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE bewerbungen SET deleted = 1, deletedAt = ? WHERE id = ?',
                      (datetime.now().isoformat(), id))
            conn.commit()
            affected = c.rowcount
        return affected > 0

    def get_deleted_bewerbungen(self):
        """Fetch all deleted applications, ordered by deletedAt DESC"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM bewerbungen WHERE deleted = 1 ORDER BY deletedAt DESC')
            rows = [dict(row) for row in c.fetchall()]
        return rows

    def recover_bewerbung(self, id):
        """Recover a deleted application"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE bewerbungen SET deleted = 0, deletedAt = NULL, updatedAt = ? WHERE id = ?',
                      (datetime.now().isoformat(), id))
            conn.commit()
            affected = c.rowcount
        return affected > 0

    def permanently_delete_bewerbung(self, id):
        """Permanently delete application from database (irreversible)"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM bewerbungen WHERE id = ?', (id,))
            conn.commit()
            affected = c.rowcount
        return affected > 0

    def get_settings(self):
        """Get all settings as dict"""
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

    def set_setting(self, key, value):
        """Set single setting (upsert)"""
        with db_connection() as conn:
            c = conn.cursor()
            value_json = json.dumps(value) if not isinstance(value, str) else value
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                      (key, value_json))
            conn.commit()

    def set_settings_bulk(self, settings_dict):
        """Set multiple settings at once"""
        with db_connection() as conn:
            c = conn.cursor()
            for key, value in settings_dict.items():
                value_json = json.dumps(value) if not isinstance(value, str) else value
                c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                          (key, value_json))
            conn.commit()

    def import_data(self, bewerbungen, settings):
        """Import applications and settings (bulk operation)"""
        with db_connection() as conn:
            c = conn.cursor()

            # Import bewerbungen
            for b in bewerbungen:
                c.execute('''INSERT OR REPLACE INTO bewerbungen
                    (id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (b.get('id'), b.get('firma'), b.get('position'), b.get('status'),
                     b.get('datum'), b.get('gehalt'), b.get('ort'), b.get('email'),
                     b.get('quelle'), b.get('link'), b.get('notizen'),
                     b.get('createdAt'), b.get('updatedAt')))

            # Import settings
            for key, value in settings.items():
                value_json = json.dumps(value) if not isinstance(value, str) else value
                c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                          (key, value_json))

            conn.commit()

    def export_data(self, include_deleted=False):
        """Export data for backup (excludes deleted by default)"""
        return {
            'bewerbungen': self.get_all_bewerbungen(include_deleted=include_deleted),
            'settings': self.get_settings(),
            'exportedAt': datetime.now().isoformat()
        }

    def clear_all(self):
        """Clear all data (careful!)"""
        with db_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM bewerbungen')
            c.execute('DELETE FROM settings')
            conn.commit()

# Global instance
service = DataService()

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

class RequestHandler(JSONHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/api/applications':
                data = service.get_all_bewerbungen()
                self.send_json_ok({'count': len(data), 'applications': data})

            elif path == '/api/applications/deleted':
                data = service.get_deleted_bewerbungen()
                self.send_json_ok({'count': len(data), 'deleted': data})

            elif path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                app = service.get_bewerbung(app_id)
                if app:
                    self.send_json_ok({'application': app})
                else:
                    self.send_json_error('Not found', 404)

            elif path == '/api/settings':
                settings = service.get_settings()
                self.send_json_ok({'settings': settings})

            elif path == '/api/export':
                data = service.export_data()
                self.send_json_ok(data)

            elif path == '/api/status':
                self.send_json_ok({'service': 'Bewerbungs-Tracker Data Service'})

            else:
                self.send_json_error('Not found', 404)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/api/applications':
                # Create new application
                if 'id' not in data:
                    self.send_json_error('id is required', 400)
                    return

                app = service.create_bewerbung(data)
                self.send_json_ok({'application': app}, 201)

            elif path == '/api/import':
                # Import data (backup restore)
                bewerbungen = data.get('bewerbungen', [])
                settings = data.get('settings', {})
                service.import_data(bewerbungen, settings)
                self.send_json_ok({'message': f'Imported {len(bewerbungen)} applications'})

            elif path == '/api/clear':
                # Clear all data (requires confirmation)
                if data.get('confirm') == 'DELETE_ALL':
                    service.clear_all()
                    self.send_json_ok({'message': 'All data cleared'})
                else:
                    self.send_json_error('Confirmation required', 400)

            elif path.startswith('/api/applications/') and path.endswith('/recover'):
                # Recover a deleted application
                app_id = path.split('/')[-2]
                if service.recover_bewerbung(app_id):
                    app = service.get_bewerbung(app_id)
                    self.send_json_ok({'message': 'Recovered', 'application': app})
                else:
                    self.send_json_error('Not found', 404)

            else:
                self.send_json_error('Not found', 404)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def do_PUT(self):
        """Handle PUT requests (updates)"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                updated = service.update_bewerbung(app_id, data)
                self.send_json_ok({'application': updated})

            elif path == '/api/settings':
                # Bulk update settings
                service.set_settings_bulk(data)
                settings = service.get_settings()
                self.send_json_ok({'settings': settings})

            else:
                self.send_json_error('Not found', 404)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        try:
            if path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                # Check if permanent deletion is requested (requires confirmation)
                if query_params.get('permanent') == ['true']:
                    if service.permanently_delete_bewerbung(app_id):
                        self.send_json_ok({'message': 'Permanently deleted'})
                    else:
                        self.send_json_error('Not found', 404)
                else:
                    # Soft delete (mark as deleted)
                    if service.delete_bewerbung(app_id):
                        self.send_json_ok({'message': 'Deleted (recoverable)'})
                    else:
                        self.send_json_error('Not found', 404)
            else:
                self.send_json_error('Not found', 404)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.log_date_time_string()}] {format % args}")

def run_server(port=8767):
    """Start the Data Service server"""
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"✅ Bewerbungs-Tracker Data Service running on http://127.0.0.1:{port}")
    print(f"📦 SQLite database: {DB_FILE}")
    print(f"📚 API Endpoints:")
    print(f"   GET  /api/applications - List all applications (active)")
    print(f"   GET  /api/applications/:id - Get single application")
    print(f"   GET  /api/applications/deleted - List deleted applications")
    print(f"   POST /api/applications - Create application")
    print(f"   PUT  /api/applications/:id - Update application")
    print(f"   DELETE /api/applications/:id - Soft delete application")
    print(f"   DELETE /api/applications/:id?permanent=true - Permanently delete")
    print(f"   POST /api/applications/:id/recover - Recover deleted application")
    print(f"   GET  /api/settings - Get all settings")
    print(f"   PUT  /api/settings - Update settings")
    print(f"   GET  /api/export - Export data (excludes deleted)")
    print(f"   POST /api/import - Import data")
    print(f"   GET  /api/status - Service status")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped")

if __name__ == '__main__':
    run_server()
