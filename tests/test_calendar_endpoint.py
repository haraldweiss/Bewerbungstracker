# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from datetime import datetime
from icalendar import Calendar
from tests.fixtures.interview_emails import TKMS_BODY
from database import db
from models import Email


def _create_app(client, auth_token, notes=None, status=None):
    payload = {"company": "TKMS", "position": "System Security Engineer", "notes": notes or ""}
    if status:
        payload["status"] = status
    resp = client.post(
        "/api/applications",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_calendar_export_from_notes(client, auth_token):
    app_id = _create_app(client, auth_token, notes=TKMS_BODY)
    resp = client.get(
        f"/api/applications/{app_id}/calendar-event.ics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    assert "Interview-TKMS" in resp.headers.get("Content-Disposition", "")
    cal = Calendar.from_ical(resp.data)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1


def test_calendar_export_no_date_returns_400(client, auth_token):
    app_id = _create_app(client, auth_token, notes="Keine Termininformation hier.")
    resp = client.get(
        f"/api/applications/{app_id}/calendar-event.ics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 400
    assert "Termin" in resp.get_json().get("error", "")


def test_calendar_export_unknown_app_returns_404(client, auth_token):
    resp = client.get(
        "/api/applications/00000000-0000-0000-0000-000000000000/calendar-event.ics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


def test_calendar_export_requires_auth(client):
    resp = client.get("/api/applications/whatever/calendar-event.ics")
    assert resp.status_code == 401


def test_calendar_export_prefers_email_body_over_notes(app, client, auth_headers):
    """Email-Body mit Interview-Keyword schlägt notes-Fallback.

    Setup:
    - Application mit notes="alter Notiz-Text ohne Termin" (notes-Parser findet nichts)
    - Email mit subject 'Einladung Vorstellungsgespräch' + body=TKMS_BODY,
      verknüpft mit der Application via matched_application_id.

    Erwartet: Endpoint nutzt Email-Body → parsed Termin 2026-05-27 13:00.
    """
    headers, user = auth_headers
    token = headers["Authorization"].replace("Bearer ", "")

    app_id = _create_app(client, token, notes="alter Notiz-Text ohne Termin")

    with app.app_context():
        email = Email(
            user_id=user.id,
            subject="Einladung Vorstellungsgespräch — TKMS",
            body=TKMS_BODY,
            matched_application_id=app_id,
            timestamp=datetime(2026, 5, 20, 10, 0, 0),
        )
        db.session.add(email)
        db.session.commit()

    resp = client.get(
        f"/api/applications/{app_id}/calendar-event.ics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"

    cal = Calendar.from_ical(resp.data)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1
    dtstart = events[0].get("DTSTART").dt
    # Termin aus TKMS_BODY: 27.05.2026, 13:00 Europe/Berlin
    assert dtstart.year == 2026
    assert dtstart.month == 5
    assert dtstart.day == 27
    assert dtstart.hour == 13
    assert dtstart.minute == 0


def test_calendar_upcoming_includes_passcode_without_500(client, auth_token):
    app_id = _create_app(
        client,
        auth_token,
        notes=(
            "Einladung zum Vorstellungsgespraech am 03.07.2026 um 13:00 Uhr. "
            "Teams: https://teams.microsoft.com/meet/123?p=abc "
            "Passcode: KJ9wu6HU"
        ),
        status="interview",
    )

    resp = client.get(
        "/api/applications/upcoming",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert resp.status_code == 200
    events = resp.get_json()
    event = next(e for e in events if e["application_id"] == app_id)
    assert event["meeting_passcode"] == "KJ9wu6HU"
