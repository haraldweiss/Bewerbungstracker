# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from icalendar import Calendar
from services.calendar_parser import ParsedInterview
from services.calendar_ics import build_ics

BERLIN = ZoneInfo("Europe/Berlin")


def test_build_ics_minimal():
    parsed = ParsedInterview(
        start=datetime(2026, 5, 27, 13, 0, tzinfo=BERLIN),
        end=datetime(2026, 5, 27, 14, 0, tzinfo=BERLIN),
        location="MS Teams",
        meeting_url="https://teams.microsoft.com/meet/123",
        passcode=None,
    )
    ics_bytes = build_ics(
        application_id="app-uuid-1",
        company="TKMS",
        position="System Security Engineer",
        parsed=parsed,
    )
    cal = Calendar.from_ical(ics_bytes)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1
    event = events[0]
    assert "TKMS" in str(event["SUMMARY"])
    assert "System Security Engineer" in str(event["SUMMARY"])
    assert str(event["LOCATION"]) == "MS Teams"
    assert str(event["URL"]) == "https://teams.microsoft.com/meet/123"
    alarms = [c for c in event.subcomponents if c.name == "VALARM"]
    assert len(alarms) == 2


def test_build_ics_without_start_raises():
    parsed = ParsedInterview(start=None, end=None, location=None, meeting_url=None, passcode=None)
    with pytest.raises(ValueError):
        build_ics("a", "X", "Y", parsed)


def test_build_ics_includes_passcode_in_description():
    parsed = ParsedInterview(
        start=datetime(2026, 5, 27, 13, 0, tzinfo=BERLIN),
        end=datetime(2026, 5, 27, 14, 0, tzinfo=BERLIN),
        location="MS Teams",
        meeting_url="https://teams.microsoft.com/meet/123",
        passcode="QG9ms7xq",
    )
    ics_bytes = build_ics("a", "X", "Y", parsed)
    # RFC 5545 line-folding kann lange Zeilen mit "\r\n " umbrechen — entfalten vor Check
    unfolded = ics_bytes.replace(b"\r\n ", b"")
    assert b"QG9ms7xq" in unfolded
