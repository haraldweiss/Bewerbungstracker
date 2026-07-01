# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Parse Interview-Termin, Meeting-Link und Passcode aus deutschem Freitext
(Application.notes oder Email.body). Tz-aware Europe/Berlin."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

# German month names for parsing dates like "3. Juli 2026"
_GERMAN_MONTHS = {
    'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4, 'mai': 5, 'juni': 6,
    'juli': 7, 'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
}

_RE_DATE_NUM = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+(?:um\s+)?(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)
# Jahreslose deutsche Variante: "26.5. um 16:30" - kein Jahr direkt nach dem Tagespunkt.
# Negativer Lookahead (?!\d) verhindert Match auf "26.5.2026".
_RE_DATE_NUM_NOYEAR = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(?!\d)\s*(?:um\s+)?(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)
# Deutsche Monatsnamen: "3. Juli 2026 um 13:00 Uhr"
_RE_DATE_GERMAN_MONTH = re.compile(
    r"(\d{1,2})\.?\s+([a-zA-ZäöüÄÖÜ]+)\s+(\d{4})\s+um\s+(\d{1,2}):(\d{2})\s*Uhr?",
    re.IGNORECASE,
)
# Flexible Zeit: "2.6.2026 um 11 Uhr" (ohne Minuten)
_RE_DATE_FLEX_TIME = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+(?:um\s+)?(\d{1,2})(?::(\d{2}))?\s*Uhr?",
    re.IGNORECASE,
)
_RE_DATE_ISO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T\s]+(\d{1,2}):(\d{2})"
)
_RE_TEAMS = re.compile(
    r"https://teams\.microsoft\.com/meet/\d+(?:\?p=\S+)?",
    re.IGNORECASE,
)
_RE_ZOOM = re.compile(
    r"https://[a-z0-9.-]*zoom\.us/j/\d+(?:\?pwd=\S+)?",
    re.IGNORECASE,
)
_RE_PASSCODE = re.compile(
    r"Passcode:\s*([A-Za-z0-9;:.!@#$%^&*\-_]+)",
    re.IGNORECASE,
)
_RE_DURATION = re.compile(
    r"(\d{2,3})\s*(?:min|Minuten)",
    re.IGNORECASE,
)


@dataclass
class ParsedInterview:
    start: Optional[datetime]
    end: Optional[datetime]
    location: Optional[str]
    meeting_url: Optional[str]
    passcode: Optional[str]


def parse_interview_event(text: str, now: Optional[datetime] = None) -> ParsedInterview:
    """Parse Interview-Termin etc.

    ``now`` (tz-aware) wird nur fuer die Jahresaufloesung jahresloser Datums-
    angaben benoetigt. Wenn ``None``, verwendet die Funktion ``datetime.now(BERLIN)``.
    """
    if not text:
        return ParsedInterview(None, None, None, None, None)

    start = _extract_datetime(text, now=now)

    meeting_url = None
    location = None
    m_teams = _RE_TEAMS.search(text)
    m_zoom = _RE_ZOOM.search(text)
    if m_teams:
        meeting_url = m_teams.group(0)
        location = "MS Teams"
    elif m_zoom:
        meeting_url = m_zoom.group(0)
        location = "Zoom"

    duration_min = 60
    m_dur = _RE_DURATION.search(text)
    if m_dur:
        try:
            d = int(m_dur.group(1))
            if 5 <= d <= 240:
                duration_min = d
        except ValueError:
            pass
    end = start + timedelta(minutes=duration_min) if start else None

    passcode = None
    m_pass = _RE_PASSCODE.search(text)
    if m_pass:
        passcode = m_pass.group(1).strip()

    return ParsedInterview(
        start=start,
        end=end,
        location=location,
        meeting_url=meeting_url,
        passcode=passcode,
    )


def _extract_datetime(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    m = _RE_DATE_GERMAN_MONTH.search(text)
    if m:
        day, month_name, year, hour, minute = (int(m.group(1)), m.group(2).lower(), int(m.group(3)), int(m.group(4)), int(m.group(5)))
        month = _GERMAN_MONTHS.get(month_name)
        if month:
            return _safe_dt(year, month, day, hour, minute)

    m = _RE_DATE_FLEX_TIME.search(text)
    if m:
        day, month, year, hour, minute = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5) or 0))
        return _safe_dt(year, month, day, hour, minute)

    m = _RE_DATE_ISO.search(text)
    if m:
        y, mo, d, h, mi = (int(x) for x in m.groups())
        return _safe_dt(y, mo, d, h, mi)

    m = _RE_DATE_NUM.search(text)
    if m:
        d, mo, y, h, mi = (int(x) for x in m.groups())
        return _safe_dt(y, mo, d, h, mi)

    m = _RE_DATE_NUM_NOYEAR.search(text)
    if m:
        d, mo, h, mi = (int(x) for x in m.groups())
        y = _resolve_year(mo, d, now)
        return _safe_dt(y, mo, d, h, mi)

    return None


def _resolve_year(month: int, day: int, now: Optional[datetime]) -> int:
    """Jahr fuer jahresloses Datum aufloesen: aktuelles Jahr, falls Datum noch
    nicht vergangen ist, sonst naechstes Jahr."""
    if now is None:
        now = datetime.now(BERLIN)
    try:
        candidate = datetime(now.year, month, day, tzinfo=BERLIN)
    except ValueError:
        return now.year
    if candidate.date() < now.date():
        return now.year + 1
    return now.year


def _safe_dt(y, mo, d, h, mi) -> Optional[datetime]:
    try:
        return datetime(y, mo, d, h, mi, tzinfo=BERLIN)
    except ValueError:
        return None
