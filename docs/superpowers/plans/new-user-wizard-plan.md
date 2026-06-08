# New User Wizard — Implementation Plan

## 9 Tasks (empfohlen für subagent-driven development)

### Task 1: Backend — DB-Migration + Wizard-API
- Neue Spalten: `users.onboarding_complete` (BOOLEAN), `users.onboarding_data` (TEXT JSON)
- Neue Endpoints:
  - `GET /api/profile/wizard-status` → `{complete: bool, current_step: int, data: {...}}`
  - `PATCH /api/profile/wizard-save` → speichert Wizard-Zwischenstand
  - `PATCH /api/profile/wizard-complete` → setzt `onboarding_complete = true`
- Tests: 3 neue Testfälle

### Task 2: Frontend — WizardController (`frontend/js/wizard.js`)
- Klasse `WizardController` mit:
  - Schritt-Navigation (next/prev/goTo)
  - State-Management (localStorage + API-Sync)
  - Fortschrittsanzeige
  - "Später erinnern"-Logik
  - Event-Dispatching für Schritte

### Task 3: Schritt 1 — Begrüßung
- Willkommenstext + "Los geht's!"-Button
- Minimal: nur HTML + CSS

### Task 4: Schritt 2 — KI-Provider
- 3 große Auswahlkacheln (opencode/Claude/Ollama)
- Claude: API-Key-Eingabefeld
- opencode: empfohlen-Badge
- API: `PATCH /api/providers/user/settings`

### Task 5: Schritt 3 — E-Mail-Anbindung
- 3 Optionen (Gmail/IMAP/Überspringen)
- Gmail: Google Apps Script Code-Block + URL-Eingabe
- IMAP: Formular (Host, Port, User, Pass) + Preset-Buttons
- API: `POST /api/profile/imap` + `POST /api/profile/imap/test`

### Task 6: Schritt 4 — Job-Discovery
- Checkboxen für Job-Kategorien + Freitext
- Absenden → `POST /api/profile/job-discovery/request`
- Hinweis auf Admin-Freigabe

### Task 7: Schritt 5 — CV-Upload (optional)
- Datei-Upload (PDF/DOCX/Text) + Drag&Drop
- API: `PUT /api/profile/cv`
- Zusammenfassung nach Upload anzeigen

### Task 8: Schritt 6 — Zusammenfassung + Abschluss
- Checkliste der erledigten/übersprungenen Schritte
- `PATCH /api/profile/wizard-complete`
- Redirect zum Dashboard

### Task 9: Integration in `index.html` + `auth.js`
- Wizard-Overlay-Container in `index.html`
- Login-Flow: nach `init()` → `checkWizard()`
- CSS-Datei einbinden
- localStorage-Prüfung + API-Abfrage

---

## Geschätzter Aufwand

| Task | Dateien | Aufwand |
|---|---|---|
| 1 Backend | 2-3 | ~45 min |
| 2 WizardController | 1 | ~30 min |
| 3 Begrüßung | 1 | ~10 min |
| 4 KI-Provider | 2 | ~30 min |
| 5 E-Mail | 3 | ~45 min |
| 6 Job-Discovery | 2 | ~20 min |
| 7 CV-Upload | 2 | ~20 min |
| 8 Abschluss | 2 | ~15 min |
| 9 Integration | 3 | ~30 min |
| **Gesamt** | **~18** | **~4 h** |
