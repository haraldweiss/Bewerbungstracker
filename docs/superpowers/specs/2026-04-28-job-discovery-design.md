# Job-Discovery & Auto-Matching — Design Spec

**Datum:** 2026-04-28
**Status:** Design (zur Review)
**Autor:** Brainstorming-Session mit Harald Weiss

---

## 1. Ziel & Motivation

Erweiterung des Bewerbungstrackers um eine **automatische Stellensuche**, die regelmäßig
neue Stellenausschreibungen aus konfigurierbaren Quellen abruft, gegen den hinterlegten
Lebenslauf des Users abgleicht und passende Treffer im Tracker anzeigt.

Bisher ist der Tracker rein **reaktiv** (User trägt Bewerbungen manuell ein, Email-Monitor
verfolgt Antworten). Mit diesem Feature wird er **proaktiv** — er schlägt aktiv neue
Stellen vor, bevor der User selbst sucht.

### User-Story (Kern)

> Als Job-Suchender möchte ich, dass der Tracker im Hintergrund passende Stellen aus
> verschiedenen Portalen (Bundesagentur, Adzuna, RSS-Feeds spezialisierter Job-Boards)
> sammelt und mir die besten Matches mit Begründung anzeigt, damit ich nicht jeden
> Tag manuell auf 5 Portalen suchen muss.

---

## 2. Design-Entscheidungen (aus Brainstorming)

| # | Aspekt | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Quellen | RSS + offizielle APIs (Bundesagentur, Adzuna, Arbeitnow) — Hybrid System-Defaults + User-konfigurierbar | Stabil, keine ToS-Verstöße, gute Abdeckung deutscher Markt |
| 2 | Matching | Zweistufig: lokales Pre-Filtering → Claude-Bewertung der Top-Kandidaten | Balance Kosten/Qualität, nutzt Phase-2-Routing-Service |
| 3 | Worker-Architektur | VPS via externer Cron-Service (cron-job.org o.ä.) | IONOS Shared-Hosting hat keinen Cron, kleine Requests bleiben unter Timeout |
| 4 | Pipeline-Form | 4 separate Stages (crawl → prefilter → claude-match → notify) | Robustheit, Cost-Cap pro Stage, debugbar |
| 5 | User-Aktion | Anzeige + Push-Notification + One-Click-Übernahme als Bewerbung. Phase 2: Claude-generierte Anschreiben-Drafts | Sofort-Wert ohne Cost-Explosion |
| 6 | KI-Provider | BYOK (Bring Your Own Key) — User hinterlegt eigene Credentials. Auch Custom-HTTP-Endpoints (Ollama, vLLM, OpenRouter) | Kosten beim User, Self-Hosting möglich |

---

## 3. Datenmodell

### 3.1 Neue Tabelle: `job_sources` (universelle Feed-Verwaltung)

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | INT PK | |
| `user_id` | INT FK NULL | NULL = system-globale Quelle, sonst user-eigen |
| `name` | TEXT NOT NULL | z.B. "StepStone Frontend Berlin" |
| `type` | TEXT NOT NULL | `rss` \| `adzuna` \| `bundesagentur` \| `arbeitnow` |
| `config` | JSON NOT NULL | type-spezifische Config (siehe 3.4) |
| `enabled` | BOOL DEFAULT 1 | |
| `crawl_interval_min` | INT DEFAULT 60 | Mindest-Intervall zwischen Crawls |
| `last_crawled_at` | TIMESTAMP NULL | |
| `last_error` | TEXT NULL | Letzter Fehler beim Crawlen |
| `consecutive_failures` | INT DEFAULT 0 | Counter für Auto-Disable |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### 3.2 Neue Tabelle: `raw_jobs`

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | INT PK | |
| `source_id` | INT FK NOT NULL | |
| `external_id` | TEXT NOT NULL | Job-URL oder Feed-GUID, eindeutig pro Source |
| `title` | TEXT NOT NULL | |
| `company` | TEXT | |
| `location` | TEXT | |
| `url` | TEXT NOT NULL | Original-Link zur Stelle |
| `description` | TEXT | |
| `posted_at` | TIMESTAMP | |
| `raw_payload` | JSON | Vollständiger Roh-Datensatz (Debugging) |
| `crawl_status` | TEXT | `raw` \| `prefiltered` \| `matched` \| `archived` |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |

