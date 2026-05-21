# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Baut .ics-Bytes aus ParsedInterview + Application-Metadaten."""

from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event, Alarm
from services.calendar_parser import ParsedInterview


def build_ics(
    application_id: str,
    company: str,
    position: str,
    parsed: ParsedInterview,
) -> bytes:
    """Erzeugt eine VCALENDAR mit einem VEVENT + 2 VALARMs (30min, 24h vorher).

    Erwartet einen ParsedInterview MIT start/end. Wenn start fehlt, ValueError.
    """
    if parsed.start is None or parsed.end is None:
        raise ValueError("ParsedInterview.start/end fehlen — kein Event möglich")

    cal = Calendar()
    cal.add("prodid", "-//Bewerbungstracker//Interview Export//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    event = Event()
    event.add("uid", f"{application_id}@bewerbungstracker")
    event.add("summary", f"Interview {company} — {position}")
    event.add("dtstart", parsed.start)
    event.add("dtend", parsed.end)
    event.add("dtstamp", datetime.now(timezone.utc))
    if parsed.location:
        event.add("location", parsed.location)
    if parsed.meeting_url:
        event.add("url", parsed.meeting_url)
    event.add("description", _description(company, position, parsed))

    for minutes_before in (30, 24 * 60):
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Interview {company}")
        alarm.add("trigger", timedelta(minutes=-minutes_before))
        event.add_component(alarm)

    cal.add_component(event)
    return cal.to_ical()


def _description(company: str, position: str, parsed: ParsedInterview) -> str:
    lines = [
        "Interview-Termin aus Bewerbungstracker.",
        "",
        f"Position: {position}",
        f"Firma: {company}",
    ]
    if parsed.meeting_url:
        lines += ["", f"Meeting-Link: {parsed.meeting_url}"]
    if parsed.passcode:
        lines.append(f"Passcode: {parsed.passcode}")
    return "\n".join(lines)
