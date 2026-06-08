# New User Wizard — Design Spec

**Projekt:** Bewerbungstracker
**Status:** Draft / Planung
**Datum:** 2026-06-08
**Autor:** opencode (DeepSeek V4 Flash)

---

## 1. Problem

Der Bewerbungstracker hat keine geführte Ersteinrichtung. Neue Nutzer müssen:

- IMAP-Zugang konfigurieren (Host, User, Passwort, SSL)
- KI-Provider wählen (Claude/Ollama/opencode)
- Job-Discovery aktivieren (benötigt Admin-Freigabe)
- CV/Profil-Daten eingeben
- E-Mail-Import einrichten

Technisch unerfahrene Nutzer sind damit überfordert. Der Wizard führt schrittweise durch alle notwendigen Konfigurationen.

---

## 2. Ziel

Ein **modalbasierter Setup-Wizard**, der beim ersten Login startet und den Nutzer in 5-7 Schritten durch die Einrichtung führt.

### Nicht-Ziele (v1)

- Kein "AI-Coach" oder Chatbot
- Kein automatisches Erkennen von IMAP-Einstellungen
- Kein Tutorial-Video oder interaktive Tour
- Keine Mehrsprachigkeit (nur Deutsch)

---

## 3. UI-Architektur

### 3.1 Auslöser

Der Wizard startet automatisch, wenn **alle drei Bedingungen** erfüllt sind:

1. Nutzer ist eingeloggt (`is_active === true`)
2. Nutzer hat den Wizard noch nicht abgeschlossen (`localStorage.getItem('wizard_done') !== 'true'`)
3. Nutzer hat noch keine aktive Job-Quelle oder IMAP-Konfiguration (oder `?wizard=1` in URL)

### 3.2 UI-Komponente

Ein **modales Overlay** (Fullscreen auf Mobil, zentriert auf Desktop) mit:

- Fortschrittsanzeige (Schritt X von Y)
- Zurück/Weiter-Buttons
- Schritt-überspringen-Button (klein, dezent)
- "Später erinnern"-Link (schließt Wizard, startet beim nächsten Login neu)
- Schließen nur möglich, wenn alle Pflichtschritte erledigt sind

### 3.3 View-Steuerung

- Ein zentraler `WizardController` in JS (`frontend/js/wizard.js`)
- Zustand im Wizard-State-Objekt: `{ step: 0, data: {...}, done: false }`
- Bei jedem Schritt kann der Nutzer vor/zurück navigieren
- Daten werden nach jedem Schritt im Wizard-State gespeichert, erst beim letzten Schritt gebündelt gespeichert

---

## 4. Wizard-Schritte

### Schritt 1: Begrüßung ("Willkommen!")

**Inhalt:**
- Kurzer Text: "Willkommen beim Bewerbungstracker! In den nächsten Minuten führen wir dich durch die Einrichtung."
- Hinweis: "Du kannst jeden Schritt überspringen und später in den Einstellungen nachholen."
- Voraussetzung: Nichts

**Button:** "Los geht's!"

---

### Schritt 2: KI-Provider wählen

**Inhalt:**
- "Wähle deinen KI-Assistenten für die automatische Bewertung von Stellenanzeigen."
- 3 Optionen als große Kacheln mit Icons (nicht als Dropdown):
  - **opencode.ai** (⭐ empfohlen) — "Kostenlose Modelle, keine Anmeldung nötig"
  - **Claude (Anthropic)** — "Beste Qualität, benötigt API-Key"
  - **Ollama (Lokal)** — "Läuft auf deinem Rechner, keine Internetverbindung nötig"
- "Du kannst den Provider jederzeit in den Einstellungen wechseln."
- Wenn "Claude" gewählt: Eingabefeld für API-Key + Link zu console.anthropic.com
- Wenn "Ollama" gewählt: kurzer Text "Stelle sicher, dass Ollama auf deinem Rechner läuft."
- Wenn "opencode" gewählt: Keine weiteren Eingaben nötig

**API-Nutzung:** `PATCH /api/providers/user/settings` (existiert bereits)

**Voraussetzung:** Keine (Default-Werte sind akzeptabel)

---

### Schritt 3: E-Mail-Anbindung (IMAP)

**Inhalt:** (Die komplexeste Konfiguration, daher größter Schritt)

- Drei Optionen als große Kacheln:
  - **Gmail / Google Mail** — "Verwende ein Google Apps Script für den E-Mail-Import"
  - **Eigener E-Mail-Server (IMAP)** — "Für GMX, Web.de, Posteo, etc."
  - **Überspringen** — "Richte ich später ein"

**Bei Gmail:**
- "Kopiere dieses Google Apps Script in dein Google Drive"
- Code-Block zum Kopieren (Textarea, readonly, daneben Copy-Button)
- "Führe das Script einmal aus und erlaube die Berechtigungen."
- "Füge die Script-URL hier ein:"
- URL-Eingabefeld + Button "Testen"

