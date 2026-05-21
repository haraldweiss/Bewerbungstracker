# User-defined Email-Plattformen

**Datum:** 2026-05-21
**Status:** Spec genehmigt — bereit für Implementation-Plan

## Motivation

Heute ist `PROFILES`-Dict in `services/job_sources/email_jobs.py` hardcoded
mit 3 Plattformen (Indeed/LinkedIn/XING). Jede neue Plattform
(Stepstone, get-in-IT, Monster, …) erfordert Code-Änderung + Deploy.

Ziel: Admin kann im UI neue Email-Plattformen anlegen, ohne Code-Push.
AI-Pattern-Learning (Train-Button) übernimmt danach die Layout-Extraktion.

## Nicht-Ziele (YAGNI)

- Pro-User-Plattformen — Plattformen sind global (konsistent mit
  bestehendem Modell: `PROFILES` global, `LearnedEmailPattern` global).
- Full Migration der 3 hardcoded Plattformen in DB — die bleiben in Code
  (Hybrid). Migration ist out-of-scope, weil deren Pattern fein
  kalibriert sind und Risiko zu hoch.
- Editor für `subject_patterns` / `body_*_re` im UI — AI-Pattern-Learner
  ersetzt das. User kümmern sich nicht um Regex.
- Versionierung von Plattform-Edits, Import/Export, Sharing zwischen
  Instanzen, Plattform-Sandbox-Tests vor Save.

## Architektur

### Datenmodell

Neue DB-Tabelle `platform_profiles`:

```sql
CREATE TABLE platform_profiles (
    id INTEGER PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,            -- z.B. "stepstone"
    display_name VARCHAR(120) NOT NULL,           -- z.B. "Stepstone"
    domain VARCHAR(120) NOT NULL,                 -- z.B. "stepstone.de"
    subject_must_contain TEXT NOT NULL,           -- JSON-Array von Strings
    ai_schema_hint TEXT,                          -- optional, freier Text
    digest_threshold INTEGER NOT NULL DEFAULT 3,
    -- Advanced overrides — wenn NULL, wird aus `domain` auto-generiert
    url_pattern_override TEXT,
    from_whitelist_override TEXT,
    -- Audit
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by_user_id VARCHAR(36) NOT NULL REFERENCES users(id)
);
```

Slug-Constraint: `^[a-z0-9_-]{2,64}$`, und `slug NOT IN PROFILES.keys()`
(verhindert Kollision mit hardcoded Plattformen).

### Profile-Resolution

Adapter ruft eine neue Funktion `get_profile(slug: str) -> PlatformProfile`
in `services/job_sources/email_jobs.py`:

```python
def get_profile(slug: str) -> PlatformProfile:
    """Resolve Plattform-Slug zu PlatformProfile.

    1. Hardcoded PROFILES-Dict (legacy, getestet).
    2. DB-Tabelle platform_profiles (user-defined).
    3. KeyError wenn nichts gefunden.
    """
    if slug in PROFILES:
        return PROFILES[slug]
    from models import PlatformProfileRow
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if row is None:
        raise KeyError(f"Unknown platform: {slug}")
    return _build_profile_from_row(row)
```

Aufrufer (`fetch_sample_mails`, `EmailJobsAdapter` constructor, etc.)
nutzen die neue Funktion statt direkten `PROFILES[slug]`-Zugriff.

### Auto-Generation aus Domain

`_build_profile_from_row(row)` baut einen `PlatformProfile` mit
generischen Defaults wenn keine Overrides gesetzt sind:

