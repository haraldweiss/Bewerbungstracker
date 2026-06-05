"""Tests fuer apply_quick_action() — DB-Folgeaktionen."""
import json
from datetime import datetime, date

import pytest
from database import db
from models import User, RawJob, JobMatch, JobSource, Application


@pytest.fixture
def setup(app, user_factory):
    with app.app_context():
        user = user_factory()
        src = JobSource(
            user_id=user.id, name='t', type='manual', enabled=True,
        )
        src.config = {}
        db.session.add(src)
        db.session.commit()
        raw = RawJob(
            source_id=src.id, external_id='e1',
            title='Senior Security Analyst', company='Signal Iduna Group AG',
            url='https://x.test/1', description='d',
        )
        db.session.add(raw)
        db.session.commit()
        m = JobMatch(user_id=user.id, raw_job_id=raw.id, status='new')
        db.session.add(m)
        db.session.commit()
        yield (user, raw, m)


def test_company_rejected_creates_application(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='company_rejected')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        a = apps[0]
        assert a.company == 'Signal Iduna Group AG'
        assert a.position == 'Senior Security Analyst'
        assert a.status == 'absage'
        assert a.applied_date is None


def test_company_rejected_idempotent_upgrades_existing_to_absage(app, setup):
    user, raw, m = setup
    with app.app_context():
        existing = Application(
            user_id=user.id, company='signal iduna group ag',
            position='senior security analyst', status='beworben',
            applied_date=date.today(),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='company_rejected')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1, "kein duplicate insert"
        assert apps[0].status == 'absage'


def test_company_rejected_does_not_downgrade_zusage(app, setup):
    user, raw, m = setup
    with app.app_context():
        existing = Application(
            user_id=user.id, company='Signal Iduna Group AG',
            position='Senior Security Analyst', status='zusage',
            applied_date=date.today(),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='company_rejected')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'zusage', "absage darf zusage NICHT ueberschreiben"


def test_already_applied_creates_application_with_today(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='already_applied')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'beworben'
        assert apps[0].applied_date == date.today()


def test_already_applied_idempotent_skips_existing(app, setup):
    user, raw, m = setup
    with app.app_context():
        existing = Application(
            user_id=user.id, company='Signal Iduna Group AG',
            position='Senior Security Analyst', status='interview',
            applied_date=date(2026, 1, 1),
        )
        db.session.add(existing)
        db.session.commit()

        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='already_applied')

        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert len(apps) == 1
        assert apps[0].status == 'interview', "kein Status-Downgrade"
        assert apps[0].applied_date == date(2026, 1, 1)


def test_job_unavailable_creates_no_application(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw, action='job_unavailable')
        apps = Application.query.filter_by(user_id=user.id, deleted=False).all()
        assert apps == []


def test_wrong_job_type_appends_to_user_blacklist(app, setup):
    user, raw, m = setup
    with app.app_context():
        user = db.session.merge(user)
        assert json.loads(user.job_type_blacklist) == []
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='werkstudent')
        assert json.loads(user.job_type_blacklist) == ['werkstudent']


def test_wrong_job_type_idempotent(app, setup):
    user, raw, m = setup
    with app.app_context():
        user = db.session.merge(user)
        from services.job_matching.quick_actions import apply_quick_action
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='freelance')
        apply_quick_action(user=user, match=m, raw=raw,
                           action='wrong_job_type', job_type='freelance')
        assert json.loads(user.job_type_blacklist) == ['freelance']


def test_company_rejected_raises_on_empty_company(app, setup):
    user, raw, m = setup
    with app.app_context():
        raw.company = ''
        db.session.commit()
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='company_rejected')


def test_wrong_job_type_raises_on_missing_job_type(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='wrong_job_type', job_type=None)


def test_unknown_action_raises(app, setup):
    user, raw, m = setup
    with app.app_context():
        from services.job_matching.quick_actions import (
            apply_quick_action, QuickActionError,
        )
        with pytest.raises(QuickActionError):
            apply_quick_action(user=user, match=m, raw=raw,
                               action='not_a_real_action')
