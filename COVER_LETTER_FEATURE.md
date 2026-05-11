# 📝 Cover-Letter-Generator – Vollständige Dokumentation

## Überblick

Der Cover-Letter-Generator unterstützt dich beim Schreiben professioneller Bewerbungsschreiben. Das System analysiert deine CV und die Stellenbeschreibung, generiert einen personalisierten Bewerbungsbrief mit Confidence-Scoring und ermöglicht Export als PDF oder DOCX. Die Kernfunktion: intelligente Keyword-Matching zwischen CV und Job-Anforderungen mit Farbcodierung nach Sicherheitswert.

## Hauptfunktionen

- ✅ **Draft-Erstellung**: Job-Titel, Firma, Stellenbeschreibung eingeben → Draft speichern
- 📊 **Analyse**: CV gegen Stellenbeschreibung abgleichen (gematched Skills, Experience, Requirements)
- ✍️ **Generierung**: KI-gestützter Text basierend auf Analyse + Konfiguration (Tone, Length, Focus)
- 🎨 **Confidence-Farbcodierung**: Jeder Absatz mit Sicherheitswert (grün=hoch, gelb=mittel, rot=niedrig)
- ⚙️ **Konfigurierbar**: Tone (professional|casual|technical), Length (short|medium|long), Focus (technical|leadership|projects|balanced)
- 📥 **Export**: PDF oder DOCX-Download
- 🔒 **User-Isolation**: Jeder User sieht nur eigene Cover Letters
- 📱 **Status-Tracking**: draft → generated → finalized → sent

## Workflow-Pfade

### Pfad 1: Quick-Generierung (aus Job-Vorschlag)
1. Job-Discovery oder Jobsuche: Position gefunden
2. Button **"Cover Letter generieren"** klicken
3. Dialog öffnet:
   - Job-Titel (vorausgefüllt)
   - Firma (vorausgefüllt)
   - Stellenbeschreibung (vorausgefüllt oder paste)
   - CV-Text (select/paste)
   - Tone, Length, Focus wählen
4. **"Generieren"** → Draft + Analysis + Content wird erstellt
5. Live-Preview mit Confidence-Farbcodierung
6. **"Speichern"** → Status=generated

### Pfad 2: Detailanalyse & Manuelle Bearbeitung
1. Bestehenden Draft öffnen oder neuen erstellen
2. **"Analysiere"** klicken:
   - matched_skills: Array von {skill, confidence}
   - matched_experience: Array von {years, title, relevance}
   - interpreted_requirements: Array von Requirements aus Job-Beschreibung
3. Content wird mit HTML-Attributen `data-confidence` versehen (per Absatz)
4. Benutzer kann Content inline editieren
5. **"Status aktualisieren"** → finalized
6. **"Exportiere"** als PDF/DOCX oder **"Markiere als versendet"**

### Pfad 3: Aus existierender Bewerbung
1. Application (Firma + Position) öffnen
2. Tab **"Cover Letter"** klicken
3. **"Neuer Draft"** oder bestehenden öffnen
4. Application-ID wird automatisch linked (application_id)
5. Workflow wie Pfad 1/2

## Confidence-Scoring & Farbcodierung

Jeder generierte Absatz erhält einen **confidence_score** (0–100) basierend auf:
- Wort-Overlap zwischen CV und Job-Anforderungen
- Keyword-Relevanz (aus matched_skills + interpreted_requirements)
- Kontext-Passung (z.B. Leadership-Experience für Leadership-Position)

### Farbschema (Frontend)
| Score | Farbe | Bedeutung |
|-------|-------|-----------|
| 80–100 | 🟢 Grün | Hoch confident – direkt gematcht |
| 50–79 | 🟡 Gelb | Mittel – sinnvoll interpretiert |
| 0–49 | 🔴 Rot | Niedrig – allgemein/unsicher |

**HTML-Struktur** (im Content gespeichert):
```html
<p data-confidence="85" class="confidence-high">
  Mit meinen langjährigen Erfahrungen in Python...
</p>
```