| Feld | Auto-Generation aus `domain` |
|---|---|
| `from_whitelist` | `(rf"@(?:[a-z0-9.-]+\.)?{re.escape(domain)}$",)` |
| `url_pattern` | `re.compile(rf"https?://(?:[a-z0-9.-]+\.)?{re.escape(domain)}/[^\s)<>\"'\\]+", re.I)` |
| `subject_patterns` | `(re.compile(r"^(?P<title>.+?)\s+(?:bei\|at\|@)\s+(?P<company>.+?)\s*$", re.I),)` |
| `body_title_re` | `_GENERIC_BODY_TITLE_RE` (existierendes Default) |
| `body_company_re` | `_GENERIC_BODY_COMPANY_RE` |
| `body_location_re` | `_GENERIC_BODY_LOCATION_RE` |
| `body_card_re` | `None` (AI-Pattern-Learner liefert das beim Train) |
| `hard_title_blacklist_re` | `None` |
| `from_filter` | `f"from:{domain}"` |
| `name` | `slug` |
| `source_label` | `display_name` |

Wenn `url_pattern_override` gesetzt: nutze den statt Auto-Gen. Same für
`from_whitelist_override`.

### API-Endpoints

Neu in `api/admin.py` (admin-required via `@admin_required`):

```
GET    /api/admin/platforms                  → [{slug, display_name, domain, ...}, ...]
POST   /api/admin/platforms                  → create  {slug, display_name, domain, ...}
PATCH  /api/admin/platforms/<slug>           → update
DELETE /api/admin/platforms/<slug>           → delete (mit FK-Check auf JobSource.type==<slug>_email)
```

Validation in POST/PATCH:
- `slug`: regex `^[a-z0-9_-]{2,64}$`, NICHT in `PROFILES.keys()`, nicht
  bereits in DB
- `domain`: regex `^[a-z0-9.-]+\.[a-z]{2,}$`
- `subject_must_contain`: Liste mit 1–20 Strings, jeweils ≤80 chars
- `url_pattern_override` (optional): muss compilebar sein, sonst 400
- `from_whitelist_override` (optional): muss compilebar sein

DELETE-Endpoint prüft via `JobSource.query.filter_by(type=f"{slug}_email").count() > 0` →
wenn Sources existieren: 409 mit Error "Plattform wird noch von N JobSource(s) genutzt".

### Frontend

Neuer Admin-Tab „🌐 Plattformen" in `index.html` (im bestehenden Admin-UI):

**Tabelle:** Slug, Anzeige-Name, Domain, Subject-Keywords, AI-Hint, Aktion
- Hardcoded Plattformen (Indeed/LinkedIn/XING) werden als read-only
  Einträge angezeigt mit Hinweis „(Hardcoded — nicht editierbar)"
- DB-Plattformen mit „Bearbeiten" / „Löschen"-Button

**Wizard-Modal „+ Neue Plattform":**

| Feld | Eingabe | Default | Auto-derived |
|---|---|---|---|
| Anzeige-Name | text | (leer) | — |
| Domain | text | (leer) | — |
| Subject-Keywords (kommagetrennt) | text | (leer) | — |
| AI-Hint | textarea | (leer) | — |
| Slug | text | (auto aus Anzeige-Name, lowercase, `-` ↔ `_`) | overridable |
| URL-Pattern (Advanced, optional) | text | (auto) | aus `domain` |
| From-Whitelist (Advanced, optional) | text | (auto) | aus `domain` |

„Speichern" → POST `/api/admin/platforms` → bei Success: Modal schließen,
Tabelle reloaden.

**Bestehender JobSource-Editor anpassen** (`index.html:3625+`):
- Aktueller Type-Selector: hardcoded `rss`, `adzuna`, `bundesagentur`,
  `arbeitnow`, `indeed_email`, `bulk_email`
- Neu: für jede DB-Plattform `<slug>_email` als Option hinzufügen
- Beim Page-Load: GET `/api/admin/platforms`, dann Selector dynamisch
  füllen mit DB-Plattformen ergänzt

### Datenfluss

