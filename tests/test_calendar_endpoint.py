# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from icalendar import Calendar
from tests.fixtures.interview_emails import TKMS_BODY


def _create_app(client, auth_token, notes=None):
    resp = client.post(
        "/api/applications",
        json={"company": "TKMS", "position": "System Security Engineer", "notes": notes or ""},
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
