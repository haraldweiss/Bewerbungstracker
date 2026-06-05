# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Sanity: neue User-Spalte job_type_blacklist hat Default '[]'.

Zwei Pfade getestet:
1. ORM-Insert: Python-side `default='[]'` wird angewandt.
2. Raw-INSERT: SQL-side `server_default='[]'` wird angewandt — relevant
   für Alembic-Backfill bestehender Rows in Prod.
"""
import json

import sqlalchemy as sa

from models import User
from database import db


def test_user_default_job_type_blacklist_is_empty_array(app, user_factory):
    """ORM-Pfad: User-Factory legt User an, default greift Python-seitig."""
    with app.app_context():
        u = user_factory()
        db.session.refresh(u)
        assert u.job_type_blacklist == '[]'
        assert json.loads(u.job_type_blacklist) == []


def test_server_default_works_on_raw_insert(app):
    """SQL-Pfad: Raw-INSERT ohne default => server_default greift."""
    with app.app_context():
        db.session.execute(sa.text(
            "INSERT INTO users (id, email, password_hash, is_admin, "
            "email_confirmed, is_active, job_discovery_enabled, "
            "job_notification_threshold, job_claude_budget_per_tick, "
            "job_daily_budget_cents, ai_provider, job_reject_filter_enabled, "
            "job_reject_window_days, job_learn_enabled, job_learn_min_samples, "
            "job_learn_weight_pct) "
            "VALUES ('raw-id-1', 'raw@test.de', 'h', 0, 1, 1, 0, 80, 5, 50, "
            "'claude', 1, 180, 1, 3, 30)"
        ))
        db.session.commit()
        u = db.session.get(User, 'raw-id-1')
        assert u.job_type_blacklist == '[]'
        assert json.loads(u.job_type_blacklist) == []
