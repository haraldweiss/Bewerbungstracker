# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Sanity: neue User-Spalte job_type_blacklist hat Default '[]'."""
from models import User
from database import db


def test_user_default_job_type_blacklist_is_empty_array(app, user_factory):
    with app.app_context():
        u = user_factory()
        db.session.refresh(u)
        assert u.job_type_blacklist == '[]'
