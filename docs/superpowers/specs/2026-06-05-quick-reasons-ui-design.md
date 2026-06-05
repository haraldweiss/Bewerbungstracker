# Quick-Reasons-UI — Design

**Status:** approved 2026-06-05
**Source:** Auto-Reject-Analyse 2026-06-05 — 1.786/1.891 JobMatches dismissed, davon 812 (45 %) mit leerem `feedback_text`. Verlorene Lerninfo + 138 manuell-getippte User-Texte zeigen wiederkehrende Muster, die mit Folgeaktionen automatisierbar wären.

## Ziel

Reduktion der stillen Dismisses durch **1-Klick-Quick-Actions, die echte DB-Folgewirkung haben**, statt nur Lernkontext zu sammeln. Hebel pro Action (geschätzt aus 138 User-Texten / 180d):

| Action | Hebel | Folgewirkung |
|---|---|---|
| Firma hat schon abgelehnt | ~12 Fälle | Future-Block via `company_already_rejected` |
| Schon dort beworben | ~15 Fälle | Future-Skip via `include_applied`-Filter |
| Stelle nicht mehr verfügbar | ~10 Fälle | Marker für späteren Body-Phrasen-Scan |
| Falscher Job-Typ (Werkstudent/Freelancer/AÜ) | ~15 Fälle | User-Setting + Prefilter-Block |

Out-of-Scope: Backfill bestehender Dismisses, Bulk-Mode-Integration, Body-Phrasen-Scan (eigenes Backlog-Item), Re-Categorize-Endpoint.

## UI — Modal-Erweiterung

Bestehendes Modal `#dismissFeedbackModal` in `index.html` bekommt oben einen neuen Block:

```
┌────────────────────────────┬────────────────────────────┐
│ 🚫 Firma hat schon         │ 🔁 Schon dort beworben     │
│    abgelehnt               │                            │
│ Future-Block für Firma     │ Wird als beworben markiert │
├────────────────────────────┼────────────────────────────┤
│ 📋 Stelle nicht mehr       │ 🏷️ Falscher Job-Typ        │
│    verfügbar               │    (öffnet Subwahl)        │
│ Markiert für Phrasen-      │ Aktiviert Filter im Profil │
│   Lernen                   │                            │
└────────────────────────────┴────────────────────────────┘

──────  Optional: AI-Match-Feedback (klein, einklappbar)  ──────
   [bestehende 8 Checkboxes + Freitext]

[Abbrechen]  [Skip ohne Feedback]
```

- 1-Klick auf eine Action: dismiss + Folgeaktion + Modal-Close + Toast mit Bestätigung.
- „Falscher Job-Typ" klappt eine Sub-Auswahl aus (3 Radio-Buttons: Werkstudent / Freelancer/Freiberuflich / Arbeitnehmerüberlassung (AÜ)). Erst nach Wahl + Bestätigung wird dismissed.
- Bestehende Lern-Reasons (`wrong_location`, `salary_too_low`, …) werden in eine einklappbare Sektion verschoben. Default: zugeklappt. Wer Lerninfo geben will, öffnet sie bewusst.
- Skip-Button bleibt für „echtes" stilles Dismiss.
- Mobile (max-width: 600px): 2×2-Grid bricht auf 1-Spalte. CSS-Media-Query.

## Backend — PATCH-Erweiterung

`PATCH /api/jobs/matches/<id>` ([api/jobs_user.py:542](api/jobs_user.py:542)) bekommt zwei neue optionale Felder:

- `quick_action: str` ∈ `{'company_rejected', 'already_applied', 'job_unavailable', 'wrong_job_type'}`
- `job_type: str` (nur bei `wrong_job_type` erforderlich) ∈ `{'werkstudent', 'freelance', 'temp_agency'}`

Wenn `quick_action` gesetzt ist:
- `status='dismissed'` ist implizit (auch wenn der Request `status` nicht setzt).
- `feedback_text` wird automatisch auf einen system-Wert gesetzt: `'quick_action_company_rejected'`, `'quick_action_already_applied'`, `'job_no_longer_available'`, `'wrong_job_type_blocked'`. User-übergebener `feedback_text` wird ignoriert (Konsistenz).
- `feedback_reasons` darf zusätzlich gesetzt sein und wird gespeichert (AI-Lernpfad bleibt).
- Folgeaktionen werden in derselben Transaktion ausgeführt; bei Fehler in der Folgeaktion → 500 + rollback, kein partial-update.

