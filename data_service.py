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
        conn = sqlite3.connect(self.db_file)
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
            updatedAt TEXT
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
        conn.close()

    def get_all_bewerbungen(self):
        """Fetch all applications, ordered by createdAt DESC"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM bewerbungen ORDER BY createdAt DESC')
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return rows

    def get_bewerbung(self, id):
        """Fetch single application by ID"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM bewerbungen WHERE id = ?', (id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def create_bewerbung(self, data):
        """Create new application"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
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
        
        c.execute('''INSERT INTO bewerbungen 
            (id, firma, position, status, datum, gehalt, ort, email, quelle, link, notizen, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            tuple(bewerbung.values()))
        
        conn.commit()
        conn.close()
        return bewerbung

    def update_bewerbung(self, id, data):
        """Update existing application"""
        conn = sqlite3.connect(self.db_file)
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
        conn.close()
        return updated

    def delete_bewerbung(self, id):
        """Delete application"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('DELETE FROM bewerbungen WHERE id = ?', (id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0

    def get_settings(self):
        """Get all settings as dict"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('SELECT key, value FROM settings')
        settings = {}
        for key, value in c.fetchall():
            try:
                settings[key] = json.loads(value)
            except:
                settings[key] = value
        conn.close()
        return settings

    def set_setting(self, key, value):
        """Set single setting (upsert)"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        value_json = json.dumps(value) if not isinstance(value, str) else value
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                  (key, value_json))
        conn.commit()
        conn.close()

    def set_settings_bulk(self, settings_dict):
        """Set multiple settings at once"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        for key, value in settings_dict.items():
            value_json = json.dumps(value) if not isinstance(value, str) else value
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                      (key, value_json))
        conn.commit()
        conn.close()

    def import_data(self, bewerbungen, settings):
        """Import applications and settings (bulk operation)"""
        conn = sqlite3.connect(self.db_file)
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
        conn.close()

    def export_data(self):
        """Export all data for backup"""
        return {
            'bewerbungen': self.get_all_bewerbungen(),
            'settings': self.get_settings(),
            'exportedAt': datetime.now().isoformat()
        }

    def clear_all(self):
        """Clear all data (careful!)"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('DELETE FROM bewerbungen')
        c.execute('DELETE FROM settings')
        conn.commit()
        conn.close()

# Global instance
service = DataService()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            if path == '/api/applications':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                data = service.get_all_bewerbungen()
                self.wfile.write(json.dumps({'status': 'ok', 'count': len(data), 'applications': data}).encode())
            
            elif path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                app = service.get_bewerbung(app_id)
                if app:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok', 'application': app}).encode())
                else:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
            
            elif path == '/api/settings':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                settings = service.get_settings()
                self.wfile.write(json.dumps({'status': 'ok', 'settings': settings}).encode())
            
            elif path == '/api/export':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                data = service.export_data()
                self.wfile.write(json.dumps(data).encode())
            
            elif path == '/api/status':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'service': 'Bewerbungs-Tracker Data Service'}).encode())
            
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())

    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            if path == '/api/applications':
                # Create new application
                if 'id' not in data:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'id is required'}).encode())
                    return
                
                app = service.create_bewerbung(data)
                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'application': app}).encode())
            
            elif path == '/api/import':
                # Import data (backup restore)
                bewerbungen = data.get('bewerbungen', [])
                settings = data.get('settings', {})
                service.import_data(bewerbungen, settings)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'message': f'Imported {len(bewerbungen)} applications'}).encode())
            
            elif path == '/api/clear':
                # Clear all data (requires confirmation)
                if data.get('confirm') == 'DELETE_ALL':
                    service.clear_all()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok', 'message': 'All data cleared'}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'Confirmation required'}).encode())
            
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())

    def do_PUT(self):
        """Handle PUT requests (updates)"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            if path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                updated = service.update_bewerbung(app_id, data)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'application': updated}).encode())
            
            elif path == '/api/settings':
                # Bulk update settings
                service.set_settings_bulk(data)
                settings = service.get_settings()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'settings': settings}).encode())
            
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            if path.startswith('/api/applications/'):
                app_id = path.split('/')[-1]
                if service.delete_bewerbung(app_id):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok', 'message': 'Deleted'}).encode())
                else:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Not found'}).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())

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
    print(f"   GET  /api/applications - List all applications")
    print(f"   GET  /api/applications/:id - Get single application")
    print(f"   POST /api/applications - Create application")
    print(f"   PUT  /api/applications/:id - Update application")
    print(f"   DELETE /api/applications/:id - Delete application")
    print(f"   GET  /api/settings - Get all settings")
    print(f"   PUT  /api/settings - Update settings")
    print(f"   GET  /api/export - Export all data")
    print(f"   POST /api/import - Import data")
    print(f"   GET  /api/status - Service status")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped")

if __name__ == '__main__':
    run_server()