**Bei IMAP:**
- Formular: Host, Port (993), Benutzername, Passwort, SSL (Toggle, default an)
- Button "Verbindung testen"
- Bekannte Provider als Preset-Buttons: "GMX", "Web.de", "Posteo", "IONOS"

**API-Nutzung:** `POST /api/profile/imap` + `POST /api/profile/imap/test` (existiert)

**Voraussetzung:** Keine (kann übersprungen werden)

---

### Schritt 4: Job-Discovery aktivieren

**Inhalt:**
- Erklärung: "Der Bewerbungstracker kann automatisch passende Stellenanzeigen für dich finden."
- "Wähle aus, wonach wir suchen sollen."
- Mehrfachauswahl (Checkboxen) für Job-Kategorien: IT/Security, Verwaltung, Vertrieb, etc.
- Oder Freitext für Stichworte
- "Deine Anfrage wird an den Administrator weitergeleitet und freigeschaltet."
- Nach Absenden: "✅ Anfrage wurde gesendet. Du bekommst Bescheid, sobald die Job-Suche aktiv ist."

**API-Nutzung:** `POST /api/profile/job-discovery/request` (existiert)

**Voraussetzung:** admin muss freischalten (bestehender Flow)

---

### Schritt 5: CV / Profil (optional)

**Inhalt:**
- "Lade deinen Lebenslauf hoch, damit die KI deine Qualifikationen besser bewerten kann."
- Upload-Button für PDF/DOCX/Text
- Oder "Später hochladen" (überspringen)
- Nach Upload: kurze Zusammenfassung der extrahierten Daten anzeigen

**API-Nutzung:** `PUT /api/profile/cv` (existiert)

**Voraussetzung:** Keine (optional)

---

### Schritt 6: Zusammenfassung & Abschluss

**Inhalt:**
- Checkliste aller konfigurierten Schritte:
  - ✅ KI-Provider: opencode.ai
  - ✅ E-Mail: GMX (max@example.com)
  - ⏳ Job-Discovery: wartet auf Freigabe
  - ⏳ CV: übersprungen
- "Du kannst jederzeit in die Einstellungen gehen, um etwas zu ändern."
- Button "Zum Dashboard"

**Aktion:**
- Wizard-State in `localStorage.setItem('wizard_done', 'true')` speichern
- Optional: `PATCH /api/profile/settings` um Wizard-Abschluss zu markieren

---

## 5. Backend-Änderungen

| Änderung | Beschreibung |
|---|---|
| `GET /api/profile/wizard-status` | Gibt zurück, ob Wizard bereits abgeschlossen + welche Schritte erledigt sind |
| `PATCH /api/profile/wizard-complete` | Markiert Wizard als abgeschlossen |
| `users.onboarding_complete` | Neue DB-Spalte (BOOLEAN DEFAULT 0) |
| `users.onboarding_data` | Neue DB-Spalte (TEXT, JSON — speichert Wizard-State) |

Optional: `POST /api/profile/wizard-validate-step` zur serverseitigen Validierung eines Einzelschritts.

---

## 6. Frontend-Änderungen

| Datei | Änderung |
|---|---|
| `frontend/js/wizard.js` | **Neu** — Wizard-Controller (Schritte, State, Navigation) |
| `frontend/js/wizard.css` | **Neu** — Wizard-spezifische Styles |
| `frontend/components/wizard-step-N.html` | **Neu** — HTML-Templates pro Schritt (oder in wizard.js) |
| `index.html` | Wizard-Overlay-Container + `init()`-Integration |
| `frontend/auth.js` | Nach Login prüfen, ob Wizard gestartet werden muss |

---

## 7. Sicherheit

- Keine sensiblen Daten im localStorage (API-Keys, Passwörter) — nur Session-Tokens und Wizard-State
- API-Schritte nutzen bestehende Auth-Header (JWT)
- CV-Upload: serverseitige Validierung von Dateityp und -größe
- IMAP-Test: Verbindung nur zum angegebenen Server, keine Speicherung des Ergebnisses

---

## 8. UX-Design-Prinzipien

1. **Jederzeit unterbrechbar** — Schließen → Fortschritt bleibt → später fortsetzen
2. **Keine technischen Fachbegriffe ohne Erklärung** — "IMAP" erklären ("Posteingang via Internet")
3. **Große Touch-Ziele** — Buttons mindestens 48px Höhe
4. **Sichtbares Feedback** — Lade-Spinner bei API-Aufrufen, Hakerl bei Erfolg
5. **Mobile-first** — Wizard muss auf Smartphone bedienbar sein
6. **Fehlertoleranz** — Fehler in einem Schritt blockieren nicht den gesamten Wizard

---

## 9. Implementierungs-Plan

Siehe separates Plan-Dokument: `docs/superpowers/plans/new-user-wizard-plan.md`
