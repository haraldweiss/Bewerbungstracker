"""End-to-end Tests fuer PATCH /api/jobs/matches/<id> mit quick_action."""
import json
import pytest

from database import db
from models import User, RawJob, JobMatch, JobSource, Application


@pytest.fixture
def setup(app, user_factory):
    with app.app_context():
        user = user_factory(email='qa@test.de')
        src = JobSource(
            user_id=user.id, name='t', type='manual', enabled=True,
        )
        src.config = {}
        db.session.add(src)
        db.session.commit()
        raw = RawJob(
            source_id=src.id, external_id='e1',
            title='Senior Security Analyst', company='Acme GmbH',
            url='https://x.test/1', description='d',
        )
        db.session.add(raw)
        db.session.commit()
        m = JobMatch(user_id=user.id, raw_job_id=raw.id, status='new')
        db.session.add(m)
        db.session.commit()
        return user.id, m.id, user


def auth_headers_for(user):
    from auth_service import AuthService
    token = AuthService.create_access_token(user.id)
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def test_patch_company_rejected_sets_status_and_creates_application(client, setup):
    user_id, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'company_rejected'},
                     headers=headers)
    assert r.status_code == 200
    m = db.session.get(JobMatch, m_id)
    assert m.status == 'dismissed'
    assert m.feedback_text == 'quick_action_company_rejected'
    apps = Application.query.filter_by(user_id=user_id, deleted=False).all()
    assert len(apps) == 1
    assert apps[0].status == 'absage'


def test_patch_already_applied_creates_beworben(client, setup):
    user_id, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'already_applied'},
                     headers=headers)
    assert r.status_code == 200
    apps = Application.query.filter_by(user_id=user_id, deleted=False).all()
    assert len(apps) == 1 and apps[0].status == 'beworben'


def test_patch_job_unavailable_only_marks_feedback(client, setup):
    user_id, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'job_unavailable'},
                     headers=headers)
    assert r.status_code == 200
    m = db.session.get(JobMatch, m_id)
    assert m.status == 'dismissed'
    assert m.feedback_text == 'job_no_longer_available'
    assert Application.query.filter_by(user_id=user_id).count() == 0


def test_quick_action_updates_learning_profile(client, setup):
    from models import JobEmbedding, UserLearnProfile
    from services.job_matching.embedder import vector_pack

    user_id, m_id, user = setup
    match = db.session.get(JobMatch, m_id)
    db.session.add(JobEmbedding(raw_job_id=match.raw_job_id, vector=vector_pack([1.0] + [0.0] * 767)))
    db.session.commit()

    r = client.patch(
        f'/api/jobs/matches/{m_id}',
        json={'quick_action': 'job_unavailable'},
        headers=auth_headers_for(user),
    )

    assert r.status_code == 200
    profile = UserLearnProfile.query.filter_by(user_id=user_id).first()
    assert profile is not None
    assert profile.samples_dismissed == 1


def test_patch_wrong_job_type_updates_user_blacklist(client, setup):
    user_id, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'wrong_job_type',
                           'job_type': 'werkstudent'},
                     headers=headers)
    assert r.status_code == 200
    u = db.session.get(User, user_id)
    assert json.loads(u.job_type_blacklist) == ['werkstudent']


def test_patch_400_unknown_quick_action(client, setup):
    _, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'not_a_thing'},
                     headers=headers)
    assert r.status_code == 400


def test_patch_400_wrong_job_type_missing_job_type(client, setup):
    _, m_id, user = setup
    headers = auth_headers_for(user)
    r = client.patch(f'/api/jobs/matches/{m_id}',
                     json={'quick_action': 'wrong_job_type'},
                     headers=headers)
    assert r.status_code == 400
