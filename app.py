#!/usr/bin/env python3
"""
Bewerbungstracker - Modernized Flask App with SQLAlchemy & JWT Auth
Factory pattern for Flask application creation
"""

import os
from dotenv import load_dotenv

# .env MUSS vor `from config import config` geladen werden – Config wertet
# os.getenv(...) zur Import-Zeit aus, also vor jeglicher Modul-Initialisierung.
# Im gunicorn-Pfad reicht systemd's `source .env`, aber bei direktem
# `python script.py` (z.B. scripts/*) muss load_dotenv() ganz oben stehen.
load_dotenv()

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from config import config
from database import db
from services.email_service import init_email


def create_app(config_class=None):
    """Application factory"""
    if config_class is None:
        env = os.getenv('FLASK_ENV', 'development')
        config_class = config.get(env, config['development'])

    app = Flask(__name__, static_folder='components', static_url_path='/components')
    app.config.from_object(config_class)

    # Configure CORS for API endpoints
    # Note: Config class is selected based on FLASK_ENV at import time.
    # CORS defaults to localhost:3000 in development only, empty list in production (requires explicit CORS_ORIGINS env var).
    env = os.getenv('FLASK_ENV', 'development')
    default_origins = 'http://localhost:3000' if env != 'production' else ''
    cors_origins_str = os.getenv('CORS_ORIGINS', default_origins)
    cors_origins = [o.strip() for o in cors_origins_str.split(',') if o.strip()]

    CORS(app, resources={
        '/api/*': {
            'origins': cors_origins,
            'methods': ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
            'allow_headers': ['Content-Type', 'Authorization'],
            'supports_credentials': True
        }
    })

    # Initialize database
    db.init_app(app)

    # Initialize email service
    init_email(app)

    # Root route - serve index.html
    @app.route('/')
    def index():
        return send_file('index.html')

    # Login page route - serve login.html
    @app.route('/login')
    def login_page():
        return send_file('frontend/pages/login.html')

    # Login page route - alternative path
    @app.route('/pages/login.html')
    def login_page_alt():
        return send_file('frontend/pages/login.html')

    # Admin page route
    @app.route('/admin')
    def admin_page():
        return send_file('frontend/pages/admin.html')

    # Backup page route
    @app.route('/backup')
    def backup_page():
        return send_file('frontend/pages/backup.html')

    # Serve frontend/auth.js for login page
    @app.route('/frontend/auth.js')
    def serve_auth_js():
        return send_file('frontend/auth.js', mimetype='application/javascript')

    # Serve frontend/backup-client.js
    @app.route('/frontend/backup-client.js')
    def serve_backup_client_js():
        return send_file('frontend/backup-client.js', mimetype='application/javascript')

    # PWA Static-Files (manifest, service-worker) – ohne diese gibt's
    # 404-Errors in der Konsole und keine Push/Offline-Funktionalität.
    @app.route('/manifest.json')
    def serve_manifest():
        return send_file('manifest.json', mimetype='application/manifest+json')

    @app.route('/service-worker.js')
    def serve_service_worker():
        # Service Worker MUSS mit Service-Worker-Allowed Header serviert werden,
        # damit der Scope auf '/' liegt.
        resp = send_file('service-worker.js', mimetype='application/javascript')
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    @app.route('/favicon.ico')
    def serve_favicon():
        # 204 No Content falls keine favicon.ico existiert (verhindert 404-Spam).
        path = os.path.join(app.root_path, 'favicon.ico')
        if os.path.exists(path):
            return send_file('favicon.ico')
        return '', 204

    # Register blueprints
    from api.auth import auth_bp
    from api.applications import apps_bp
    from api.emails import emails_bp
    from api.admin import admin_bp
    from api.backup import backup_bp
    from api.profile import profile_bp
    from api.jobs_cron import jobs_cron_bp
    from claude_integration import claude_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(apps_bp)
    app.register_blueprint(emails_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(jobs_cron_bp)
    app.register_blueprint(claude_bp)

    # Error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        return {'error': 'Unauthorized'}, 401

    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500

    # Create tables on startup
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8080)
