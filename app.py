#!/usr/bin/env python3
"""
Bewerbungstracker - Modernized Flask App with SQLAlchemy & JWT Auth
Factory pattern for Flask application creation
"""

from dotenv import load_dotenv
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from config import config
import os
from database import db

# Load environment variables from .env file
load_dotenv()


def create_app(config_class=None):
    """Application factory"""
    if config_class is None:
        env = os.getenv('FLASK_ENV', 'development')
        config_class = config.get(env, config['development'])

    app = Flask(__name__, static_folder='components', static_url_path='/components')
    app.config.from_object(config_class)

    # Configure CORS for API endpoints
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
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

    # Root route - serve index.html
    @app.route('/')
    def index():
        return send_file('index.html')

    # Register blueprints
    from api.auth import auth_bp
    from api.applications import apps_bp
    from api.emails import emails_bp
    from claude_integration import claude_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(apps_bp)
    app.register_blueprint(emails_bp)
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
