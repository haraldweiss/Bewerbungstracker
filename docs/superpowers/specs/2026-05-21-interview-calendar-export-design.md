# Interview → Kalender-Export (.ics)

**Datum:** 2026-05-21
**Status:** Spec genehmigt, bereit für Implementation-Plan

## Motivation

Aktuell stehen Interview-Termine im freitextlichen `notes`-Feld der Bewerbung
(oder, sobald der Email-Import läuft, im Body der zugeordneten `Email`).
Der User muss Datum, Teams-Link, Passcode etc. manuell aus dem Text kopieren
und in seinem Kalender anlegen — das passiert pro Interview 1×, ist fehleranfällig
und unbefriedigend.

Ein „📅 In Kalender exportieren"-Button im Bewerbungs-Detail soll daraus
ein `.ics`-File generieren, das mit einem Klick in Apple Calendar, Google
Calendar oder Outlook importiert werden kann.

## Nicht-Ziele (YAGNI)

- Kein OAuth-basierter Push in Google/iCloud — der User hat Multi-Geräte-Setup,
  `.ics` deckt das ohne API-Komplexität ab.
- Keine strukturierten Termin-Felder in der DB (`interview_termin`, …) — bricht
  vorhandene Bewerbungen, und der Parser über `notes`/Email-Body funktioniert
  bereits für den realen Datenstand.
- Keine Mehrfach-Interview-Runden pro Bewerbung — eine Bewerbung = ein Termin.
  Wenn das später nötig wird, wird es separat designed.

## Architektur

**Backend** — neues Modul `api/calendar.py`:

- `GET /api/applications/<id>/calendar-event.ics`
  - Auth via Bearer-Token (wie restliche Endpoints).
  - Lädt `Application` + `Application.emails` (neueste zuerst).
  - Ruft `parse_interview_event(application)` auf.
  - Bei Erfolg: `200 text/calendar; charset=utf-8`, `Content-Disposition: attachment; filename="Interview-<firma>.ics"`.
  - Bei Parse-Fehler: `400 {"error": "Kein Termin im Notes/Email-Text gefunden"}`.

**Frontend** — in `index.html` (Detail-Modal, vor Notes):

- Button `📅 In Kalender exportieren` sichtbar wenn `status ∈ {antwort, interview, zusage}`.
- Klick → Fetch `/api/applications/<id>/calendar-event.ics` mit Auth-Header
- Bei `200`: Blob als Download triggern (`<a download="…">.click()`).
- Bei `400`: Toast „Konnte keinen Termin extrahieren — bitte Notizen prüfen".

Kein Preview-Modal in der MVP — das wird ggf. nachgereicht, wenn der Parser
zu oft daneben liegt.

## Parser-Spezifikation

### Quellen-Priorität

1. `Application.emails` — neueste Email-Row, deren `subject` oder `body`
   eines der Keywords enthält: `interview|vorstellung|gespräch|kennenlernen|einladung`.
   Verwende `email.body`.
2. Fallback: `application.notes`.

Wenn beide leer oder ohne Datum → 400.

### Extraktions-Regeln

Alle Patterns werden in einer single-pass-Funktion `parse_interview_event(text)`
angewandt. Erste passende Übereinstimmung gewinnt pro Feld.

| Feld | Pattern (Python-Regex, `re.IGNORECASE`) | Beispiel-Treffer |
|---|---|---|
| Datum + Zeit | `(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+(?:um\s+)?(\d{1,2}):(\d{2})` | `27.05.2026, um 13:00` |
| Datum + Zeit (ISO) | `(\d{4})-(\d{2})-(\d{2})[T\s]+(\d{1,2}):(\d{2})` | `2026-05-27T13:00` |
| Datum + Zeit (verbal) | `(?:Montag|Dienstag|…|Sonntag),?\s+(?:den\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})[,\s]+um\s+(\d{1,2}):(\d{2})` | `Mittwoch, den 27.05.2026 um 13:00` |
| Teams-Link | `https://teams\.microsoft\.com/meet/\d+(?:\?p=\S+)?` | `https://teams.microsoft.com/meet/369456768796951?p=eBRCEjJycl527BN1fv` |
| Zoom-Link | `https://[a-z0-9.-]*zoom\.us/j/\d+(?:\?pwd=\S+)?` | `https://arcticwolf.zoom.us/j/92396253627?pwd=…` |
| Passcode | `Passcode:\s*([A-Za-z0-9;:.!@#$%^&*\-_]+)` | `Passcode: QG9ms7xq` |
| Dauer (min) | `(\d{2,3})\s*(?:min|Minuten|Stunde)` | `60 Minuten` → 60 |

