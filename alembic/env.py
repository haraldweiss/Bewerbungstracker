# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from logging.config import fileConfig

from database import db
from models import *  # Important: imports all models
from config import Config

# this is the Alembic Config object, which provides
# the values of the [alembic] section of the .ini file
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = db.metadata


def _resolve_db_url() -> str:
    """Liefert die DB-URL die auch Flask-SQLAlchemy nutzt.

    Flask-SQLAlchemy löst relative SQLite-Pfade gegen `<app>/instance/` auf,
    Alembic per Default nicht. Damit beide auf dieselbe Datei zugreifen,
    bauen wir den absoluten Pfad explizit aus dem Flask-instance-Pfad.
    """
    url = os.getenv('DATABASE_URL', 'sqlite:///bewerbungstracker.db')
    if url.startswith('sqlite:///') and not url.startswith('sqlite:////'):
        # Relativer SQLite-Pfad → instance/-Verzeichnis davorsetzen
        rel = url[len('sqlite:///'):]
        instance_dir = Path(__file__).parent.parent / 'instance'
        instance_dir.mkdir(exist_ok=True)
        abs_path = (instance_dir / rel).resolve()
        url = f'sqlite:///{abs_path}'
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _resolve_db_url()

    context.configure(
        url=configuration["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _resolve_db_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
