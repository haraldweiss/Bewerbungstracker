# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session as SQLSession


db = SQLAlchemy()


def get_db() -> SQLSession:
    """Get current database session"""
    return db.session


def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)

    with app.app_context():
        db.create_all()


def reset_db(app):
    """Drop all tables and recreate (dev only)"""
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()
