#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Rebuild UserLearnProfile-Centroids aus historischen JobMatch-Daten.

Iteriert pro User über alle dismissed/imported Matches und ruft
update_centroid_for_feedback für jeden auf. Idempotent — alte Profile
werden vorher geleert.

Usage:
    python scripts/rebuild_user_centroids.py                # alle User
    python scripts/rebuild_user_centroids.py --user-id <id> # einen User
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import User, JobMatch, UserLearnProfile
from services.job_matching.learner import update_centroid_for_feedback


def rebuild_for_user(user):
    existing = UserLearnProfile.query.filter_by(user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    matches = (JobMatch.query
               .filter(JobMatch.user_id == user.id,
                       JobMatch.status.in_(['dismissed', 'imported']))
               .order_by(JobMatch.updated_at)
               .all())
    print(f'User {user.email}: {len(matches)} matches')
    done = 0
    for m in matches:
        try:
            update_centroid_for_feedback(user, m)
            db.session.commit()
            done += 1
        except Exception as e:
            print(f'  fail match_id={m.id}: {e}')
    print(f'  -> {done} aggregiert')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user-id', type=str, default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.user_id:
            user = User.query.get(args.user_id)
            if user is None:
                print('User not found')
                sys.exit(1)
            rebuild_for_user(user)
        else:
            for u in User.query.filter_by(job_discovery_enabled=True).all():
                rebuild_for_user(u)


if __name__ == '__main__':
    main()
