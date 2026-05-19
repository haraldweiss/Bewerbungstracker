# Email-Pattern-Lerner — Design

**Datum:** 2026-05-19
**Author:** Harald Weiss (mit Claude Opus 4.7)
**Status:** Draft — wartet auf User-Review
**Vorgänger-Spec:** [2026-05-19-email-jobs-linkedin-xing-design.md](./2026-05-19-email-jobs-linkedin-xing-design.md)

## Ziel

Email-Job-Source-Pattern (Subject-Regex, Body-Card-Regex,
Title-Blacklist) adaptiv anpassbar machen. Bei LinkedIn/Xing/Indeed
Layout-Drift kann ein User auf Knopfdruck den AI ein neues Pattern
lernen lassen, ohne dass ein Entwickler Regex pflegen muss.

## Ausgangslage

- LinkedIn/Xing-Adapter wurde mit hardcoded `body_card_re` /
  `subject_patterns` deployed. Live-Test ergab: 28 von 100 LinkedIn-Mails
  parseable, der Rest fehlt durch Layout-Variationen.
- Hardcoded Pattern bricht bei nächstem Mail-Redesign — keine
  Wartungs-Strategie etabliert.
- ai-provider-service existiert bereits auf VPS mit Multi-Provider-
  Fallback (Ollama-Mac-Tunnel → Claude-Cloud).

## Architektur

### Komponenten-Übersicht

1. **Datenmodell:** neue Tabelle `learned_email_patterns` (global pro Plattform)
2. **Service-Layer:** `services/job_sources/pattern_learner.py` —
   `fetch_sample_mails`, `ai_learn_pattern`, `compile_pattern`,
   `validate_pattern`
3. **Adapter-Integration:** `EmailJobsAdapter._parse_email` liest active
   `LearnedEmailPattern` und überstimmt Profile-Defaults
4. **API:** `POST /api/jobs/sources/<id>/train-pattern`,
   `GET /api/jobs/learned-patterns`,
   `POST /api/jobs/learned-patterns/<platform>/rollback`
5. **UI:** 🧠-Button pro Source, Warn-Badge bei niedriger Hit-Rate,
   Settings-Karte „Gelernte Pattern" mit Rollback

### Was bleibt unverändert

- Hardcoded `body_card_re` / `subject_patterns` in `PROFILES` bleiben als
  Default-Fallback (wenn keine learned-Row für die Plattform aktiv).
- `url_pattern` + `from_whitelist` bleiben hardcoded
  (Security-relevant, sollen nicht via AI-Train veränderbar sein).
- Bestehender Indeed-Email-Cron + import-from-email-Endpoint unverändert.

## Datenmodell

### Tabelle `learned_email_patterns`

```sql
CREATE TABLE learned_email_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        VARCHAR(32) NOT NULL,
    pattern_json    TEXT NOT NULL,
    sample_count    INTEGER NOT NULL,
    hit_rate        REAL NOT NULL,
    trained_at      DATETIME NOT NULL,
    trained_by_user_id  UUID NOT NULL REFERENCES users(id),
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    rolled_back_at  DATETIME NULL,
    rolled_back_by_user_id  UUID NULL REFERENCES users(id)
);

CREATE INDEX ix_lep_platform_active ON learned_email_patterns(platform, is_active);
CREATE UNIQUE INDEX ux_lep_one_active_per_platform
    ON learned_email_patterns(platform) WHERE is_active = 1;
```

### Versionierung

- Jedes Train **erzeugt eine neue Row** (kein UPDATE).
- Aktivierung: in **einer Transaktion** alte aktive Row `is_active = False`
  + neue Row `is_active = True`.
- Rollback: aktuelle aktive → `is_active = False, rolled_back_at, rolled_back_by`;
  vorige Row für selbe Plattform → `is_active = True`.

### SQLAlchemy-Modell (`models.py`)

```python
class LearnedEmailPattern(db.Model):
    __tablename__ = 'learned_email_patterns'
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(32), nullable=False, index=True)
    pattern_json = db.Column(db.Text, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    hit_rate = db.Column(db.Float, nullable=False)
    trained_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trained_by_user_id = db.Column(UUID, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    rolled_back_at = db.Column(db.DateTime, nullable=True)
    rolled_back_by_user_id = db.Column(UUID, db.ForeignKey('users.id'), nullable=True)
```

### Alembic-Migration

`versions/<hash>_add_learned_email_patterns.py` — Tabelle + Index + Partial-Unique.

## JSON-Pattern-Schema

