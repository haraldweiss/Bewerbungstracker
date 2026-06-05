# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cron-Prefilter dismissed Matches, deren Job-Typ in User-Blacklist steht."""
import json
import pytest
from datetime import datetime

from database import db
from models import User, RawJob, JobMatch, JobSource


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ENCRYPTION_KEY", "rYJrSGE_CPN0eL4Z5VYC0YMyhc4FU8X3uVlS8mPWyTw=")
    from app import create_app
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_source(user):
    src = JobSource(
        user_id=user.id, name='test-src', type='manual',
        enabled=True,
    )
    src.config = {}
    db.session.add(src)
    db.session.commit()
    return src


def _make_match(user, src, title, company='Acme'):
    raw = RawJob(
        source_id=src.id, external_id=f'ext-{title}',
        title=title, company=company, url=f'https://x.test/{title}',
        description='lorem ipsum',
    )
    db.session.add(raw)
    db.session.commit()
    m = JobMatch(
        user_id=user.id, raw_job_id=raw.id, status='new',
        prefilter_score=None,
    )
    db.session.add(m)
    db.session.commit()
    return m


def test_prefilter_dismisses_blacklisted_job_type(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist=json.dumps(['werkstudent']),
            cv_data_json=json.dumps({'cv': {'skills': ['python'], 'summary': ''}}),
        )
        src = _make_source(user)
        m = _make_match(user, src, 'Werkstudent IT-Support')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        result = handle_cron_prefilter({})

        db.session.refresh(m)
        assert m.status == 'dismissed'
        assert m.feedback_text == 'wrong_job_type_blocked'
        assert result['dismissed'] >= 1


def test_prefilter_keeps_non_blacklisted_job_type(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist=json.dumps(['werkstudent']),
            cv_data_json=json.dumps({
                'cv': {'skills': ['python', 'security'],
                       'summary': 'security analyst'}
            }),
        )
        src = _make_source(user)
        m = _make_match(user, src, 'Senior Security Analyst (m/w/d)')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        handle_cron_prefilter({})

        db.session.refresh(m)
        # Either remains 'new' or 'dismissed' for other reason — but NOT
        # wrong_job_type_blocked.
        assert m.feedback_text != 'wrong_job_type_blocked'


def test_prefilter_skips_check_when_blacklist_empty(app, user_factory):
    with app.app_context():
        user = user_factory(
            job_type_blacklist='[]',
            cv_data_json=json.dumps({
                'cv': {'skills': ['python'], 'summary': ''}
            }),
        )
        src = _make_source(user)
        m = _make_match(user, src, 'Werkstudent IT-Support')

        from services.tasks.handlers.cron_prefilter import handle_cron_prefilter
        handle_cron_prefilter({})

        db.session.refresh(m)
        # Mit leerer Blacklist darf der Werkstudent-Block NICHT greifen.
        assert m.feedback_text != 'wrong_job_type_blocked'
