#!/usr/bin/env python3
"""
Bewerbungstracker - Modernized Flask App with SQLAlchemy & JWT Auth
Factory pattern for Flask application creation
"""

from flask import Flask, jsonify
from config import config
import os
from database import db


def create_app(config_class=None):
    """Application factory"""
    if config_class is None:
        env = os.getenv('FLASK_ENV', 'development')
        config_class = config.get(env, config['development'])

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize database
    db.init_app(app)

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