```json
{
  "subject_pattern": {
    "prefix_optional": true,
    "prefix_keywords": ["Neue Stelle", "Job alert", "New job", "Stellenangebot"],
    "separator": "bei|at|@"
  },
  "body_card": {
    "url_labels": ["Jobangebot ansehen", "View job", "Show job"],
    "fields_before_url": ["title", "company", "location"],
    "separator_lines_allowed": 5
  },
  "filters": {
    "title_blacklist": [
      "Ihre Jobbenachrichtigung",
      "Top-Jobs für Sie",
      "Lust auf",
      "\\d+ neue Jobs?"
    ],
    "company_blacklist_separators": ["----", "===="]
  }
}
```

**Schema-Validation** via `jsonschema` library. Bei Fail: 1 Retry mit
verschärfter Prompt, dann HTTP 502.

**Daraus baut `compile_pattern`** deterministisch:
- `body_card_re`: Regex aus `fields_before_url` + `url_labels` +
  `separator_lines_allowed` (analog zum aktuellen LinkedIn-Pattern, aber
  mit den Werten aus JSON)
- `subject_re`: Regex mit optionalem Prefix + `separator`
- `title_blacklist_re`: kombinierter Alternations-Pattern aus Liste

**NICHT im Schema** (bewusst):
- Freier Regex vom AI (ReDoS-Risiko)
- URL-Pattern (ändert sich praktisch nie)
- From-Whitelist (Security)
- HTML-Selektoren (Plain-Text reicht)
- Multi-Language jenseits DE+EN

## Pattern-Lern-Workflow

`POST /api/jobs/sources/<id>/train-pattern`

**Body (optional):**
```json
{ "sample_size": 30, "train_size": 5, "min_hit_rate": 0.40 }
```

**Defaults:** sample_size=30, train_size=5, min_hit_rate=0.40

**Schritte:**

1. Auth + Ownership-Check (`source.user_id == user.id`, `source.type` ist
   `*_email`)
2. **Rate-Limit-Check:** wenn `LearnedEmailPattern.query.filter(platform=...,
   trained_at > now - 1h).first()` → HTTP 429
3. `platform = source.type.removesuffix('_email')`
4. `fetch_sample_mails(user, source.config, n=sample_size)` via bestehender
   `EmailJobsAdapter._fetch_emails`-Logik
5. Split: `train = mails[:train_size]`, `test = mails[train_size:]`
6. `ai_learn_pattern(train, platform_hint=platform)`:
   - Prompt-Template (System + User) inkl. Schema-Hint
   - Truncate Body auf ~8k Chars pro Mail
   - Call via `ai_provider_client.chat(...)`
   - JSON-Schema-Validation; bei Fail: 1 Retry mit härterer Prompt
7. `compile_pattern(pattern_dict) → CompiledPattern`
   - Regex-Compile mit Timeout-Schutz (regex-library statt re)
   - Bei Compile-Error: HTTP 502
8. `validate_pattern(compiled, test_mails)`:
   - Wende `body_card_re` auf jede Test-Mail an
   - Zähle Mails mit ≥1 Card-Match
   - `hit_rate = matched / len(test)`
9. Wenn `hit_rate < min_hit_rate`: HTTP 422 mit
   `{error, hit_rate, sample_count, sample_diagnostics: [...]}`,
   kein DB-Save
10. Wenn ≥: DB-Transaction (alte deactivate + neue activate), HTTP 200
    mit Pattern-Übersicht + 3 example_matches

### ReDoS-Schutz

- Regex wird **selbst aus dem JSON gebaut** — AI liefert Daten, nicht
  Pattern. Daher kein ReDoS-Risiko aus AI-Output.
- Optional: `regex` library statt `re` + Match-Timeout 200ms pro Mail.

### Rate-Limiting

- **1 Train pro Plattform pro Stunde, system-weit.**
- Implementation: DB-Query gegen `trained_at`.

## Adapter-Integration

`services/job_sources/email_jobs.py:EmailJobsAdapter._parse_email`:

- Beim ersten `_parse_email`-Call der Instance: lookup
  `LearnedEmailPattern.query.filter_by(platform=self.profile.name, is_active=True).first()`.
- Result cachen in `self._learned_pattern` (für Lebensdauer der Adapter-Instance).
- Wenn vorhanden: nutze `learned.body_card_re` statt `self.profile.body_card_re`;
  gleiche Logik für `subject_re`; `title_blacklist_re` wird zusätzlich angewandt.
- Wenn nicht vorhanden: hardcoded Defaults aus `PROFILES`.

## Rollback-Endpoint

`POST /api/jobs/learned-patterns/<platform>/rollback`

1. Finde `current = LearnedEmailPattern.query.filter_by(platform=..., is_active=True).first()`
2. Finde `prev = LearnedEmailPattern.query.filter(platform=...,
   trained_at < current.trained_at).order_by(trained_at.desc()).first()`
