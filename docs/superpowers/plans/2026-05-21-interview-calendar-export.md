# Interview → Kalender (.ics) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pro Bewerbung eine `.ics`-Datei erzeugen lassen, die Interview-Termin
+ Teams/Zoom-Link enthält, parsbar aus `Application.notes` oder verknüpfter
`Email.body`. Frontend-Button im Detail-Modal triggert den Download.

**Architecture:** Reines Backend-Feature, kein DB-Schema-Change.
`services/calendar_parser.py` extrahiert Termin/Link/Passcode aus Freitext;
`services/calendar_ics.py` baut die .ics-Bytes; `api/calendar.py` ist der
Blueprint mit dem einen GET-Endpoint. Frontend ist ein zusätzlicher Button
im Detail-Modal in `index.html`.

**Tech Stack:** Flask Blueprint, `icalendar>=5.0` (neu), `zoneinfo` (stdlib),
Vanilla-JS-Fetch im Frontend.

**Spec:** `docs/superpowers/specs/2026-05-21-interview-calendar-export-design.md`

---

### Task 1: Parser-Modul mit TDD

**Files:**
- Create: `services/calendar_parser.py`
- Test: `tests/test_calendar_parser.py`

- [ ] **Step 1: Fixtures-Datei mit echten Mail-Texten anlegen**

Create `tests/fixtures/interview_emails.py`:

```python
"""Realistische Interview-Texte aus Mai 2026 — anonymisiert nur, falls nötig."""

TKMS_BODY = """Guten Tag Harald,

Wir laden Dich sehr herzlich zu einem Videointerview am 27.05.2026, um 13:00 (Europa/Berlin) Uhr, ein.

Um dich zum vereinbarten Termin einzuwählen, nutze bitte folgenden Link:
https://teams.microsoft.com/meet/369456768796951?p=eBRCEjJycl527BN1fv

Bitte plane rund 60 Minuten für unseren Austausch ein.
"""

ARVATO_BODY = """Hallo Harald,
Der Termin findet am Dienstag, den 26.05.2026, um 13:00 Uhr statt und ist auf etwa 60 Minuten angesetzt.

Microsoft Teams-Besprechung
Teilnehmen: https://teams.microsoft.com/meet/347973579379767?p=zM6lucnT4kcB6rBazd
Passcode: KJ9wu6HU
"""

ESET_BODY = """Lieber Harald,
Bitte logge dich am Freitag, den 22.05.2026 16:00 Uhr unter folgendem Link bei Teams ein:
https://teams.microsoft.com/meet/346349356596605?p=EaTH3u5tv6QVaCc9c5
Passcode: QG9ms7xq
"""

ARCTIC_WOLF_BODY = """Wed, Mar 18, 2026
10:00 AM - 10:30 AM ( Europe/Berlin )
https://arcticwolf.zoom.us/j/92396253627?pwd=gLYaaIubIvokEDtKIRxfIvasQEXKb7.1
(Password: 9chNu;)
"""
```

- [ ] **Step 2: Failing Test schreiben (TKMS happy path)**

Create `tests/test_calendar_parser.py`:

```python
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
```

- [ ] **Step 3: Run und FAIL bestätigen**

```bash
PYTHONPATH=. pytest tests/test_calendar_parser.py::test_parse_tkms_format -v
```
Expected: `ModuleNotFoundError: No module named 'services.calendar_parser'`

- [ ] **Step 4: Minimal-Implementation**

Create `services/calendar_parser.py`:

```python
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

# Numerisches Datum mit Uhrzeit: "27.05.2026 um 13:00", "27.05.2026, 13:00"
_RE_DATE_NUM = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+(?:um\s+)?(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)
# ISO-Datum: "2026-05-27T13:00" / "2026-05-27 13:00"
_RE_DATE_ISO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T\s]+(\d{1,2}):(\d{2})"
)
# Verbal: "Mittwoch, den 27.05.2026 um 13:00"  → fängt _RE_DATE_NUM ohnehin ab,
# aber wir wollen "den" tolerieren — der numerische Re reicht.

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

    # Datum
    start = _extract_datetime(text)

    # Link → Location
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

    # Dauer
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

    # Passcode
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
    # ISO first (eindeutiger)
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
```