**Index:** `UNIQUE (source_id, external_id)`

### 3.3 Neue Tabelle: `job_matches` (per-User Bewertung)

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | INT PK | |
| `raw_job_id` | INT FK NOT NULL | |
| `user_id` | INT FK NOT NULL | |
| `prefilter_score` | FLOAT NULL | 0–100, lokale Heuristik |
| `match_score` | FLOAT NULL | 0–100, Claude-Bewertung |
| `match_reasoning` | TEXT NULL | Claude-Begründung |
| `missing_skills` | JSON NULL | Liste von Skills, die im CV fehlen |
| `status` | TEXT NOT NULL | `new` \| `seen` \| `imported` \| `dismissed` |
| `notified_at` | TIMESTAMP NULL | |
| `imported_application_id` | INT FK NULL | Verknüpfung zur erstellten Bewerbung |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Indizes:**
- `(user_id, status, match_score DESC)` — Frontend-Listing
- `(prefilter_score) WHERE match_score IS NULL` — Stage 3 Selektion
- `UNIQUE (raw_job_id, user_id)`

### 3.4 Source-Config-Schemas (JSON)

Pro `type` validiertes Schema:

**`rss`:**
```json
{"url": "https://example.com/feed.xml"}
```

**`adzuna`:**
```json
{"app_id": "...", "app_key": "...", "country": "de", "what": "frontend developer", "where": "Berlin", "results_per_page": 50}
```

**`bundesagentur`:**
```json
{"was": "Frontend Entwickler", "wo": "10115", "umkreis": 25, "arbeitszeit": "vz", "befristung": "befristet"}
```

**`arbeitnow`:**
```json
{"tags": ["javascript", "remote"], "visa_sponsorship": false}
```

### 3.5 Neue Tabelle: `user_ai_credentials` (BYOK)

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | INT PK | |
| `user_id` | INT FK NOT NULL | |
| `provider` | TEXT NOT NULL | `anthropic` \| `custom_openai_compat` \| `custom_anthropic_compat` \| `custom_template` |
| `encrypted_api_key` | BLOB NULL | Mit User-DEK verschlüsselt (Envelope-Encryption) |
| `key_nonce` | BLOB NULL | |
| `endpoint_url` | TEXT NULL | Für custom_*-Provider |
| `auth_header_name` | TEXT NULL | z.B. `Authorization` |
| `encrypted_auth_header_value` | BLOB NULL | |
| `auth_nonce` | BLOB NULL | |
| `default_model` | TEXT NULL | z.B. `claude-haiku-4-5-20251001` |
| `request_template` | JSON NULL | Nur custom_template |
| `response_path` | TEXT NULL | JSONPath, nur custom_template |
| `monthly_budget_cents` | INT NULL | Hard-Limit Cost pro Monat |
| `is_active` | BOOL DEFAULT 0 | Wird true nach erfolgreichem Test |
| `created_at`, `updated_at` | TIMESTAMP | |

**Constraint:** Maximal 1 aktive Credentials-Eintrag pro `(user_id, provider)`.

### 3.6 Erweiterung der bestehenden `api_calls`-Tabelle

Neues Feld:

| Spalte | Typ | Anmerkung |
|---|---|---|
| `key_owner` | TEXT NOT NULL DEFAULT 'server' | `server` \| `user` \| `custom_endpoint` |

### 3.7 Erweiterung der bestehenden `user_settings`-Tabelle

Neue Felder für Job-Discovery (alle nullable mit sinnvollen Defaults im Code):

| Spalte | Typ | Default | Anmerkung |
|---|---|---|---|
| `job_discovery_enabled` | BOOL | 0 | Master-Schalter pro User |
| `job_language_filter` | JSON | `["de","en"]` | Liste akzeptierter Sprachen |
| `job_region_filter` | JSON | `null` | z.B. `{"plz_prefixes": ["10","11"], "remote_ok": true}`. NULL = kein Filter |
| `job_notification_threshold` | INT | 80 | Match-Score ab dem notified wird |
| `job_claude_budget_per_tick` | INT | 5 | Max Claude-Calls pro Cron-Tick |
| `job_daily_budget_cents` | INT | 50 | Hard-Limit Cost pro Tag |

