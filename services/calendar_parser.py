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

_RE_DATE_NUM = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+(?:um\s+)?(\d{1,2}):(\d{2})",
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


def parse_interview_event(text: str) -> ParsedInterview:
    if not text:
        return ParsedInterview(None, None, None, None, None)

    start = _extract_datetime(text)

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


def _extract_datetime(text: str) -> Optional[datetime]:
    m = _RE_DATE_ISO.search(text)
    if m:
        y, mo, d, h, mi = (int(x) for x in m.groups())
        return _safe_dt(y, mo, d, h, mi)

    m = _RE_DATE_NUM.search(text)
    if m:
        d, mo, y, h, mi = (int(x) for x in m.groups())
        return _safe_dt(y, mo, d, h, mi)

    return None


def _safe_dt(y, mo, d, h, mi) -> Optional[datetime]:
    try:
        return datetime(y, mo, d, h, mi, tzinfo=BERLIN)
    except ValueError:
        return None