- [ ] **Step 5: Test grün?**

```bash
PYTHONPATH=. pytest tests/test_calendar_parser.py::test_parse_tkms_format -v
```
Expected: PASS

- [ ] **Step 6: Weitere Tests anhängen**

Append to `tests/test_calendar_parser.py`:

```python
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
```

- [ ] **Step 7: Alle Parser-Tests laufen lassen**

```bash
PYTHONPATH=. pytest tests/test_calendar_parser.py -v
```
Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add services/calendar_parser.py tests/test_calendar_parser.py tests/fixtures/interview_emails.py
git commit -m "feat(calendar): parser für Interview-Termin/Link/Passcode aus Freitext"
```

---

### Task 2: .ics-Generator

**Files:**
- Modify: `requirements.txt` (add `icalendar>=5.0`)
- Create: `services/calendar_ics.py`
- Test: `tests/test_calendar_ics.py`

- [ ] **Step 1: Dependency installieren**

```bash
echo "icalendar>=5.0" >> requirements.txt
pip install 'icalendar>=5.0'
```

- [ ] **Step 2: Failing Test schreiben**

Create `tests/test_calendar_ics.py`:

```python
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
```

- [ ] **Step 3: Run und FAIL bestätigen**

```bash
PYTHONPATH=. pytest tests/test_calendar_ics.py -v
```
Expected: `ModuleNotFoundError: No module named 'services.calendar_ics'`

- [ ] **Step 4: Implementation**

Create `services/calendar_ics.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Baut .ics-Bytes aus ParsedInterview + Application-Metadaten."""

from datetime import datetime, timedelta
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
    event.add("dtstamp", datetime.utcnow())
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
```

- [ ] **Step 5: Test grün**

```bash
PYTHONPATH=. pytest tests/test_calendar_ics.py -v
```
Expected: PASS

- [ ] **Step 6: Negativ-Test ergänzen**

Append to `tests/test_calendar_ics.py`:

```python
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
    assert b"QG9ms7xq" in ics_bytes
```

- [ ] **Step 7: Run all ics-tests**

```bash
PYTHONPATH=. pytest tests/test_calendar_ics.py -v
```
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add services/calendar_ics.py tests/test_calendar_ics.py requirements.txt
git commit -m "feat(calendar): .ics-Generator mit Alarms + Description-Template"
```

---

### Task 3: API-Endpoint + Blueprint-Registrierung

**Files:**
- Create: `api/calendar.py`
- Modify: `app.py` (Blueprint registrieren)
- Test: `tests/test_calendar_endpoint.py`

- [ ] **Step 1: Failing Endpoint-Test**

Create `tests/test_calendar_endpoint.py`:

```python
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
```

- [ ] **Step 2: Run und FAIL bestätigen**

```bash
PYTHONPATH=. pytest tests/test_calendar_endpoint.py -v
```
Expected: Alle FAIL — Endpoint existiert nicht (404 oder 405).

- [ ] **Step 3: Endpoint implementieren**

Create `api/calendar.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""GET /api/applications/<id>/calendar-event.ics

Liefert eine .ics-Datei mit dem Interview-Termin der Bewerbung.
Quelle: neueste verknüpfte Email mit Interview-Keyword, sonst Application.notes.
"""

import re
from flask import Blueprint, jsonify, Response
from api.auth import token_required
from models import Application, Email
from services.calendar_parser import parse_interview_event
from services.calendar_ics import build_ics

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/applications")

_KEYWORDS = re.compile(r"(interview|vorstellung|gespr[äa]ch|kennenlernen|einladung)", re.IGNORECASE)


