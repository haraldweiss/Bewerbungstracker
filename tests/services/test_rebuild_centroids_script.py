# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Regressionstests fuer scripts/rebuild_user_centroids.py."""
from scripts import rebuild_user_centroids as ruc


def _user_with_two_dismissed_matches(db_session, user_factory):
    from models import JobEmbedding, JobMatch, JobSource, RawJob
    from services.job_matching.embedder import vector_pack

    user = user_factory()
    src = JobSource(name='rb', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add(src)
    db_session.flush()
    matches = []
    for i in range(2):
        raw = RawJob(source_id=src.id, external_id=f'r{i}', title='X', url=f'http://x/{i}')
        db_session.add(raw)
        db_session.flush()
        db_session.add(JobEmbedding(
            raw_job_id=raw.id, vector=vector_pack([1.0] + [0.0] * 767)))
        m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='dismissed')
        db_session.add(m)
        matches.append(m)
    db_session.commit()
    return user, matches


def test_rebuild_aggregates_all_matches(app, db_session, user_factory):
    from models import UserLearnProfile

    user, _ = _user_with_two_dismissed_matches(db_session, user_factory)

    ruc.rebuild_for_user(user)

    profile = UserLearnProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.samples_dismissed == 2


def test_rebuild_rolls_back_session_after_failure(app, db_session, user_factory, monkeypatch):
    """Schlaegt der Learner NACH Verschmutzen der Session fehl, darf der dirty
    State nicht vom commit() des naechsten Matches mitpersistiert werden —
    und die Schleife muss fuer die restlichen Matches weiterlaufen."""
    from database import db
    from models import UserLearnProfile

    user, matches = _user_with_two_dismissed_matches(db_session, user_factory)

    real = ruc.update_centroid_for_feedback

    def boom(u, m):
        if m.id == matches[0].id:
            # Simuliert Fehler nach teilweise geschriebenem State
            # (z.B. Exception zwischen add() und flush()).
            db.session.add(UserLearnProfile(user_id='orphan'))
            raise RuntimeError('boom')
        return real(u, m)

    monkeypatch.setattr(ruc, 'update_centroid_for_feedback', boom)

    ruc.rebuild_for_user(user)

    # Ohne rollback() waere das Orphan-Profil beim naechsten commit() mit
    # gespeichert worden.
    assert UserLearnProfile.query.filter_by(user_id='orphan').first() is None
    profile = UserLearnProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.samples_dismissed == 1
