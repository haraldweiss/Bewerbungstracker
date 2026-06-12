# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from scripts.reeval_technical_failures import select_candidates, reset_match


def test_selects_dismissed_failure_without_human_judgment(app, db_session, user_factory):
    from models import RawJob, JobMatch, JobSource
    u = user_factory()
    src1 = JobSource(name='t1', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    src2 = JobSource(name='t2', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add_all([src1, src2]); db_session.flush()
    raw1 = RawJob(source_id=src1.id, external_id='a1', title='X', description='Y', url='http://x')
    raw2 = RawJob(source_id=src2.id, external_id='a2', title='Y', description='Z', url='http://y')
    db_session.add_all([raw1, raw2]); db_session.flush()
    fail = JobMatch(raw_job_id=raw1.id, user_id=u.id, status='dismissed', match_score=0.0,
                    match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                    feedback_reasons=None)
    human = JobMatch(raw_job_id=raw2.id, user_id=u.id, status='dismissed', match_score=0.0,
                     match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                     feedback_reasons='["wrong_seniority"]')
    db_session.add_all([fail, human]); db_session.commit()
    ids = {m.id for m in select_candidates()}
    assert fail.id in ids
    assert human.id not in ids        # menschliches Urteil respektiert


def test_reset_match_makes_retriable(app, db_session, user_factory):
    from models import RawJob, JobMatch, JobSource
    u = user_factory()
    raw_src = JobSource(name='t2', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add(raw_src); db_session.flush()
    raw = RawJob(source_id=raw_src.id, external_id='b', title='X', description='Y', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, status='dismissed', match_score=0.0,
                 match_reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                 notified_at=None, eval_attempts=0)
    db_session.add(m); db_session.commit()
    reset_match(m)
    db_session.commit()
    assert m.status == 'new'
    assert m.match_score is None
    assert m.match_reasoning is None
    assert m.eval_attempts == 1       # Retry-Zweig greift