### Folgeaktionen serverseitig

#### `company_rejected`
```python
# Idempotent: SELECT auf (user, lower(company), lower(position), deleted=False)
existing = Application.query.filter(
    Application.user_id == user.id,
    Application.deleted == False,
    db.func.lower(Application.company) == raw.company.lower().strip(),
    db.func.lower(Application.position) == raw.title.lower().strip(),
).first()
if existing:
    if existing.status not in ('absage', 'ghosting', 'rejected'):
        existing.status = 'absage'
else:
    db.session.add(Application(
        user_id=user.id,
        company=raw.company,
        position=raw.title,
        status='absage',
        applied_date=None,  # NULL: User weiß nicht/will nicht angeben wann
        notes=f'Quick-Action aus JobMatch #{m.id} ({datetime.utcnow().date().isoformat()})',
    ))
```

#### `already_applied`
Identische Idempotenz-Prüfung. Bei Insert: `status='beworben'`, `applied_date=date.today()`, gleiche `notes`-Konvention. Bei existing: nichts tun (User hat den Lauf eh schon registriert).

#### `job_unavailable`
Nur `feedback_text='job_no_longer_available'`. Keine Application, kein RawJob-Update (privacy: andere User könnten dieselbe URL durchaus noch verfolgen wollen). Reiner Lernmarker.

#### `wrong_job_type`
Anforderung: `job_type` muss gesetzt sein, sonst 400. Logik:
```python
blacklist = json.loads(user.job_type_blacklist or '[]')
if job_type not in blacklist:
    blacklist.append(job_type)
    user.job_type_blacklist = json.dumps(blacklist)
```

### Fehlerfälle
- `quick_action` Wert nicht im Enum → 400 „unbekannte quick_action".
- `quick_action ∈ {company_rejected, already_applied}` mit `not raw.company or not raw.title` → 400 „Firma/Titel im RawJob fehlt, Quick-Action nicht möglich".
- `quick_action='wrong_job_type'` ohne `job_type` → 400 „job_type fehlt".

## Neue User-Settings + Prefilter

### Migration
Alembic-Migration: `User.job_type_blacklist TEXT` mit Default `'[]'` (JSON-Array-String).

```python
def upgrade():
    op.add_column('users', sa.Column(
        'job_type_blacklist', sa.Text(), nullable=False, server_default="'[]'"
    ))

def downgrade():
    op.drop_column('users', 'job_type_blacklist')
```

### Detection
Neue reine Funktion in [services/job_matching/prefilter.py](services/job_matching/prefilter.py):

```python
_JOB_TYPE_KEYWORDS = {
    'werkstudent': ('werkstudent', 'werkstudentin', 'werkstudierende'),
    'freelance': ('freelancer', 'freelance', 'freiberuflich', 'freiberufler',
                  'selbstständig', 'auf rechnung'),
    'temp_agency': ('arbeitnehmerüberlassung', 'aü', 'leiharbeit', 'zeitarbeit'),
}

def detect_job_type(title: str | None) -> str | None:
    """Liefert ersten Hit ∈ {'werkstudent','freelance','temp_agency'} oder None.

    Konservativ: case-insensitive Word-Boundary-Match (re.search r'\\b{kw}\\b').
    Reihenfolge: werkstudent → freelance → temp_agency (erste Wahl gewinnt).

    Sonderfall AÜ: nur als alleinstehendes Wort matchen, nicht als Substring.
    Konkretes Pattern: r'(?i)\\bAÜ\\b'. Falsch wären "Bautätigkeit" o.Ä. —
    der Word-Boundary in re mit Unicode-Flag fängt das.
    """
```

### Prefilter-Integration
In `cron_prefilter.py`, vor dem Score-Check:
```python
blacklist = json.loads(user_obj.job_type_blacklist or '[]') if user_obj else []
if blacklist:
    detected = detect_job_type(raw.title)
    if detected and detected in blacklist:
        match.status = 'dismissed'
        if not user_has_judgment:
            match.feedback_text = 'wrong_job_type_blocked'
        dismissed += 1
        # weiter zu nächstem Match
        continue
```
Reihenfolge: nach Rejected-Company-Check (billigster Check zuerst), vor Duplicate-Check.

