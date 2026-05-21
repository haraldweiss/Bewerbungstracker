# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from services.calendar_parser import parse_interview_event
from tests.fixtures.interview_emails import TKMS_BODY


BERLIN = ZoneInfo("Europe/Berlin")


def test_parse_tkms_format():
    result = parse_interview_event(TKMS_BODY)
    assert result.start == datetime(2026, 5, 27, 13, 0, tzinfo=BERLIN)
    assert result.end == datetime(2026, 5, 27, 14, 0, tzinfo=BERLIN)  # default 60min
    assert result.meeting_url == "https://teams.microsoft.com/meet/369456768796951?p=eBRCEjJycl527BN1fv"
    assert result.location == "MS Teams"
    assert result.passcode is None


from tests.fixtures.interview_emails import ARVATO_BODY, ESET_BODY, ARCTIC_WOLF_BODY


def test_parse_arvato_with_passcode():
    result = parse_interview_event(ARVATO_BODY)
    assert result.start == datetime(2026, 5, 26, 13, 0, tzinfo=BERLIN)
    assert result.meeting_url == "https://teams.microsoft.com/meet/347973579379767?p=zM6lucnT4kcB6rBazd"
    assert result.passcode == "KJ9wu6HU"


def test_parse_eset_format():
    result = parse_interview_event(ESET_BODY)
    assert result.start == datetime(2026, 5, 22, 16, 0, tzinfo=BERLIN)
    assert result.passcode == "QG9ms7xq"


def test_parse_zoom_link():
    result = parse_interview_event(ARCTIC_WOLF_BODY)
    assert result.location == "Zoom"
    assert "zoom.us/j/92396253627" in result.meeting_url


def test_parse_empty_returns_none():
    result = parse_interview_event("")
    assert result.start is None
    assert result.end is None
    assert result.meeting_url is None


def test_parse_text_without_date():
    result = parse_interview_event("Nur ein Link: https://teams.microsoft.com/meet/123 ohne Datum")
    assert result.start is None
    assert result.meeting_url == "https://teams.microsoft.com/meet/123"


def test_parse_custom_duration():
    text = "Termin am 01.06.2026 um 10:00, ca. 90 Minuten."
    result = parse_interview_event(text)
    assert result.start == datetime(2026, 6, 1, 10, 0, tzinfo=BERLIN)
    assert result.end == datetime(2026, 6, 1, 11, 30, tzinfo=BERLIN)