1. Admin öffnet „🌐 Plattformen" → GET `/api/admin/platforms` lädt Liste
2. „+ Neue Plattform" Modal → 4 Pflichtfelder → POST → DB-Row erstellt
3. Im JobSource-Selector erscheint neue `<slug>_email`-Option
4. User legt JobSource damit an (z.B. „Stepstone IT-Jobs", folder `Stepstone`)
5. Klick auf 🧠 Lernen → `fetch_sample_mails` ruft `get_profile(slug)` →
   resolved aus DB → AI lernt Pattern → speichert als
   `LearnedEmailPattern(platform=slug, ...)`
6. Cron-Crawl: `EmailJobsAdapter` ruft `get_profile(slug)` → DB-Plattform
   wird wie Indeed/LinkedIn/XING gehandhabt

## Error-Handling

| Fall | Verhalten |
|---|---|
| Slug-Kollision mit hardcoded | 400 + `{"error": "Slug 'indeed' ist reserviert"}` |
| Slug schon in DB | 400 + `{"error": "Slug 'stepstone' existiert bereits"}` |
| Ungültiges `url_pattern_override` (Regex-Compile-Error) | 400 + `{"error": "URL-Pattern ungültig: ..."}` |
| DELETE auf Plattform mit Refs | 409 + `{"error": "Plattform wird von 2 JobSource(s) genutzt"}` |
| Non-Admin POST/PATCH/DELETE | 403 |
| Domain-Format ungültig | 400 |

## Testing

Pytest-Datei `tests/test_platform_profiles.py`:

1. **Model**:
   - `PlatformProfileRow` create/query/delete
   - Slug-Unique-Constraint
2. **`get_profile`**:
   - Resolve hardcoded → returnt aus PROFILES
   - Resolve DB-slug → konstruiert PlatformProfile aus Row
   - Unknown slug → KeyError
3. **`_build_profile_from_row`**:
   - Auto-Generation: `from_whitelist` matched `user@stepstone.de`
   - Auto-Generation: `url_pattern` matched `https://stepstone.de/job/123`
   - Override: wenn `url_pattern_override` gesetzt, der wird genutzt
4. **API**:
   - GET als admin → 200 + Liste
   - GET als regular user → 403
   - POST: validation (slug-format, slug-reserved, domain-format)
   - DELETE: blocked wenn JobSource references it
5. **Frontend** — manuelle Smoke-Tests dokumentiert im Plan

## Deployment

- Alembic-Migration für `platform_profiles`-Tabelle
- Kein Schema-Change an `JobSource` (type-Feld bleibt `String(32)`)
- Frontend: `service-worker.js` `CACHE_NAME` bumpen
- VPS-Deploy via `bewerbungen-deploy.sh`

## Risiken

- **Generischer URL-Pattern kann zu breit matchen** — z.B. wenn die Plattform
  auch Footer-Tracking-Links auf der gleichen Domain hat. Override-Feld als
  Escape-Hatch. AI-Pattern-Learner kann diese herausfiltern via
  `body_card_re`.

- **JobSource.type-Format** — heute `indeed_email`, `linkedin_email`, etc.
  Bei DB-Plattformen wäre der Type `<slug>_email`. Das Format muss
  konsistent bleiben damit der Adapter beim Crawl erkennt: „Type endet auf
  `_email` → benutze `EmailJobsAdapter` mit slug = type[:-len('_email')]".
  Heute hat `api/jobs_cron.py` (oder ähnlich) wahrscheinlich Hardcoded-Switch
  auf Type. Muss ggf. angepasst werden.

- **Validation der Regex-Overrides** — User kann böswillig regex DoS
  einfügen. Mitigation: `re.compile` mit Timeout (via `re2` falls verfügbar,
  oder length-limit auf Pattern-String ≤500 Zeichen). Reicht für MVP.

## Backward Compatibility

- Bestehende JobSources mit `type ∈ {indeed_email, linkedin_email, xing_email}`
  funktionieren unverändert weiter (Hardcoded-PROFILES haben Vorrang)
- Bestehende `LearnedEmailPattern`-Einträge bleiben gültig
- Keine Migration der bestehenden 3 Plattformen
