# Feedback-aware Matching — Phase A

**Datum:** 2026-05-22
**Status:** Spec für Phase A. Phase B + C dokumentiert als Backlog.

## Motivation

User schreibt regelmäßig Feedback in zwei Quellen:
- **`Application.notes`** — z.B. „Link kaputt", „passt nicht, weil Salary zu niedrig", „Recruiter unfreundlich"
- **`JobMatch.feedback_text` + `feedback_reasons`** — beim Dismiss eines Job-Vorschlags

Aktuell wird **JobMatch-Feedback** schon vom Pre-Filter ausgewertet (`services/job_matching/learner.py::update_centroid_for_feedback`), aber **Application.notes ist komplett isoliert** — geht nirgendwohin.

Ziel Phase A: `Application.notes` wird in den bestehenden Feedback-Cycle eingebunden, ohne Schema-Refactor.

## Phase A — Scope (jetzt)

### Trigger

Beim Status-Wechsel einer `Application` auf einen der „terminalen" Status
`{absage, ghosting, interview, zusage}`:

1. Falls `Application.notes` nicht leer UND ein `JobMatch` per
   `JobMatch.imported_application_id == Application.id` existiert:
   - Spiegele `Application.notes` in `JobMatch.feedback_text`
   - Setze `JobMatch.feedback_reasons` Tag basierend auf Status:
     - `absage` / `ghosting` → `["rejected_after_apply"]`
     - `interview` → `["positive_signal_interview"]`
     - `zusage` → `["positive_signal_offer"]`

2. Falls KEIN `JobMatch` verlinkt ist (manuelle Bewerbung) — überspringe.
   Phase B kümmert sich um diesen Pfad.

### Aufruf

In `api/applications.py:patch_application` (Status-Update-Endpoint) nach dem
DB-Commit aufrufen:

```python
from services.job_matching.feedback_bridge import maybe_bridge_to_feedback
maybe_bridge_to_feedback(app_obj)
```

### Neues Modul

`services/job_matching/feedback_bridge.py`:

```python
def maybe_bridge_to_feedback(application) -> bool:
    """Bridge Application.notes → JobMatch.feedback_text.

    Returns True wenn ein Match aktualisiert wurde.
    """
    terminal_states = {"absage", "ghosting", "interview", "zusage"}
    if application.status not in terminal_states:
        return False
    if not (application.notes or "").strip():
        return False
    from models import JobMatch
    from database import db
    match = JobMatch.query.filter_by(
        imported_application_id=application.id
    ).first()
    if match is None:
        return False
    # Notes anhängen (nicht überschreiben — User kann beim Dismiss schon was hingeschrieben haben)
    existing = (match.feedback_text or "").strip()
    new = application.notes.strip()
    if existing == new or new in existing:
        return False
    match.feedback_text = f"{existing}\n--- aus Bewerbungs-Notiz ---\n{new}".strip()
    # Reasons tag
    tag = {
        "absage": "rejected_after_apply",
        "ghosting": "rejected_after_apply",
        "interview": "positive_signal_interview",
        "zusage": "positive_signal_offer",
    }[application.status]
    import json as _json
    existing_reasons = []
    if match.feedback_reasons:
        try:
            existing_reasons = _json.loads(match.feedback_reasons)
        except (ValueError, TypeError):
            pass
    if tag not in existing_reasons:
        existing_reasons.append(tag)
        match.feedback_reasons = _json.dumps(existing_reasons)
    # Trigger existing learner
    from services.job_matching.learner import update_centroid_for_feedback
    update_centroid_for_feedback(application.user_id, match)
    db.session.commit()
    return True
```

### Tests

`tests/test_feedback_bridge.py`:

1. **absage triggert Bridge** — Application mit notes + status=absage → JobMatch.feedback_text wird gefüllt + Tag `rejected_after_apply` gesetzt
2. **interview triggert Bridge** — gleiche Logik, Tag `positive_signal_interview`
3. **leere notes** → kein Update
4. **terminaler Status ohne notes** → kein Update
5. **non-terminaler Status (`beworben`)** → kein Update
6. **kein verlinkter JobMatch** → kein Update (returnt False)
7. **idempotent**: zweimaliger Aufruf mit gleichen notes → kein doppeltes Anhängen
8. **Reasons-JSON robust gegen malformed** — fallback zu []

### Acceptance

- Bei Status-Wechsel auf einen terminalen Status mit notes:
  → bestehender Pre-Filter-Lerner sieht das negative/positive Signal
  → künftige Job-Vorschläge mit ähnlichem Profil werden auto-dismissed
  (negativ) bzw. höher gescored (positiv)

## Phase B — Backlog: AI-Match Kontext-aware

**Idee:** AI-Match-Endpoint bekommt User's letzte N (≤10) `JobMatch.feedback_text` + `JobMatch.feedback_reasons` als System-Prompt-Kontext. AI sieht „User hat X verworfen weil Y" und scort entsprechend.

**Größe:** ~½ Tag. Kein DB-Schema-Change.

## Phase C — Backlog: Cover-Letter aus erfolgreichen Bewerbungen

**Idee:** Bei Cover-Letter-Generation für eine neue Stelle:
1. Lade alle `Application` mit status ∈ {`interview`, `zusage`}
2. Extrahiere deren Position-Title + Skills + Industries (aus den ursprünglichen RawJob-Beschreibungen)
3. Feed dem CL-Generator als „Diese Skills/Industries hat der User schon erfolgreich beworben"

**Größe:** ~1 Tag (Skill-Extraktion + Prompt-Erweiterung + UI).

## Out of Scope (alle Phasen)

- Neues DB-Schema `user_feedback_log` (Phase A nutzt existing `JobMatch.feedback_text`)
- Multi-Account-User-Sharing (Single-User-System)
- Real-time-Pre-Filter-Update beim Tippen in notes (nur bei Status-Wechsel)
- Frontend-Anzeige der Feedback-Beeinflussung ("dieser Job würde dismissed weil …")
