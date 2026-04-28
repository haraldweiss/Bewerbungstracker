# Job-Discovery & Auto-Matching (Phase A: Backend)

## Konzept

Automatische Stellensuche aus konfigurierbaren Quellen mit lokalem Pre-Filter
und Claude-basiertem Matching gegen den hinterlegten Lebenslauf.

## Setup

### 1. DB-Migration

```bash
python scripts/migrate_job_discovery.py
python scripts/seed_job_sources.py
```

### 2. ENV-Variablen

```bash
JOB_CRON_TOKEN=<random-secret-32+chars>
ANTHROPIC_API_KEY=<dein-key>     # Phase A: Server-Key. Phase B: BYOK.
CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001
```

### 3. User aktivieren

User muss `job_discovery_enabled=true` setzen und einen CV (cv_data_json) hinterlegen.
(Frontend dafür kommt in Phase C — aktuell via direkter SQL-Update oder via Profile-API.)

### 4. Cron-Setup (cron-job.org o.ä.)

```
*/15 * * * *      POST https://<deine-domain>/api/jobs/crawl-source
*/15 * * * *      POST https://<deine-domain>/api/jobs/prefilter
*/30 * * * *      POST https://<deine-domain>/api/jobs/claude-match
*/30 * * * *      POST https://<deine-domain>/api/jobs/notify
0 3 * * *         POST https://<deine-domain>/api/jobs/cleanup
```

Header bei jedem Aufruf: `X-Cron-Token: <JOB_CRON_TOKEN>`

## Manuelle Tests

| Schritt | Erwartung |
|---|---|
| `POST /api/jobs/crawl-source` mit Token | 200, neue Jobs in `raw_jobs` |
| `POST /api/jobs/prefilter` | 200, `match.prefilter_score` gesetzt |
| `POST /api/jobs/claude-match` | 200, Top-N Matches mit `match_score` + `match_reasoning` |
| `POST /api/jobs/notify` | 200, Push-Notification (Phase A: Stub mit Logging) für Score ≥ 80 |
| `GET /api/jobs/matches?min_score=70` | Liste mit JWT |
| `POST /api/jobs/matches/<id>/import` | erstellt Bewerbung mit Match-Notiz |

## Limits / Cost-Capping

- Pro User max `job_claude_budget_per_tick` Claude-Calls (Default 5)
- Pro User max `job_daily_budget_cents` Kosten/Tag (Default 50 Cent)
- Quelle 5× Fehler in Folge → Auto-Disable
- RawJobs > 60 Tage ohne aktive Matches → archiviert

## Architektur

5 Cron-Stages mit kleinen, schnellen Endpoints (für IONOS-Shared-Hosting kompatibel):

1. **crawl-source** — wählt eine fällige Quelle, lädt Roh-Jobs in DB
2. **prefilter** — lokales Keyword-Scoring gegen User-CV (kostenlos)
3. **claude-match** — Top-N Jobs durch Claude bewerten lassen
4. **notify** — Push-Notifications für Hi-Score-Matches
5. **cleanup** — täglicher Job-Archivierungs-Run

## Source-Adapter

| Type | Quelle | Auth |
|---|---|---|
| `rss` | Beliebiger RSS/Atom-Feed | keine |
| `adzuna` | Adzuna API (https://developer.adzuna.com) | app_id + app_key |
| `bundesagentur` | Bundesagentur Jobsuche-API (offiziell, kostenlos) | Public-Key inline |
| `arbeitnow` | Arbeitnow API (https://www.arbeitnow.com) | keine |

Konfiguration pro Quelle in `job_sources.config` (JSON, type-spezifisch).

## REST-API (User-facing)

| Endpoint | Zweck |
|---|---|
| `GET /api/jobs/sources` | Eigene + globale Quellen |
| `POST /api/jobs/sources` | Eigene Quelle anlegen (mit SSRF-Validation für RSS) |
| `PATCH /api/jobs/sources/<id>` | Eigene Quelle editieren |
| `DELETE /api/jobs/sources/<id>` | Eigene Quelle löschen |
| `POST /api/jobs/sources/<id>/test-crawl` | Manueller Test-Crawl |
| `GET /api/jobs/matches` | Match-Liste mit Filtern (min_score, status, source_id, q) |
| `PATCH /api/jobs/matches/<id>` | Status ändern (seen/dismissed/new) |
| `POST /api/jobs/matches/<id>/import` | Als Bewerbung übernehmen |

## Phase B (geplant)

BYOK — User können eigene API-Keys hinterlegen (Anthropic, Ollama, OpenRouter), Cost
fällt dann beim User-Account an. Siehe `docs/superpowers/plans/2026-04-28-job-discovery-phase-b-byok.md`.

## Phase C (geplant)

Frontend-Integration — Job-Vorschläge-Tab + Settings-UIs für Quellen und KI-Konfiguration.