---

## 4. Pipeline-Architektur (4 Cron-Stages)

Alle Endpoints unter `/api/jobs/*`, geschützt mit `X-Cron-Token`-Header (env-var
`JOB_CRON_TOKEN`). Externer Cron-Service ruft sie nach Schedule auf:

```
*/15 * * * *      → POST /api/jobs/crawl-source
*/15 * * * *      → POST /api/jobs/prefilter      (5 Min versetzt)
*/30 * * * *      → POST /api/jobs/claude-match
*/30 * * * *      → POST /api/jobs/notify          (5 Min versetzt)
0 3 * * *         → POST /api/jobs/cleanup         (täglich nachts)
```

### Stage 1: `POST /api/jobs/crawl-source`

**Aufgabe:** Eine fällige Quelle abrufen, Roh-Jobs in DB ablegen.

**Verhalten:**
1. Wähle Quelle mit `enabled=1` UND `last_crawled_at + crawl_interval_min < now()`,
   sortiert nach `last_crawled_at ASC` (Round-Robin).
2. Lade Daten via type-spezifischem Adapter (RSS / Adzuna-API / etc.).
3. Pro Job: Insert in `raw_jobs` (Dedup über `(source_id, external_id)`).
4. Für jeden Match-fähigen User Insert `job_matches`-Stub mit `status='new'`,
   `prefilter_score=NULL`, `match_score=NULL`.
   **Match-fähig** ist ein User, der **alle** drei Bedingungen erfüllt:
   (a) `user.is_active=1`,
   (b) hat Job-Discovery aktiviert (neues Feld `user_settings.job_discovery_enabled`),
   (c) hat ein hinterlegtes CV (`user_profile.cv_text IS NOT NULL`) — ohne CV kein Matching.
5. Update `source.last_crawled_at`, reset `consecutive_failures` bei Erfolg.

**Limits:** Max 1 Quelle pro Aufruf, max 50 neue Jobs pro Quelle, Hard-Stop bei 25s.

**Fehlerverhalten:**
- HTTP-Error / Timeout: `last_error` setzen, `consecutive_failures += 1`.
- Bei `consecutive_failures >= 5`: `enabled=0`, Notification an Owner-User der Quelle.

### Stage 2: `POST /api/jobs/prefilter`

**Aufgabe:** Lokales Keyword-Scoring der `job_matches` mit `prefilter_score IS NULL`.

**Algorithmus:**
1. Tokenisiere User-CV einmal pro Aufruf (cached pro User pro Tick):
   - Skills aus CV-Profil-Sektion (`db.user_profile.skills`)
   - Job-Titel-Historie aus `applications`
   - Tech-Stack aus CV-Volltext
2. Tokenisiere Job: Title (× 2) + Description (× 1) + Skills-Tags (× 3)
3. Score = gewichteter Overlap-Anteil, normalisiert auf 0–100
4. Negative Filter (jeder schiebt Score auf 0):
   - Sprache nicht in User-`language_filter`
   - Region nicht in User-`region_filter` (wenn gesetzt)
   - Job > 60 Tage alt
5. Setze `prefilter_score`, falls < 30 dann `status='dismissed'` (Auto-Verworfen).

**Limits:** Max 100 `job_matches` pro Aufruf.

### Stage 3: `POST /api/jobs/claude-match`

**Aufgabe:** Top-Kandidaten von Claude bewerten lassen.