### Settings-UI
Neue Sektion im Profil-Tab in `index.html`:
```
Job-Typen ausblenden
  ☐ Werkstudenten-Stellen
  ☐ Freelancer / Freiberuflich
  ☐ Arbeitnehmerüberlassung (AÜ)
```
GET/PATCH `/api/profile` erweitert um `job_type_blacklist`.

## Edge-Cases

| Fall | Verhalten |
|---|---|
| Match bereits dismissed, User klickt erneut Quick-Action | Aktuell nicht erreichbar (Modal wird nur aus 🗑️-Button aufgerufen, der nur auf nicht-dismissed Karten ist). Falls doch erreicht: PATCH überschreibt feedback_text, Folgeaktion läuft (idempotent). |
| Bulk-Dismiss (5538) | Quick-Actions NICHT im Bulk-Mode. Bulk macht weiterhin Standard-Dismiss ohne Modal. |
| `wrong_job_type` mehrfach mit gleichem job_type | Idempotent (set-Logik). |
| `job_type_blacklist` enthält invaliden Wert (manuell DB-editiert) | `detect_job_type` liefert nur valide Werte → kein Match → kein Schaden. |
| Mobile-Layout | 2×2-Grid → 4×1-Stack via `@media (max-width: 600px)`. |

## Tests

### Backend
Datei: `tests/api/test_quick_actions.py` (neu)
- `test_company_rejected_creates_application`
- `test_company_rejected_idempotent_updates_existing_status`
- `test_company_rejected_keeps_existing_absage_status` (kein Downgrade)
- `test_already_applied_creates_application_with_today_date`
- `test_already_applied_idempotent_skips_existing`
- `test_job_unavailable_only_sets_feedback_text`
- `test_wrong_job_type_appends_to_blacklist`
- `test_wrong_job_type_idempotent`
- `test_quick_action_400_when_company_empty`
- `test_quick_action_400_when_unknown_value`
- `test_wrong_job_type_400_when_job_type_missing`

Datei: `tests/services/test_prefilter.py` (erweitern)
- `test_detect_job_type_werkstudent_de`
- `test_detect_job_type_freelance`
- `test_detect_job_type_au_word_boundary`
- `test_detect_job_type_returns_none_for_normal_title`

Datei: `tests/services/tasks/test_handler_cron_prefilter.py` (erweitern oder neu)
- `test_prefilter_dismisses_blacklisted_job_type`
- `test_prefilter_skips_when_blacklist_empty`

### Frontend
- Keine automatischen Tests im Repo (vanilla JS).
- Manuelle Verifikation: 1× je Quick-Action auf Desktop, 1× auf Mobile-Viewport. Checkliste in PR-Beschreibung.

## Migration-Risiken

- Bestehende `JobMatch`-Einträge sind nicht betroffen (Read-Modell).
- Bestehende `Application`-Einträge sind nicht betroffen (nur neue können entstehen).
- Backwards-kompatibel: alte Clients (ohne `quick_action`) funktionieren unverändert (PATCH bleibt für sie identisch).

## Umfang & Commits

Geschätzt ~470 LoC inkl. Tests. Aufteilung in 4-5 Commits:
1. `Add: Alembic migration — User.job_type_blacklist`
2. `Add: detect_job_type() + Prefilter-Integration + Tests`
3. `Add: PATCH /api/jobs/matches quick_action-Feld + Folgeaktionen + Tests`
4. `Add: Quick-Reasons-Buttons im Dismiss-Modal (Frontend)`
5. `Add: Job-Typ-Blacklist-Settings im Profil-Tab (Frontend)`

## Erfolgs-Metrik (post-deploy)

Nach 14 Tagen prüfen:
- Anteil Dismisses mit `feedback_text != ''` steigt von aktuell 55 % auf ≥ 80 %.
- `company_already_rejected`-Treffer im Prefilter steigt ≥ 3× (Baseline: 7 Treffer / 180d).
- Neue System-Feedback-Codes (`quick_action_*`, `wrong_job_type_blocked`) tauchen in der Verteilung auf.

Wenn nach 14 Tagen kein klarer Effekt: Quick-Actions sind zu versteckt → Re-Design Richtung Approach B (Inline-Bar statt Modal).
