# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import pytest


def _admin_headers(client, user_factory):
    """Promote user to admin and return auth headers."""
    from database import db
    user = user_factory()
    user.is_admin = True
    db.session.commit()
    from auth_service import AuthService
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def _user_headers(client, user_factory):
    user = user_factory()
    from auth_service import AuthService
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_list_platforms_admin_only(client, user_factory):
    headers, _ = _user_headers(client, user_factory)
    r = client.get("/api/admin/platforms", headers=headers)
    assert r.status_code == 403


def test_list_platforms_empty(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.get("/api/admin/platforms", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"platforms": []}


def test_create_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone",
            "display_name": "Stepstone",
            "domain": "stepstone.de",
            "subject_must_contain": ["stelle", "job"],
            "ai_schema_hint": "",
        },
        headers=headers,
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["slug"] == "stepstone"
    assert data["domain"] == "stepstone.de"


def test_create_rejects_reserved_slug(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "indeed",
            "display_name": "Indeed Custom",
            "domain": "example.com",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "reserviert" in r.get_json().get("error", "").lower()


def test_create_rejects_duplicate_slug(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    payload = {
        "slug": "stepstone", "display_name": "A", "domain": "a.de",
        "subject_must_contain": ["x"],
    }
    client.post("/api/admin/platforms", json=payload, headers=headers)
    r = client.post("/api/admin/platforms", json=payload, headers=headers)
    assert r.status_code == 400
    assert "existiert" in r.get_json().get("error", "").lower()


def test_create_rejects_invalid_slug_format(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "STEP STONE!",
            "display_name": "X", "domain": "x.de",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_rejects_invalid_domain(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone", "display_name": "Stepstone",
            "domain": "not a domain",
            "subject_must_contain": ["x"],
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_rejects_invalid_regex_override(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={
            "slug": "stepstone", "display_name": "Stepstone",
            "domain": "stepstone.de",
            "subject_must_contain": ["x"],
            "url_pattern_override": r"[invalid(regex",
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_update_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "Old", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    r = client.patch(
        "/api/admin/platforms/stepstone",
        json={"display_name": "New Name"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["display_name"] == "New Name"


def test_delete_platform(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "x", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    r = client.delete("/api/admin/platforms/stepstone", headers=headers)
    assert r.status_code == 200


def test_delete_blocked_when_jobsource_references_it(client, user_factory):
    from database import db
    from models import JobSource
    headers, admin = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "x", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    js = JobSource(
        name="Stepstone Test", type="stepstone_email",
        enabled=True,
    )
    js.config = {}
    db.session.add(js); db.session.commit()
    r = client.delete("/api/admin/platforms/stepstone", headers=headers)
    assert r.status_code == 409
    assert "JobSource" in r.get_json().get("error", "")


def test_update_nonexistent_platform_returns_404(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.patch(
        "/api/admin/platforms/nonexistent",
        json={"display_name": "X"},
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_nonexistent_platform_returns_404(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.delete("/api/admin/platforms/nonexistent", headers=headers)
    assert r.status_code == 404


def test_create_requires_admin(client, user_factory):
    headers, _ = _user_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={"slug": "xy", "display_name": "X", "domain": "x.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    assert r.status_code == 403


def test_update_requires_admin(client, user_factory):
    headers, _ = _user_headers(client, user_factory)
    r = client.patch(
        "/api/admin/platforms/any", json={"display_name": "X"},
        headers=headers,
    )
    assert r.status_code == 403


def test_delete_requires_admin(client, user_factory):
    headers, _ = _user_headers(client, user_factory)
    r = client.delete("/api/admin/platforms/any", headers=headers)
    assert r.status_code == 403


def test_create_rejects_empty_subject_must_contain(client, user_factory):
    headers, _ = _admin_headers(client, user_factory)
    r = client.post(
        "/api/admin/platforms",
        json={"slug": "xy", "display_name": "X", "domain": "x.de",
              "subject_must_contain": []},
        headers=headers,
    )
    assert r.status_code == 400
    assert "subject_must_contain" in r.get_json().get("error", "")


def test_patch_slug_change_rejected(client, user_factory):
    """PATCH mit slug-Änderung muss 400 zurückgeben (slug ist immutable)."""
    headers, _ = _admin_headers(client, user_factory)
    client.post(
        "/api/admin/platforms",
        json={"slug": "stepstone", "display_name": "Stepstone", "domain": "stepstone.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    r = client.patch(
        "/api/admin/platforms/stepstone",
        json={"slug": "newslug"},  # versuch slug zu ändern
        headers=headers,
    )
    assert r.status_code == 400
    assert "Slug" in r.get_json().get("error", "")


def test_create_rejects_slug_too_long(client, user_factory):
    """Slug > 26 chars wird abgelehnt (JobSource.type ist String(32))."""
    headers, _ = _admin_headers(client, user_factory)
    long_slug = "x" * 27
    r = client.post(
        "/api/admin/platforms",
        json={"slug": long_slug, "display_name": "X", "domain": "x.de",
              "subject_must_contain": ["x"]},
        headers=headers,
    )
    assert r.status_code == 400