Frontend rendert Hintergrundfarbe oder Border entsprechend.

## Datenmodell

### CoverLetter (SQL-Tabelle)
```python
class CoverLetter(db.Model):
    id: str (UUID)                   # Primary Key
    user_id: str (FK)                # User dieser Cover Letter
    application_id: str (FK, optional)  # Verknüpfung zu Application
    
    job_title: str                   # z.B. "Senior Engineer"
    company_name: str                # z.B. "Apple"
    job_description: str             # Vollständige Stellenbeschreibung
    cv_used: str (optional)          # Welcher CV-Snapshot verwendet
    
    # Generierter Content
    content: str (HTML)              # Mit data-confidence pro Absatz
    analysis_json: str (JSON)        # {matched_skills, matched_experience, interpreted_requirements}
    
    # Konfiguration
    tone: str enum                   # professional|casual|technical (default: professional)
    length: str enum                 # short|medium|long (default: medium)
    focus: str enum                  # technical|leadership|projects|balanced (default: balanced)
    
    # Lifecycle
    status: str enum                 # draft|generated|finalized|sent (default: draft)
    exported_at: datetime (optional) # Wann zuletzt als PDF/DOCX exportiert
    created_at: datetime             # Erstellt
    updated_at: datetime             # Zuletzt geändert
    
    # Relationships
    application: Application (optional)  # Backreference
```

### Analysis-JSON-Schema
```json
{
  "matched_skills": [
    {"skill": "Python", "confidence": 0.95, "source": "job_desc"},
    {"skill": "REST APIs", "confidence": 0.87, "source": "job_desc"}
  ],
  "matched_experience": [
    {"years": 5, "title": "Backend Engineer", "relevance": 0.92},
    {"years": 2, "title": "DevOps", "relevance": 0.65}
  ],
  "interpreted_requirements": [
    {"requirement": "Cloud Infrastructure (AWS/GCP)", "found_in_cv": true},
    {"requirement": "Team Leadership", "found_in_cv": false}
  ]
}
```

## API-Endpoints

Alle unter `/api/cover-letters`:

### 1. Cover Letter erstellen (Draft)
```
POST /create
Content-Type: application/json
Authorization: Bearer <token>

{
  "job_title": "Senior Backend Engineer",
  "company_name": "Apple",
  "job_description": "We are looking for...",
  "application_id": "uuid-optional",
  "cv_used": "resume.pdf (optional)",
  "tone": "professional (optional, default)",
  "length": "medium (optional, default)",
  "focus": "balanced (optional, default)"
}

Response (201):
{
  "id": "uuid",
  "user_id": "uuid",
  "application_id": null,
  "job_title": "Senior Backend Engineer",
  "company_name": "Apple",
  "tone": "professional",
  "length": "medium",
  "focus": "balanced",
  "status": "draft",
  "cv_used": null,
  "exported_at": null,
  "created_at": "2026-05-11T10:00:00",
  "updated_at": "2026-05-11T10:00:00"
}
```

### 2. Cover Letter analysieren & generieren
```
POST /<cover_letter_id>/generate
Content-Type: application/json
Authorization: Bearer <token>

{
  "cv_text": "Hier ist mein kompletter Lebenslauf...",
  "applicant_name": "Max Mustermann (optional)"
}

Response (200):
{
  "id": "uuid",
  "status": "generated",
  "content": "<p data-confidence=\"92\">...</p>",
  "analysis": {
    "matched_skills": [...],
    "matched_experience": [...],
    "interpreted_requirements": [...]
  },
  "job_description": "...",
  "created_at": "...",
  "updated_at": "..."
}

Error (400): Stellenbeschreibung < 50 Zeichen
Error (400): cv_text fehlt
```

### 3. Cover Letter Details abrufen
```
GET /<cover_letter_id>
Authorization: Bearer <token>

Response (200):
{
  "id": "uuid",
  "job_title": "...",
  "company_name": "...",
  "tone": "professional",
  "length": "medium",
  "focus": "balanced",
  "status": "generated",
  "content": "...",
  "analysis": {...},
  "job_description": "...",
  "created_at": "...",
  "updated_at": "...",
  "exported_at": null
}

Error (404): Nicht gefunden oder nicht Eigentum des Users
```