**Dauer-Default:** 60 Minuten.
**Zeitzone:** `Europe/Berlin` (hartcodiert; alle Bewerbungen sind deutsch).

### Rückgabe

```python
ParsedInterview(
    start: datetime,        # tz-aware Europe/Berlin
    end: datetime,
    location: str | None,   # "MS Teams" / "Zoom" / None
    meeting_url: str | None,
    passcode: str | None,
)
```

`location` wird aus dem gefundenen Link-Host abgeleitet.

## .ics-Generierung

Bibliothek: `icalendar` (Python). Steht nicht in `requirements.txt`, wird mit-installiert.

### Feldmapping

```text
BEGIN:VEVENT
UID            = <application_id>@bewerbungstracker
SUMMARY        = Interview {company} — {position}
DTSTART;TZID=Europe/Berlin = parsed.start
DTEND;TZID=Europe/Berlin   = parsed.end
LOCATION       = parsed.location or ""
URL            = parsed.meeting_url or ""
DESCRIPTION    = template, siehe unten
BEGIN:VALARM  TRIGGER:-PT30M  ACTION:DISPLAY  END:VALARM
BEGIN:VALARM  TRIGGER:-P1D    ACTION:DISPLAY  END:VALARM
END:VEVENT
```

### DESCRIPTION-Template

```
Interview-Termin aus Bewerbungstracker.

Position: {position}
Firma: {company}

Meeting-Link: {meeting_url}
Passcode: {passcode}

— erzeugt aus {Email|Notes}, am {today}
```

(Felder, die `None` sind, werden weggelassen.)

## Error-Handling

| Fall | Verhalten |
|---|---|
| Application nicht gefunden / fremder User | 404 |
| Kein Datum im Text gefunden | 400 + `{"error": "..."}` |
| Datum gefunden, aber Link fehlt | 200, .ics ohne LOCATION/URL — User kann manuell ergänzen |
| `icalendar`-Import-Fehler | 500, logged |

## Testing

Pytest-Datei `tests/test_calendar_export.py`:

1. **Parser** (`test_parser_*`):
   - 3 Fixture-Texte (TKMS, Arvato, ESET — aus realen 2026-05 Mails kopiert):
     liefern korrekte `start`, `meeting_url`, `passcode`.
   - Negativ: Leerer Text → `ParsedInterview` mit `start=None`.
   - Verbal-Datum: `Mittwoch, den 27.05.2026 um 13:00` → start korrekt.

2. **Endpoint** (`test_endpoint_*`):
   - Bewerbung mit Email + Termin → `200 text/calendar`, `Content-Disposition` enthält Firma.
   - Bewerbung ohne Termin → `400`.
   - Fremder User → `404`.

3. **.ics-Validität:** `icalendar.Calendar.from_ical(response.data)` ohne Exception,
   1 VEVENT, 2 VALARMs.

## Deployment-Hinweise

- `requirements.txt`: `icalendar>=5.0` hinzufügen
- Kein Schema-Migrations-Schritt nötig
- Frontend: `service-worker.js` `CACHE_NAME` bumpen (Memory-Hinweis
  `feedback_frontend_release_sw_bump`)
- Deploy via `bewerbungen-deploy.sh` (pull + pip + restart)

## Risiken

- **Parser-Brüchigkeit bei freier Schreibweise:** akzeptabel für MVP,
  da bei Fehlschlag der User klare 400-Meldung bekommt und Notes editieren kann.
  Wenn das in der Praxis oft auftritt, später Preview-Modal mit manuellen Feldern.
- **Empty `emails`-Tabelle in Prod:** der Parser fällt dann automatisch auf
  `notes` zurück, was die realistische Quelle ist (siehe DB-Stand 2026-05-21).