**Verhalten:**
1. Pro User mit aktiven AI-Credentials:
   1.1. Prüfe Tagesbudget (Sum `api_calls.cost_cents` heute) ≤ User-Limit
   1.2. Lade Top-N `job_matches` mit `prefilter_score >= 30 AND match_score IS NULL`,
        sortiert nach `prefilter_score DESC`. N = User-Setting `claude_match_budget_per_tick` (Default 5).
   1.3. Pro Job: AI-Provider-Adapter ruft Provider auf (Anthropic / Custom-Endpoint),
        Prompt enthält CV-Auszug + Job-Title + Job-Description + Job-Location.
   1.4. Antwort als JSON erwartet: `{score: 0-100, reasoning: string, missing_skills: string[]}`.
   1.5. Bei ungültigem JSON: 1× Retry mit strengerem Prompt, sonst `match_score=0`,
        `match_reasoning="Bewertung fehlgeschlagen"`.
   1.6. Update `job_matches.match_score`, `match_reasoning`, `missing_skills`.
   1.7. Update `raw_jobs.crawl_status='matched'`.
   1.8. Log `api_calls` mit `key_owner` (`user` / `custom_endpoint` / `server`).

**Limits:** Hard-Stop bei 25s, Tages-Budget pro User.

### Stage 4: `POST /api/jobs/notify`

**Aufgabe:** Push-Notifications für neue Hi-Score-Matches.

**Verhalten:**
1. Lade `job_matches` mit `match_score >= user.notification_threshold` (Default 80)
   AND `notified_at IS NULL` AND `status='new'`.
2. Sende Push-Notification über bestehende Notifications-Infrastruktur:
   "Neue Stelle: <title> bei <company> — Match-Score <score>".
3. Setze `notified_at = now()`.

**Limits:** Max 20 Notifications pro Tick (Spam-Schutz).

### Stage 5: `POST /api/jobs/cleanup` (täglich)

**Aufgabe:** Datenhygiene.

**Verhalten:**
1. Archiviere `raw_jobs` älter als 60 Tage UND ohne `job_matches` mit
   `status IN ('new', 'imported')`.
2. Lösche dazugehörige `job_matches` mit `status IN ('seen', 'dismissed')` älter als 60 Tage.
3. Reset `consecutive_failures` für Quellen, deren `last_error IS NULL` seit 7 Tagen.

---

## 5. AI-Provider-Adapter

Ein gemeinsames Interface `AIProvider` mit den Methoden:
- `match_job(cv_summary: str, job: dict) -> MatchResult`
- `test_connection() -> bool`

### 5.1 Implementierungen

**`AnthropicProvider`** (offizieller Anthropic-API-Key):
- Nutzt `anthropic` Python-SDK
- Modell aus `default_model` (Default `claude-haiku-4-5-20251001`)
- Kosten via SDK-Response-Headers

**`OpenAICompatProvider`** (Self-Hosted + Drittanbieter):
- HTTP POST an `endpoint_url` mit OpenAI Chat-Completions-Format
- Optional Bearer-Auth via `auth_header_*` Felder
- Funktioniert mit: Ollama (`/v1/`), LM Studio, vLLM, LocalAI, OpenRouter, Groq, Together.ai
- Kosten via `usage`-Feld der Response (sofern vorhanden), sonst `cost=0`

**`AnthropicCompatProvider`** (Anthropic-kompatible Proxies):
- HTTP POST mit Anthropic `/v1/messages`-Format

**`CustomTemplateProvider`** (Power-User-Escape-Hatch):
- User-definiertes Mustache-Template für Request-Body
- User-definierter JSONPath für Response-Extraktion
- Variablen verfügbar: `{{prompt}}`, `{{system}}`, `{{cv_summary}}`, `{{job_title}}`, `{{job_description}}`

### 5.2 Provider-Factory

`ai_provider_factory.get_provider(user_id) -> AIProvider`:
1. Lade `user_ai_credentials WHERE user_id=? AND is_active=1` (höchste Priorität: `provider='anthropic'`)
2. Wenn keiner: Falls env `ALLOW_SERVER_FALLBACK_KEY=true`, nutze Server-Default
3. Sonst: Raise `NoCredentialsError` → Stage 3 überspringt User

### 5.3 KeyCache

API-Keys und Auth-Header werden nach Decrypt 5 Minuten in einem In-Memory-Cache
gehalten (analog zur bestehenden DEK-Cache-Logik aus der Envelope-Encryption).
Reduziert Crypto-Overhead bei Stage 3 mit vielen Jobs.

---

## 6. Frontend-Integration

### 6.1 Neuer Tab: "🔍 Job-Vorschläge"

