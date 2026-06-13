# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SQLSession


db = SQLAlchemy()


@event.listens_for(Engine, 'connect')
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """SQLite-Pragmas pro Connection setzen.

    WAL ist persistent im DB-File-Header, aber wir setzen es defensiv bei
    jeder neuen Connection (falls DB-File mal frisch erstellt wird). Wichtig
    bei Multi-Writer-Setup (gunicorn + task-worker-Daemon + Cron). Ohne WAL
    blockieren sich Reader und Writer gegenseitig → "database is locked".

    busy_timeout: wartet bis zu 10s bei Lock-Konflikten statt sofort zu
    failen — schützt vor Race zwischen kurz-lebigen Writes.
    """
    import sqlite3
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        # busy_timeout MUSS zuerst gesetzt werden: `journal_mode=WAL` braucht
        # selbst kurz einen Write-Lock, und ohne aktives busy_timeout failt es
        # SOFORT mit "database is locked" bei Multi-Writer-Contention (app +
        # worker + cron + email-service teilen sich eine SQLite-Datei). Erst den
        # Timeout setzen → die WAL-Pragma (und alles danach) wartet bis zu 10s.
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
    finally:
        cursor.close()


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