### 4. Alle Cover Letters des Users auflisten
```
GET /
Authorization: Bearer <token>

Response (200):
[
  {
    "id": "uuid",
    "job_title": "...",
    "company_name": "...",
    "status": "generated",
    "created_at": "...",
    "updated_at": "...",
    "exported_at": null
  },
  ...
]
```

### 5. Cover Letter aktualisieren
```
PATCH /<cover_letter_id>
Content-Type: application/json
Authorization: Bearer <token>

{
  "content": "<p data-confidence=\"95\">Neuer Text...</p> (optional)",
  "status": "finalized (optional)",
  "tone": "professional (optional)",
  "length": "medium (optional)",
  "focus": "technical (optional)"
}

Response (200):
{
  "id": "uuid",
  "status": "finalized",
  "content": "...",
  "updated_at": "2026-05-11T10:15:00",
  ...
}

Error (400): Ungültige Status/Tone/Length/Focus-Werte
```

### 6. Als PDF oder DOCX exportieren
```
POST /<cover_letter_id>/export
Content-Type: application/json
Authorization: Bearer <token>

{
  "format": "pdf" | "docx"
}

Response (200):
Binary file download (application/pdf oder application/vnd.openxmlformats-officedocument.wordprocessingml.document)

+ DB-Update: exported_at = now()

Error (404): Cover Letter nicht gefunden
Error (400): format nicht unterstützt
```

### 7. Cover Letter löschen
```
DELETE /<cover_letter_id>
Authorization: Bearer <token>

Response (204): No Content

Error (404): Nicht gefunden oder nicht Eigentum des Users
```

## Export-Formate

### PDF-Export
- **Header**: Firma + Job-Titel
- **Body**: Content (HTML mit Confidence-Highlighting oder als Text)
- **Footer**: Exportiert am [Datum], User E-Mail (optional)
- **Styling**: Professional – passend zur CV-Vorlage
- **Confidence-Farben**: Optional per Toggle im Export-Dialog

### DOCX-Export
- **Struktur**: Standard Microsoft Word
- **Absätze**: Mit data-confidence beibehalten (als HTML Comments oder Styles)
- **Editierbar**: User kann nach Export weiterbearbeiten
- **Kompatibilität**: Office 2010+ und Google Docs

## Konfiguration

### Tone (Ton des Schreibens)
| Value | Anwendung | Beispiel |
|-------|-----------|----------|
| `professional` | Klassisches, formales Bewerbungsschreiben | Standard für Corporate-Jobs |
| `casual` | Lockerer, persönlicherer Ton | Tech-Startups, kreative Rollen |
| `technical` | Fokus auf technische Skills & Tools | Engineering, Dev-Positionen |

### Length (Umfang)
| Value | Länge | Anwendung |
|-------|-------|----------|
| `short` | ~100–150 Wörter | Cover Letter kurz & knackig |
| `medium` | ~200–300 Wörter | Standard (recommended) |
| `long` | ~400–500 Wörter | Detaillierte Begründung |

### Focus (Schwerpunkt der Argumentation)
| Value | Fokus | Anwendung |
|-------|-------|----------|
| `technical` | Technische Skills & Tools | Backend/Frontend/DevOps |
| `leadership` | Management & Führung | Team Lead, Manager |
| `projects` | Projekte & Erfolge | Portfolios, Achievements |
| `balanced` | Ausgewogen | Standard |

**Szenario**: Senior Backend Engineer → Focus=technical + Tone=professional + Length=medium

## Sicherheit & Datenschutz

### User-Isolation
- Jede Cover Letter ist an `user_id` gebunden
- API-Endpoints validieren `user_id` in Query (token_required decorator)
- Keine Cross-User Access möglich