@calendar_bp.route("/<app_id>/calendar-event.ics", methods=["GET"])
@token_required
def export_calendar(user, app_id: str):
    app_obj = Application.query.filter_by(id=app_id, user_id=user.id, deleted=False).first()
    if not app_obj:
        return jsonify({"error": "Bewerbung nicht gefunden"}), 404

    text = _select_text(app_obj)
    parsed = parse_interview_event(text)
    if parsed.start is None:
        return jsonify({"error": "Kein Termin im Notes/Email-Text gefunden"}), 400

    ics_bytes = build_ics(
        application_id=app_obj.id,
        company=app_obj.company,
        position=app_obj.position,
        parsed=parsed,
    )
    safe_company = re.sub(r"[^A-Za-z0-9_-]+", "-", app_obj.company)[:50] or "Bewerbung"
    filename = f"Interview-{safe_company}.ics"
    return Response(
        ics_bytes,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def _select_text(app_obj: Application) -> str:
    """Bevorzugt Body der neuesten Email mit Interview-Keyword, sonst notes."""
    candidates = sorted(
        (e for e in (app_obj.emails or []) if (e.body or e.subject) and _KEYWORDS.search((e.subject or "") + " " + (e.body or ""))),
        key=lambda e: e.timestamp or e.created_at,
        reverse=True,
    )
    if candidates and candidates[0].body:
        return candidates[0].body
    return app_obj.notes or ""
```

- [ ] **Step 4: Blueprint in app.py registrieren**

Modify `app.py` (in `create_app`, beim Block "Register blueprints"):

```python
    from api.calendar import calendar_bp
    # ... (nach den bestehenden Imports)
    app.register_blueprint(calendar_bp)
```

Exakte Insertion-Stelle: nach `from claude_integration import claude_bp` ergänzen
`from api.calendar import calendar_bp`, und nach `app.register_blueprint(claude_bp)`
ergänzen `app.register_blueprint(calendar_bp)`.

- [ ] **Step 5: Tests laufen lassen**

```bash
PYTHONPATH=. pytest tests/test_calendar_endpoint.py -v
```
Expected: 4 passed

- [ ] **Step 6: Regression — vorhandene Tests**

```bash
PYTHONPATH=. pytest tests/test_applications.py tests/test_auth_endpoints.py -v
```
Expected: Alle weiterhin grün.

- [ ] **Step 7: Commit**

```bash
git add api/calendar.py app.py tests/test_calendar_endpoint.py
git commit -m "feat(calendar): GET /api/applications/<id>/calendar-event.ics"
```

---

### Task 4: Frontend-Button im Detail-Modal

**Files:**
- Modify: `index.html` (Detail-Modal-Render-Funktion + neue JS-Funktion)
- Modify: `service-worker.js` (`CACHE_NAME` bump)

- [ ] **Step 1: Button-HTML im Detail-Modal einfügen**

In `index.html`, in der Funktion `showDetail(id)` direkt vor dem schließenden
`</div>` des `detail-grid` (etwa Zeile 5056, **nach** dem `notizen`-Block,
**vor** dem ` `): füge eine neue Section ein:

```javascript
            ${['antwort','interview','zusage'].includes(b.status) ? `
            <div class="detail-section" style="grid-column:1/-1;">
                <button onclick="exportInterviewCalendar('${id}','${escAttr(b.firma||'Bewerbung')}')"
                        class="btn btn-secondary"
                        style="display:inline-flex;align-items:center;gap:0.5rem;">
                    📅 In Kalender exportieren (.ics)
                </button>
                <div style="font-size:0.78rem;color:var(--text-muted);margin-top:0.4rem;">
                    Erzeugt eine Kalender-Datei aus Termin/Link in den Notizen.
                </div>
            </div>` : ''}
```

(`escAttr` ist eine bereits vorhandene Helper-Funktion; falls nicht
auffindbar via `grep -n "function escAttr\|escAttr =" index.html`, verwende
`escHtml` und kümmere dich um Quotes manuell.)

- [ ] **Step 2: JS-Funktion `exportInterviewCalendar` hinzufügen**

In `index.html`, nach der `showDetail`-Funktion (etwa Zeile 5059), füge ein:

```javascript
async function exportInterviewCalendar(id, firma) {
    try {
        const response = await Auth.fetch(`/api/applications/${id}/calendar-event.ics`);
        if (response.status === 400) {
            showToast('Kein Termin in den Notizen erkannt — bitte ergänzen und erneut versuchen.', 'warning');
            return;
        }
        if (!response.ok) {
            showToast(`Export fehlgeschlagen: ${response.status}`, 'error');
            return;
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const safeFirma = (firma || 'Bewerbung').replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 50);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Interview-${safeFirma}.ics`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Kalender-Datei heruntergeladen.', 'success');
    } catch (err) {
        console.error('Calendar export failed', err);
        showToast('Export fehlgeschlagen — siehe Konsole.', 'error');
    }
}
```

(`showToast` ist eine bereits vorhandene Notification-Funktion. Falls nicht,
mit `grep -n "function showToast\|showToast =" index.html` verifizieren.)

- [ ] **Step 3: Service-Worker Cache bumpen**

In `service-worker.js`, finde die Zeile `const CACHE_NAME = 'bewerbungstracker-vXX';`
(grep: `grep -n "CACHE_NAME" service-worker.js`). Erhöhe die Versionsnummer um 1.

- [ ] **Step 4: Manueller Smoke-Test (lokal)**

```bash
./start.sh
```

Im Browser auf `http://localhost:8080`:
1. Login.
2. Bewerbung mit Status `interview` öffnen (oder eine mit TKMS-Notes anlegen).
3. „📅 In Kalender exportieren" klicken → Browser lädt `Interview-TKMS.ics`.
4. Datei doppelklicken → öffnet sich in Apple Calendar mit korrektem Termin.

- [ ] **Step 5: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(frontend): kalender-export-button im detail-modal + SW bump"
```

---

### Task 5: Deploy + Smoke-Test auf VPS

- [ ] **Step 1: Push**

```bash
git push origin master
```

- [ ] **Step 2: VPS-Deploy via Standard-Routine**

```bash
ssh ionos-vps "/usr/local/bin/bewerbungen-deploy.sh"
```

Erwartet: `pull + pip install + alembic upgrade + service restart + smoke OK`.

- [ ] **Step 3: Endpoint-Smoke-Test auf Prod**

```bash
TOKEN=$(curl -s -X POST https://bewerbungstracker.de/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"harald.weiss","password":"<lokal-eingeben>"}' | jq -r '.access_token')
curl -s -o /tmp/test.ics -w "%{http_code}\n" \
    "https://bewerbungstracker.de/api/applications/<eine-bewerbung-id>/calendar-event.ics" \
    -H "Authorization: Bearer $TOKEN"
head -20 /tmp/test.ics
```

Expected: `200`, Body beginnt mit `BEGIN:VCALENDAR`.

- [ ] **Step 4: Im Browser**

PWA neu laden (Cache-Bump zieht), Detail-Modal einer Interview-Bewerbung →
Button vorhanden, Download funktioniert, .ics importiert sich in den Kalender.

- [ ] **Step 5: Done — keine weiteren Commits**

Wenn alles grün: nichts zu tun. Sollte der Smoke-Test scheitern, Logs prüfen:

```bash
ssh ionos-vps "journalctl -u bewerbungen --since '5 minutes ago' | tail -50"
```

---

## Self-Review

- ✅ Alle Spec-Sektionen sind durch Tasks abgedeckt:
  - Architektur → Task 3 (Endpoint) + Task 4 (Frontend)
  - Parser-Spec → Task 1
  - .ics-Generierung → Task 2
  - Error-Handling (404/400/401) → Task 3 Step 1 (4 Endpoint-Tests)
  - Testing-Plan → Task 1+2+3 (mit Fixtures)
  - Deployment-Hinweise → Task 5 + Task 4 Step 3 (SW-Bump)
- ✅ Keine Placeholder, alle Code-Blöcke vollständig
- ✅ Funktionsnamen konsistent zwischen Tasks (`parse_interview_event`, `build_ics`, `ParsedInterview`, `exportInterviewCalendar`)
- ✅ Test-Fixtures (`tests/fixtures/interview_emails.py`) werden in Task 1 angelegt, in Task 3 wiederverwendet