**Filter-Bar (oben):**
- Score-Slider (Mindest-Match-Score, Default 60)
- Status-Multi-Select: Neu / Gesehen / Übernommen / Verworfen
- Quellen-Dropdown
- Volltext-Suche (Titel + Firma)

**Karten-Liste:**
Sortiert nach `match_score DESC`. Pro Karte:
- Score-Badge (farbcodiert: 🟢 ≥80, 🟡 60–79, ⚪ <60)
- Job-Titel + Firma
- Location · Veröffentlichungsdatum · Quelle
- Match-Begründung (Claude-Output)
- Liste fehlender Skills (falls vorhanden)
- Buttons: **Original ansehen** / **Übernehmen** / **Verwerfen** / **Verbergen**

**Pagination:** 50 Karten pro Seite, klassische Pagination.

### 6.2 Settings-Bereich "Job-Suche"

- **Quellen-Verwaltung:** Tabelle mit eigenen + globalen Quellen, Quellen-Tester
- **Matching-Einstellungen:** Notification-Schwelle, Claude-Budget pro Tick, Sprach- und Regions-Filter

### 6.3 Settings-Bereich "🤖 KI-Konfiguration"

- Liste hinterlegter Provider (Key maskiert)
- "+ Provider hinzufügen"-Modal mit dynamischem Form je Provider-Typ
- "Verbindung testen"-Button (Pflicht vor Aktivierung)
- Verbrauchs-Statistik (Calls / Tokens / Cost) pro Provider
- Optionales Monatsbudget

### 6.4 REST-Endpoints

**Job-Matches (User-JWT-geschützt):**
| Methode + Path | Zweck |
|---|---|
| `GET /api/jobs/matches` | Query: status, min_score, source_id, q (Volltext). Returns paginated matches |
| `PATCH /api/jobs/matches/<id>` | Body: `{status: "seen"\|"dismissed"}` |
| `POST /api/jobs/matches/<id>/import` | Erstellt Bewerbung mit Match-Daten als Notiz, returns Bewerbungs-ID |

**Quellen-Verwaltung (User-JWT-geschützt):**
| Methode + Path | Zweck |
|---|---|
| `GET /api/jobs/sources` | Eigene + globale Quellen |
| `POST /api/jobs/sources` | Eigene Quelle anlegen |
| `PATCH /api/jobs/sources/<id>` | Editieren (nur eigene) |
| `DELETE /api/jobs/sources/<id>` | Löschen (nur eigene) |
| `POST /api/jobs/sources/<id>/test-crawl` | Manueller Test |

**AI-Credentials (User-JWT-geschützt):**
| Methode + Path | Zweck |
|---|---|
| `GET /api/ai-credentials` | Status-Liste, Key maskiert |
| `POST /api/ai-credentials` | Anlegen |
| `PATCH /api/ai-credentials/<id>` | Editieren |
| `DELETE /api/ai-credentials/<id>` | Entfernen |
| `POST /api/ai-credentials/<id>/test` | Verbindungstest |

**Cron (Cron-Token-geschützt):**
| Methode + Path | Zweck |
|---|---|
| `POST /api/jobs/crawl-source` | Stage 1 |
| `POST /api/jobs/prefilter` | Stage 2 |
| `POST /api/jobs/claude-match` | Stage 3 |
| `POST /api/jobs/notify` | Stage 4 |
| `POST /api/jobs/cleanup` | Stage 5 |

---

## 7. Error Handling

| Fehler | Verhalten |
|---|---|
| Quelle: HTTP-Error / Timeout | `last_error` setzen, `consecutive_failures += 1` |
| Quelle: ungültiges Format | Parse-Error in `last_error`, kein Auto-Disable (User entscheidet) |
| Quelle: 5× Fehler in Folge | Auto-Disable + Notification an Owner |
| Claude: Timeout / Rate-Limit | Job bleibt mit `match_score=NULL`, nächster Tick versucht erneut |
| Claude: ungültige JSON-Antwort | 1× Retry mit strengerem Prompt, sonst `match_score=0` |
| User: keine AI-Credentials, kein Server-Fallback | Stage 3 überspringt User, log "skipped: no credentials" |
| User: Tagesbudget überschritten | Stage 3 überspringt User, log "skipped: budget exceeded" |
| Cron-Endpoint: > 25s Laufzeit | Hard-Stop, partielle Ergebnisse committen |
| Cron-Endpoint: ungültiger Token | 403 Forbidden |