3. Wenn kein `prev`: HTTP 400 „Keine ältere Version vorhanden"
4. Transaction:
   - `current.is_active = False, rolled_back_at=now, rolled_back_by=user`
   - `prev.is_active = True`
5. HTTP 200 mit `{rolled_back_from, restored_pattern}`

## UI

### Sources-Tabelle

Pro Email-Source-Zeile zusätzlicher 🧠-Button neben `📧 Import`. Klick
öffnet Confirm-Dialog (Sample-Size, Cost-Hinweis), nach OK Spinner +
Status-Updates. Erfolg/Fehler-Toast.

### Warn-Badge

Nach jedem regulären Import (📧 Import) merkt sich der Adapter
`parsed / fetched`. Wenn `< 0.20` UND `fetched ≥ 10`:
- `JobSource.last_error = "pattern_low_hit_rate: 4/25 (16%)"`
- Source-Zeile zeigt **⚠️ Pattern könnte veraltet sein** als Status-Badge
- Tooltip: „Importer-Trefferquote nur 16 %. Klick auf 🧠 um Pattern neu zu lernen."

### Gelernte-Patterns-Übersicht

Neue Karte in Settings → Bewerbungen & Jobs:

```
🧠 Gelernte Pattern

Plattform   Hit-Rate  Trainiert am          Von           Aktion
LinkedIn    56%       2026-05-19 14:23      harald        [↶ Rollback]
XING        80%       (Hardcoded Default)   —             —
Indeed      —         (Hardcoded Default)   —             —
```

Rollback-Button erscheint nur wenn `LearnedEmailPattern.query.filter(
platform=..., trained_at < current.trained_at).count() >= 1`.

### Service Worker

CACHE_NAME bumpen `bewerbungs-tracker-v39` → `bewerbungs-tracker-v40`.

## Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| AI gibt unsinniges JSON | jsonschema-Validation + 1 Retry mit härterer Prompt + bei 2. Fail HTTP 502 |
| AI-Train teuer (Claude API) | Rate-Limit 1/Plattform/h, Cost-Hint im Confirm-Dialog |
| Pattern bricht für andere User (System-weit) | Versionierung, Rollback-Button, Audit-Log per `trained_by_user_id` |
| Hit-Rate-Schwelle 40 % zu lasch/streng | API-Body erlaubt `min_hit_rate`-Override (curl/Power-User); UI nutzt festen Default 0.40 in Iter. 1 |
| Train hängt > 60 s | Dedicated Timeout 60 s pro AI-Call; bei Timeout HTTP 504, Default bleibt |
| Race Condition: zwei User starten Train | Partial-Unique-Index + Transaction |
| Adapter-Performance regrediert | `_learned_pattern` per Instance gecacht |
| ReDoS durch AI-Output | Pattern aus Daten gebaut; `regex` library mit Timeout |

## Testing

**Unit-Tests** (`tests/services/test_pattern_learner.py`):
- `compile_pattern` baut korrekte Regex aus Schema-JSON
- `validate_pattern` zählt Hits korrekt
- JSON-Schema-Validation lehnt invalide Strukturen ab
- Pattern-Compile-Timeout funktioniert

**Integration-Tests** (`tests/api/test_pattern_learner_api.py`):
- `POST /train-pattern` Happy Path (AI gemockt)
- Rate-Limit-Reject (HTTP 429) nach 2. Train binnen 1h
- Hit-Rate < 40 % → 422, kein DB-Save
- Rollback funktioniert (alte Row wird wieder aktiv)
- Rollback ohne History → 400
- Schema-Validation-Fail + Retry → wenn beide fail → 502

**E2E manuell** auf VPS gegen echte LinkedIn-/XING-Mails (wie in
Vorgänger-Spec).

**Mock-Strategie:** `ai_provider_client.chat` wird gemockt mit festen
JSON-Antworten. Tests laufen offline.

## Done-Definition

- Alembic-Migration deployed (Tabelle existiert auf VPS)
- `services/job_sources/pattern_learner.py` mit allen 4 Funktionen
- `EmailJobsAdapter._parse_email` nutzt `LearnedEmailPattern` wenn aktiv
- 3 API-Endpoints + Tests grün
- UI: 🧠-Button pro Source + Warn-Badge + Settings-Karte „Gelernte Pattern"
- service-worker.js v40
- Memory: `project_email_jobs_import_live.md` bekommt Abschnitt
  „Pattern-Lerner"

## Out of Scope

- Pro-User-Override globaler Pattern (zu früh)
- Edit-Modus für gelerntes Pattern (JSON manuell ändern)
- Diff-View zwischen Pattern-Versionen (nice-to-have, später)
- HTML-Body-Parsing (Plain-Text reicht aktuell)
- Automatischer Re-Train (nur UI-Hint, kein Auto-AI-Call)
- Multi-Language jenseits DE+EN
