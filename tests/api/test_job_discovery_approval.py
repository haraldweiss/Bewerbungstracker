"""Tests für Job-Discovery Admin-Approval-Workflow."""
import json
import pytest

from auth_service import AuthService
from database import db
from models import User


@pytest.fixture
def admin_headers(user_factory):
    """Admin-User + JWT-Header."""
    admin = user_factory(email="admin@test.de", is_admin=True)
    token = AuthService.create_access_token(admin.id)
    return ({"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, admin)


def test_request_job_discovery_sets_timestamp(client, auth_headers):
    headers, user = auth_headers
    r = client.post("/api/profile/job-discovery/request", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "pending_approval"
    assert body["requested_at"] is not None
    assert body["enabled"] is False

    db.session.refresh(user)
    assert user.job_discovery_requested_at is not None
    assert user.job_discovery_enabled is False


def test_request_job_discovery_idempotent(client, auth_headers):
    headers, user = auth_headers
    r1 = client.post("/api/profile/job-discovery/request", headers=headers)
    first_ts = r1.get_json()["requested_at"]

    r2 = client.post("/api/profile/job-discovery/request", headers=headers)
    second_ts = r2.get_json()["requested_at"]

    assert first_ts == second_ts  # nicht überschrieben


def test_request_already_enabled_returns_status(client, auth_headers):
    headers, user = auth_headers
    user.job_discovery_enabled = True
    db.session.commit()

    r = client.post("/api/profile/job-discovery/request", headers=headers)
    body = r.get_json()
    assert body["status"] == "enabled"
    assert body["enabled"] is True


def test_status_endpoint(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/profile/job-discovery/status", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["status"] == "not_requested"


def test_cv_update_returns_first_upload_flag(client, auth_headers):
    headers, _ = auth_headers
    r = client.put("/api/profile/cv", json={"cv": {"skills": ["python"]}}, headers=headers)
    body = r.get_json()
    assert body["is_first_cv_upload"] is True

    # Zweiter Upload sollte das Flag NICHT mehr setzen
    r2 = client.put("/api/profile/cv", json={"cv": {"skills": ["python", "react"]}}, headers=headers)
    assert r2.get_json()["is_first_cv_upload"] is False


def test_cv_update_no_first_flag_when_already_requested(client, auth_headers):
    headers, user = auth_headers
    from datetime import datetime
    user.job_discovery_requested_at = datetime.utcnow()
    db.session.commit()

    r = client.put("/api/profile/cv", json={"cv": {"skills": ["python"]}}, headers=headers)
    assert r.get_json()["is_first_cv_upload"] is False


def test_admin_lists_pending_requests(client, app, user_factory, admin_headers):
    headers, _ = admin_headers
    requesting = user_factory(email="want-jd@test.de")
    from datetime import datetime
    requesting.job_discovery_requested_at = datetime.utcnow()
    requesting.cv_data_json = '{"cv":{"skills":["a"]}}'
    db.session.commit()

    # Anderer User ohne Request — soll NICHT erscheinen
    user_factory(email="no-request@test.de")

    r = client.get("/api/admin/job-discovery-requests", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1
    assert body["requests"][0]["email"] == "want-jd@test.de"
    assert body["requests"][0]["has_cv"] is True


def test_admin_approve_job_discovery(client, user_factory, admin_headers):
    headers, _ = admin_headers
    target = user_factory(email="approve-me@test.de")
    from datetime import datetime
    target.job_discovery_requested_at = datetime.utcnow()
    target.cv_data_json = '{"cv":{"skills":["a"]}}'
    db.session.commit()

    r = client.post(f"/api/admin/users/{target.id}/approve-job-discovery", headers=headers)
    assert r.status_code == 200
    db.session.refresh(target)
    assert target.job_discovery_enabled is True


def test_admin_approve_fails_without_cv(client, user_factory, admin_headers):
    headers, _ = admin_headers
    target = user_factory(email="no-cv@test.de")
    from datetime import datetime
    target.job_discovery_requested_at = datetime.utcnow()
    db.session.commit()

    r = client.post(f"/api/admin/users/{target.id}/approve-job-discovery", headers=headers)
    assert r.status_code == 400
    assert "Lebenslauf" in r.get_json()["error"]


def test_admin_approve_fails_without_request(client, user_factory, admin_headers):
    headers, _ = admin_headers
    target = user_factory(email="never-asked@test.de")
    target.cv_data_json = '{"cv":{}}'
    db.session.commit()

    r = client.post(f"/api/admin/users/{target.id}/approve-job-discovery", headers=headers)
    assert r.status_code == 400
    assert "request" in r.get_json()["error"].lower()


def test_admin_deny_resets_request(client, user_factory, admin_headers):
    headers, _ = admin_headers
    target = user_factory(email="deny@test.de")
    from datetime import datetime
    target.job_discovery_requested_at = datetime.utcnow()
    db.session.commit()

    r = client.post(f"/api/admin/users/{target.id}/deny-job-discovery", headers=headers)
    assert r.status_code == 200
    db.session.refresh(target)
    assert target.job_discovery_requested_at is None


def test_non_admin_cannot_list_requests(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/admin/job-discovery-requests", headers=headers)
    assert r.status_code in (401, 403)


# ─── Filter-PATCH-Endpoint ───────────────────────────────────────────

def test_patch_filters_updates_region_and_threshold(client, auth_headers):
    headers, user = auth_headers
    r = client.patch('/api/profile/job-discovery/filters', json={
        'job_region_filter': {'plz_prefixes': ['44', '97'], 'remote_ok': True,
                              'employment_types': ['vollzeit']},
        'job_notification_threshold': 75,
    }, headers=headers)
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.job_region_filter == {
        'plz_prefixes': ['44', '97'], 'remote_ok': True, 'employment_types': ['vollzeit']
    }
    assert user.job_notification_threshold == 75


def test_patch_filters_clears_region_when_null(client, auth_headers):
    headers, user = auth_headers
    user.job_region_filter = {'plz_prefixes': ['10'], 'remote_ok': False}
    db.session.commit()

    r = client.patch('/api/profile/job-discovery/filters',
                     json={'job_region_filter': None}, headers=headers)
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.job_region_filter is None


def test_patch_filters_validates_threshold_range(client, auth_headers):
    headers, _ = auth_headers
    r = client.patch('/api/profile/job-discovery/filters',
                     json={'job_notification_threshold': 150}, headers=headers)
    assert r.status_code == 400


def test_patch_filters_validates_plz_prefixes_format(client, auth_headers):
    headers, _ = auth_headers
    r = client.patch('/api/profile/job-discovery/filters', json={
        'job_region_filter': {'plz_prefixes': [44, 97], 'remote_ok': True}
    }, headers=headers)
    # Numbers statt Strings → 400
    assert r.status_code == 400


def test_status_endpoint_returns_filters(client, auth_headers):
    headers, user = auth_headers
    user.job_notification_threshold = 65
    user.job_region_filter = {'plz_prefixes': ['44'], 'remote_ok': True}
    db.session.commit()

    r = client.get('/api/profile/job-discovery/status', headers=headers)
    body = r.get_json()
    assert 'filters' in body
    assert body['filters']['job_notification_threshold'] == 65
    assert body['filters']['job_region_filter']['plz_prefixes'] == ['44']