---

## 8. Cost-Capping (mehrschichtig)

1. **Hard-Cap pro Tick:** Max N Claude-Calls (User-Setting, Default 5)
2. **Tagesbudget pro User:** Default 50 Cent/Tag, Stop wenn überschritten
3. **Monatsbudget pro Credentials:** User-konfiguriert, Stop wenn überschritten
4. **Pre-Filter-Schwellwert:** `prefilter_score < 30` → Auto-Verworfen, niemals Claude
5. **Dedup:** Jobs mit `(title, company)`-Kollision über Quellen → nur ein Match

---

## 9. Security

### 9.1 Cron-Endpoints
- Header `X-Cron-Token` mit env-var-Secret
- Rate-Limit: max 1× pro Minute pro IP
- Token rotierbar via env-update

### 9.2 SSRF-Schutz für RSS-Quellen
- URLs werden gegen Block-Liste validiert: `localhost`, `127.0.0.1`, `192.168.*`,
  `10.*`, `169.254.*`, `0.0.0.0`, IPv6-equivalents
- Bei Auflösung mehrerer IPs: alle prüfen
- Schutz analog zum bestehenden `imap_proxy`-Pattern

### 9.3 SSRF-Verhalten für Custom-AI-Endpoints
- localhost und private IPs **erlaubt** (gewünscht für Self-Hosted Ollama)
- URL pro User encrypted gespeichert → kein Cross-User-Angriff möglich
- Admin-Toggle `ALLOW_CUSTOM_ENDPOINTS` (default true) für Multi-User-Setups
- Test-Call Pflicht vor Aktivierung (`is_active=0` initial)
- 30s-Timeout für Custom-Endpoints

### 9.4 Multi-User-Isolation
- `job_matches` strikt user-scoped (alle Queries mit `user_id` filter)
- `raw_jobs` aus globalen Quellen geteilt, aber ohne user-spezifische Daten
- API-Keys pro User mit eigenem DEK encrypted (Envelope-Encryption)

### 9.5 JSON-Schema-Validierung
- `job_sources.config` strikt validiert pro `type`
- `user_ai_credentials.request_template` validiert auf erlaubte Mustache-Variablen
- Kein freies `eval()` oder Template-Engine-Sandbox-Escape

---

## 10. Testing

### 10.1 Test-Pyramide

**Unit-Tests** (pytest):
- `prefilter_scorer.py`: Keyword-Extraktion, Score-Berechnung, negative Filter
- `feed_parsers/{rss,adzuna,bundesagentur,arbeitnow}.py`: Snapshot-basierte Tests
- `ai_provider_factory.py`: Korrekter Provider basierend auf User-Credentials
- `custom_template_renderer.py`: Mustache-Rendering, JSONPath, Edge-Cases
- `crypto/credentials.py`: Encrypt/Decrypt mit User-DEK
- `match_budget.py`: Cost-Cap pro Tick, Tagesbudget, Monatsbudget
- `ssrf_guard.py`: Private-IP-Erkennung, Block-Verhalten

**Integration-Tests:**
- Vollständiger Pipeline-Lauf: globale Quelle → 2 User → Stage 1-4
- User dismissed Job → kein Re-Crawl-Match
- Quelle 5× Fehler → Auto-Disable + Notification
- User ohne Credentials, kein Server-Fallback → Stage 3 skip
- User mit Ollama-Mock → `cost=0`, `key_owner=custom_endpoint`
- Ungültiger API-Key → Test-Endpoint liefert 401, `is_active=false`
- Cron-Token fehlt → 403
- Tagesbudget überschritten mid-Tick → aktueller Job committet, weitere skipped
- Job-Import → `applications`-Eintrag mit Match-Notiz

**End-to-End** (selektiv, langsam):
- Echter Crawl gegen Bundesagentur-API mit Test-Query (max 1× pro CI-Run)
- Echter Anthropic-Match mit Mini-Job-Description