### CV-Daten
- **Input**: cv_text wird analysiert, nicht permanent gespeichert (nur bei Bedarf)
- **Speicherung**: Nur job_title, company_name, job_description gespeichert → reusable
- **Privacy**: User kontrolliert, welche CV-Version verwendet wird (cv_used)

### Keine Erfindung von Daten
- **Analyse** basiert ausschließlich auf CV + Job-Beschreibung
- Keine automatischen Annahmen über Fähigkeiten, die nicht im CV erwähnt sind
- **Confidence-Score** geben transparent an, wenn Skills nicht gematcht sind

### Verschlüsslung
- HTTPS-only (auf Produktions-VPS)
- CV-Text wird nicht in Logs gesammelt
- Exported Files (PDF/DOCX) enthalten keine User-Metadaten außer E-Mail (optional)

## Troubleshooting

### "Cover Letter nicht gefunden" (404)
**Problem**: Draft wurde gelöscht oder ID ist falsch.
**Lösung**:
1. Gehe zu **"Meine Cover Letters"** → Liste öffnen
2. Überprüfe, dass du den richtigen Draft auswählst
3. Wende dich an Support, wenn Draft verloren geht

### "Stellenbeschreibung zu kurz" (400 Error)
**Problem**: Job-Beschreibung < 50 Zeichen.
**Lösung**:
1. Kopiere die komplette Stellenbeschreibung von der Job-Seite
2. Mindestens 50 Zeichen erforderlich (z.B. 2–3 Sätze)
3. Füge Details ein: Anforderungen, Aufgaben, Benefits

### "cv_text ist erforderlich" (400 Error)
**Problem**: CV-Text wurde nicht übergeben beim Generieren.
**Lösung**:
1. Stelle sicher, dass du im Dialog **"CV-Text eingeben/paste"** hast
2. Paste deinen kompletten Lebenslauf (mindestens 100 Wörter)
3. Klicke **"Generieren"** erneut

### Content wird nicht korrekt coloriert
**Problem**: Confidence-Scores werden nicht als Farben angezeigt.
**Lösung**:
1. Überprüfe Browser-DevTools (Console) auf Fehler
2. Aktualisiere den Browser (Strg+Shift+R / Cmd+Shift+R)
3. Stelle sicher, dass CSS-Datei geladen ist

### Export schlägt fehl
**Problem**: PDF/DOCX-Download funktioniert nicht.
**Lösung**:
1. Überprüfe Browser-Download-Ordner (Blockierung?)
2. Stelle sicher, dass Content > 0 Zeichen (nicht leerer Draft)
3. Probiere anderen Browser oder Incognito-Modus

### "Ungültige Status/Tone/Length/Focus-Werte" (400 Error)
**Problem**: Ungültige Enum-Wert gewählt.
**Gültige Werte**:
- status: `draft`, `generated`, `finalized`, `sent`
- tone: `professional`, `casual`, `technical`
- length: `short`, `medium`, `long`
- focus: `technical`, `leadership`, `projects`, `balanced`

## Version & Kompatibilität

- **Feature eingeführt**: v4.5 (2026-05-11)
- **Backend**: Flask + SQLAlchemy + Python 3.10+
- **Frontend**: Vanilla JS + HTML5
- **Datenbank**: SQLite3 (lokal) / PostgreSQL (VPS)
- **Export**: ReportLab (PDF) + python-docx (DOCX)
- **KI-Integration**: Claude API (Analyse + Generierung)
- **Browser-Mindestanforderung**: Chrome 90+, Firefox 88+, Safari 14+

## Zukünftige Erweiterungen

- [ ] Template-Vorlagen (Branche-spezifisch)
- [ ] A/B-Testing verschiedener Tone/Focus-Kombinationen
- [ ] Batch-Generierung (mehrere Jobs gleichzeitig)
- [ ] Unternehmens-Datenbank (Firmenstil + Anredestil)
- [ ] LinkedIn-Integration (Profile → Auto-Vorschläge)
- [ ] Mehrsprachige Generierung (EN, DE, FR)
- [ ] Collaboration-Mode (Reviewer-Feedback)
