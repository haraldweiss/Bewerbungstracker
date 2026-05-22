# SPDX-License-Identifier: AGPL-3.0-or-later
"""Test that JobSource-create accepts DB-defined platforms (e.g. stepstone_email)."""
import pytest


def _admin_headers(client, user_factory):
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


def test_create_source_accepts_db_platform(client, user_factory):
    """JobSource mit `<db_slug>_email` Type wird akzeptiert."""
    from database import db
    from models import PlatformProfileRow
    admin_headers, admin = _admin_headers(client, user_factory)

    # Erstelle DB-Plattform via Admin-API
    r = client.post("/api/admin/platforms", json={
        "slug": "stepstone", "display_name": "Stepstone", "domain": "stepstone.de",
        "subject_must_contain": ["stellenangebot"],
    }, headers=admin_headers)
    assert r.status_code == 201, r.get_json()

    # Source mit stepstone_email anlegen
    user_headers, _ = _user_headers(client, user_factory)
    r2 = client.post("/api/jobs/sources", json={
        "type": "stepstone_email",
        "name": "Meine Stepstone-Quelle",
        "config": {"folder": "INBOX", "lookback_days": 30},
    }, headers=user_headers)
    assert r2.status_code == 201, r2.get_json()


def test_create_source_rejects_unknown_email_platform(client, user_factory):
    """JobSource mit nicht-existierendem Plattform-Slug wird abgelehnt."""
    headers, _ = _user_headers(client, user_factory)
    r = client.post("/api/jobs/sources", json={
        "type": "doesnotexist_email",
        "name": "Test",
        "config": {"folder": "INBOX", "lookback_days": 30},
    }, headers=headers)
    assert r.status_code == 400


def test_create_source_still_validates_hardcoded_types(client, user_factory):
    """Hardcoded types (rss, adzuna, indeed_email, ...) funktionieren weiterhin."""
    headers, _ = _user_headers(client, user_factory)
    r = client.post("/api/jobs/sources", json={
        "type": "rss", "name": "Test",
        "config": {"url": "https://example.com/feed.xml"},
    }, headers=headers)
    # URL-safety prüft auf nicht-private IPs — example.com sollte OK sein
    assert r.status_code in (201, 400)  # 400 wenn URL als unsafe gilt; in beiden Fällen kein "type"-Fehler
    if r.status_code == 400:
        error = r.get_json().get("error", "")
        assert "type" not in error.lower()


def test_create_source_rejects_invalid_type(client, user_factory):
    """Komplett ungültiger Type (z.B. 'foo') wird abgelehnt."""
    headers, _ = _user_headers(client, user_factory)
    r = client.post("/api/jobs/sources", json={
        "type": "completely_invalid", "name": "Test", "config": {},
    }, headers=headers)
    assert r.status_code == 400


def test_email_import_endpoint_accepts_db_platform(client, user_factory):
    """Der Email-Import-Endpoint akzeptiert DB-Plattform-Sources."""
    from database import db
    from models import JobSource, PlatformProfileRow
    admin_headers, admin = _admin_headers(client, user_factory)

    # Erstelle DB-Plattform
    client.post("/api/admin/platforms", json={
        "slug": "stepstone", "display_name": "Stepstone", "domain": "stepstone.de",
        "subject_must_contain": ["job"],
    }, headers=admin_headers)

    # Source direkt in DB anlegen
    user_headers, user = _user_headers(client, user_factory)
    src = JobSource(
        user_id=user.id, name="My Stepstone", type="stepstone_email",
        enabled=True, crawl_interval_min=60,
    )
    src.config = {"folder": "INBOX", "lookback_days": 30}
    db.session.add(src); db.session.commit()

    # Import-Trigger sollte NICHT mit "kein Email-Typ" 400en
    r = client.post(f"/api/jobs/sources/{src.id}/indeed-import",
                    json={}, headers=user_headers)
    # 400 ist OK wenn z.B. IMAP-Credentials fehlen — aber nicht wegen Type
    if r.status_code == 400:
        error = r.get_json().get("error", "")
        assert "Email-Typ" not in error and "kein" not in error.lower(), \
            f"Type-Validation hat false-positive: {error}"
