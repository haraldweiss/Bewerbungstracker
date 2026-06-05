"""Tests fuer GET/PATCH job_type_blacklist via /api/profile/job-discovery."""
import json
import pytest

from database import db
from models import User


@pytest.fixture
def auth_user(app, user_factory, auth_headers):
    headers, user = auth_headers
    return user, headers


def test_get_returns_job_type_blacklist(client, auth_user):
    user, headers = auth_user
    with client.application.app_context():
        user.job_type_blacklist = json.dumps(['werkstudent'])
        db.session.commit()

    r = client.get('/api/profile/job-discovery/status', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['filters']['job_type_blacklist'] == ['werkstudent']


def test_get_empty_blacklist_returns_empty_list(client, auth_user):
    user, headers = auth_user
    with client.application.app_context():
        user.job_type_blacklist = '[]'
        db.session.commit()

    r = client.get('/api/profile/job-discovery/status', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['filters']['job_type_blacklist'] == []


def test_patch_sets_job_type_blacklist(client, auth_user):
    user, headers = auth_user
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': ['werkstudent', 'freelance']},
        headers=headers,
    )
    assert r.status_code == 200
    with client.application.app_context():
        merged = db.session.merge(user)
        db.session.refresh(merged)
        assert sorted(json.loads(merged.job_type_blacklist)) == ['freelance', 'werkstudent']


def test_patch_rejects_invalid_job_type(client, auth_user):
    user, headers = auth_user
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': ['not_a_real_type']},
        headers=headers,
    )
    assert r.status_code == 400


def test_patch_rejects_non_list(client, auth_user):
    user, headers = auth_user
    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': 'werkstudent'},
        headers=headers,
    )
    assert r.status_code == 400


def test_patch_empty_list_clears_blacklist(client, auth_user):
    user, headers = auth_user
    with client.application.app_context():
        user.job_type_blacklist = json.dumps(['werkstudent'])
        db.session.commit()

    r = client.patch(
        '/api/profile/job-discovery/filters',
        json={'job_type_blacklist': []},
        headers=headers,
    )
    assert r.status_code == 200
    with client.application.app_context():
        merged = db.session.merge(user)
        db.session.refresh(merged)
        assert json.loads(merged.job_type_blacklist) == []