### 10.2 Mocking

- HTTP-Mocking via `responses` oder `httpx-mock`
- Claude-API über `MOCK_AI_RESPONSES` env-var
- Custom-Endpoint-Tests gegen Mini-Flask-Test-Server in Fixture
- `freezegun` für Crawl-Intervall-Tests

### 10.3 Coverage

- 80% Line-Coverage Standard für neue Module (analog Phase 1/2)
- 100% Branch-Coverage für: Crypto, Cost-Cap, SSRF-Guard, Provider-Factory

### 10.4 Manuelle QA-Checkliste

1. Quelle hinzufügen (alle 4 Typen) — erfolgreicher Test-Crawl
2. Match mit Score ≥ 80 → Push-Notification
3. "Übernehmen" → Bewerbung im Tracker mit Match-Daten
4. Eigenen Anthropic-Key hinterlegen → Cost in eigener Statistik
5. Ollama localhost als Custom-Endpoint → Match mit `cost=0`
6. Tagesbudget auf 1 Cent → Stage 3 stoppt nach erstem Match
7. Quelle disablen → kein Crawl mehr
8. Job dismissen → kein Wiedererscheinen
9. DB-Cleanup nach 60 Tagen

---

## 11. Out of Scope (Phase 2)

Bewusst nicht im initialen Scope, aber für später vorgesehen:

- **Auto-Apply-Drafts:** Claude generiert Anschreiben-Drafts für Top-Matches auf Basis
  von CV + Stellenbeschreibung. User reviewed, schickt manuell ab.
- **Provider-Erweiterung:** OpenAI, Google Gemini als first-class Provider (statt nur via OpenAI-compat).
- **Cross-Source-Deduplizierung mit Embeddings:** Statt simpler `(title, company)`-Heuristik
  semantische Job-Ähnlichkeit erkennen.
- **CV-Verbesserungs-Vorschläge:** Aus aggregierten `missing_skills` über alle Matches
  Skill-Gaps identifizieren und CV-Update vorschlagen.
- **Aktive Job-Sites mit Web-Scraping:** Xing, Glassdoor — bewusst aufgrund ToS-Risiken
  und Wartungsaufwand verschoben.

---

## 12. Migration & Rollout

1. **DB-Migration:** Alembic-Migration für 4 neue Tabellen + Erweiterung `api_calls`.
2. **System-Quellen-Seed:** Migrations-Skript erstellt 3-5 globale Default-Quellen
   (Bundesagentur "Frontend", Bundesagentur "Backend", Arbeitnow "Remote DACH").
3. **Backend-Deploy:** Flask-App mit neuen Endpoints, env-vars `JOB_CRON_TOKEN`,
   `ALLOW_SERVER_FALLBACK_KEY`, `ALLOW_CUSTOM_ENDPOINTS`.
4. **Cron-Setup:** cron-job.org-Account anlegen, 5 Cron-Jobs mit Token konfigurieren.
5. **Frontend-Deploy:** Neuer Tab + Settings-Sektionen.
6. **Routing-Service-Refactor:** Bestehender Placeholder umgebaut auf
   `AIProviderFactory` (User-bezogen).
7. **Soak-Test:** 1 Woche mit eigenem Account beobachten, Cost-Tracking verifizieren.
8. **Doku:** README-Update + neue `docs/FEATURES/JOB_DISCOVERY.md`.

---

## 13. Erfolgskriterien

- ✅ Mind. 3 globale Quellen liefern täglich neue Jobs
- ✅ Pre-Filter reduziert Claude-Calls um ≥ 80%
- ✅ Mind. 1 Match-Score ≥ 80 pro Tag (bei aktivem User)
- ✅ Cost pro User ≤ 50 Cent/Tag (Default-Budget eingehalten)
- ✅ Push-Notifications kommen innerhalb 90 Min nach Crawl-Erfassung beim User an
  (Pipeline-Worst-Case: crawl 15 + prefilter 15 + claude 30 + notify 30)
- ✅ Custom-Endpoint (Ollama) funktioniert mit `cost=0`
- ✅ 80% Line-Coverage / 100% Branch-Coverage auf kritischen Pfaden
