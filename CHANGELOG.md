# Changelog — Bewerbungstracker

Historische Session-Handoffs, ursprünglich in `AGENTS.md §7`. Ab 2026-06-19 werden neue Einträge hier statt in AGENTS.md dokumentiert.

### 2026-06-23 — URL-Normalisierung beim Speichern von RawJobs + Deploy (durch pi/Claude Code)

**Problem:** Der "Original"-Link bei Job-Vorschlägen führte oft auf tote Seiten (HTTP 500) — Tracking-Links von StepStone/LinkedIn/Indeed waren abgelaufen.

**Lösung:** Neue Funktion  in  ohne Netzwerk-Calls:
  - **LinkedIn:**  → 
  - **StepStone:** Magic-Link → öffentliche Anzeigen-URL aus 
  - **Alle:** Tracking-Parameter entfernt (, , , …)
  - Fehlschlag sicher: unbekanntes Format → Original-URL bleibt erhalten

**Geänderte Dateien (3):**
  - : +  (synthetische Normalisierung)
  - :  → 
  - :  beim RawJob-Erzeugen

**Deployed:** Image  auf oracle-vm, alle 5 Container recreatet, Funktion verifiziert.
**Git:**  auf , gepusht.

### 2026-06-23 — Prod-Fix: StepStone-Tracking-URL + fehlende Company bei Match #3640 (durch pi/Claude Code)

**Symptom:** Letzter Job-Vorschlag (Match #3640 / RawJob #3209 — "IT Security Operation Koordinator (m/w/d)") hatte eine StepStone-Tracking-URL (`click.stepstone.de/f/a/...`) statt der echten Stellenanzeige. Company-Feld war leer (`None`). Beim Öffnen/Import kam HTTP 500.

**Fix (Production-DB auf Oracle VM, kein Code-Commit):**
- `RawJob #3209.url` aktualisiert: `click.stepstone.de/f/a/...` → `https://www.stepstone.de/stellenangebote--IT-Security-Operation-Koordinator-m-w-d-Neuss-Pierburg-GmbH--13966783-inline.html`
- `RawJob #3209.company` gesetzt: `None` → `Pierburg GmbH`

**Verifikation:** Match #3640: status=new, score=75.0, Company=Pierburg GmbH, URL=stepstone.de/stellenangebote--IT-Security-...

### 2026-06-05 — Quick-Reasons-UI Phase 1: Tasks 4-9 implementiert (durch opencode)
- **Task 4** ✅ — `services/job_matching/quick_actions.py` + 11 Unit-Tests. `apply_quick_action()` mit 4 Aktionen (company_rejected, already_applied, job_unavailable, wrong_job_type). Idempotent, ProtectedStatuses gegen Downgrade. QuickActionError -> 400.
- **Task 5** ✅ — PATCH `/api/jobs/matches/<id>` versteht `quick_action` + `job_type`. Setzt status='dismissed' implizit, ignoriert user-feedback_text bei quick_action. 6 Integration-Tests.
- **Task 6** ✅ — `/api/profile/job-discovery` GET+PATCH für `job_type_blacklist`. Validierung via `VALID_JOB_TYPES`. 6 Tests.
- **Task 7** ✅ — Frontend: 4 Quick-Action-Buttons im Dismiss-Modal, AI-Reasons in `<details>` zugeklappt. Mobile-Responsive.
- **Task 8** ✅ — Frontend: 3 Job-Typ-Checkboxes im Profil-Tab. Load/Save via loadJobDiscoveryFilters/saveJobDiscoveryFilters.
- **Task 9** ✅ — `pytest tests/services/ tests/api/` → 298 passed, 0 failed. Keine Regression.
- Deployed to IONOS VPS.
- **Nächste Schritte:** —
### 2026-06-05 — Weekly Summary mit dynamischen Inhalten
- **email_service.py:** `check_and_send_summary()` erzeugt jetzt eine HTML-E-Mail mit:
  - Gesamtstatistik (Bewerbungen, Status-Verteilung)
  - Wochen-Werte (neue, Absagen, Gespräche, Zusagen)
  - Neue/Vorworfene Job-Vorschläge
  - Letzte Aktivitäten (10 neueste Status-Änderungen)
  - Korrekter Link zur App (`APP_URL` statt `localhost:8080`)
- **DB-Pfad-Fix:** `_get_main_db_path()` parsed `sqlite:////abs/path` korrekt (fehlender führender `/`)
- **SMTP-Encryption-Fix:** Encryption-Key wird in Config persistiert, überlebt Container-Neustarts
- **email_config.db** liegt jetzt auf dem schreibbaren Volume (`/app/data/`)
- **SMTP-Konfiguration** aktualisiert (IONOS-Passwort neu gesetzt)
- Deployed to IONOS VPS (Container-Image neugebaut + Email-Service restarted)
### 2026-06-05 — Weekly Summary Fix: baked-in .env override root cause
- **Root Cause:** `docker-entrypoint.sh` sourced `/app/.env` nach Quadlet-Env-Init → baked-in `DATABASE_URL=sqlite:///bewerbungstracker.db` überschrieb Quadlets `sqlite:////app/data/instance/...`
- **Fix:** `.env` zu `.dockerignore` hinzugefügt + `/var/www/bewerbungen/.env` auf VPS gelöscht + Image neugebaut + alle Container restarted
- Alle Container haben jetzt korrekte `DATABASE_URL` im Prozess-Env (via `/proc/<pid>/environ` verifiziert)
- **Lehre:** Baked-in `.env` im Image ist gefährlich wenn es env-Vars setzt die Quadlet vorgibt. `docker-entrypoint.sh` sollte entweder kein `.env` sourcen oder nur für lokale Dev-Umgebung.
### 2026-06-05 — Auto-Reject-Analyse + Quick-Win-Fixes
- **Analyse Prod-DB:** 1.786/1.891 JobMatches dismissed (94 %), aber `company_already_rejected` traf nur 7×. Den 138 manuellen User-Texten standen 12+ Fälle „X hat schon abgesagt" gegenüber → zwei Lücken identifiziert: (a) Suffix-Mismatch („Signal Iduna" vs. „Signal Iduna Group AG"), (b) Status `ghosting` nicht in Reject-Set.
- **Fix 1 — Company-Normalisierung:** Neuer Helper `services/email_import_utils.py::normalize_company()` (Rechtsformen-Strip GmbH/AG/KG/SE/Ltd/Inc + „Group/Holding/International" + Trailing-Klammern). `get_rejected_companies_lower()` liefert normalisiertes Set. Alle 4 Vergleichsstellen umgestellt (cron_prefilter, email_import, cron_indeed_email_import, api/jobs_user). Inline-Duplikat in cron_prefilter entfernt.
- **Fix 2 — Status-Set:** `'ghosting'` zum Reject-Set ergänzt (`_REJECTING_STATUSES`). Konsistent mit `feedback_bridge.py::_TERMINAL_STATES`-Mapping ghosting → rejected_after_apply. Prod-DB: 9 ghosting-Apps werden ab jetzt für Auto-Reject genutzt.
- **AGENTS.md §3.6:** Neue Regel — `/loop` bei Polling/wiederkehrenden Tasks (Claude Code) statt Sleep-Schleifen. opencode-Pendant aktuell unbekannt.
- **Tests:** 17 neue Tests (`tests/services/test_email_import_utils.py`) — Normalisierung + DB-Integration (Status-Set, Window, soft-deleted). 17/17 passed. Breiter Sweep `tests/services/ tests/api/` → 490 passed (7 Fehler durch lokal fehlendes jsonschema, unabhängig).
- NICHT deployed to IONOS. Backwards-kompatibel — alte Daten bleiben in DB, neuer Prefilter greift ab Deploy.

### 2026-06-06 — opencode: Body-Phrasen-Scan + Keyword-Blacklist + Fuzzy-Dup + Postfix-Mails
Alle Backlog-Items aus dem vorherigen Handoff wurden in dieser Session implementiert und deployed:
- **Body-Phrasen-Scan:** `scan_body_reject()` in `email_import_utils.py` erkennt 13 Phrasen ("werden keine Bewerbungen mehr angenommen", "Bewerbungsfrist abgelaufen" etc.) → auto-dismiss mit `feedback_text='body_phrase_rejected'`
- **User-Keyword-Blacklist:** Neue DB-Spalte `job_keyword_blacklist` + API (GET/PATCH `/profile/job-discovery/filters`) + Frontend-Textarea + Cron-Check
- **Cross-Portal-Fuzzy-Duplicate:** `SequenceMatcher` (threshold 0.85) für Titel-Ähnlichkeit + normalisierte Company über verschiedene Portale hinweg
- Image neugebaut + alle 5 Container restarted ✓

### 2026-06-01 — README-Links gefixt, .serena/ ignoriert, AGENTS-Hash korrigiert
- README English: fehlende Job-Discovery/DEPLOYMENT.md/Technology Bullets ergänzt
- README: 4 broken Deployment-Links korrigiert (`docs/DEPLOYMENT/DEPLOYMENT_*.md` → `DEPLOYMENT_*.md` im Root bzw. `docs/DEPLOYMENT_PRODUCTION.md`)
- AGENTS.md: Commit-Hash `a573167` → `816cd7c` korrigiert
- `.gitignore`: `.serena/` hinzugefügt
- Getestet: kein Code angefasst, README-Links manuell verifiziert
- NICHT deployed to IONOS

### 2026-06-01 — Containerisierung deployed + Fixes (3 Runden)
1. **Erster Deploy:** Alle 5 Container auf VPS, App HTTP 200 ✓
2. **Bugfix Runde 1:** `Exec` überschreibt CMD, nicht ENTRYPOINT → nur Rollenname
3. **Bugfix Runde 2:** `.env` überschrieb `AI_PROVIDER_SERVICE_URL` mit `127.0.0.1` → Container-Env via Quadlet ging verloren. Fix: `.env` korrigiert + Image neugebaut
4. **Bugfix Runde 3:** `host.containers.internal` resolvt auf `bewerbungen-net` Gateway (10.89.1.1), nicht zum `podman`-Bridge (10.88.0.1) wo ai-provider lauscht. Fix: `http://10.88.0.1:8767`
5. **SELinux:** `:Z` → `:z` für Shared-Volume-Zugriff (app+worker+imap+email+cron)
6. **Netzwerk:** Custom `bewerbungen-net` damit Container-DNS funktioniert
7. **supercronic PID-1 Bug:** Kein `exec` in cron-Rolle

### 2026-06-01 — Email/IMAP-Container: BIND_HOST-Fix
- IMAP-Proxy und Email-Service banden an `127.0.0.1` → nach DNAT (host→container) kamen Pakete auf eth0 an, Service hörte nur auf lo → Connection Refused
- Fix: `BIND_HOST=0.0.0.0` per env-var, überschreibt config.json + Default
- `imap_proxy.py`: zusätzlich `os.getenv('BIND_HOST')` in load_config → gewinnt immer
- `email_service.py`: `HOST = os.getenv('BIND_HOST', '127.0.0.1')`
- GETESTET: IMAP 400, Email 404 (korrekt — Services laufen und antworten)
- DEPLOYED to IONOS VPS

### 2026-06-01 — Containerisierung: Dockerfile + 5 Podman Quadlets
- Dockerfile: single-stage python:3.12-slim, multi-role (app/worker/imap-proxy/email-service/cron)
- 5 Quadlet `.container` files passend zum ai-provider-service-Pattern
- Cron-Container mit supercronic + crontab (alle 5 Stages + indeed-email-import + backup)
- `.dockerignore` aktualisiert (imap_proxy/email_service nicht mehr exkludiert)
- `deploy/container/setup-vps.sh` für Einmal-Setup auf dem VPS
- GETESTET: `podman build` + alle 5 Container laufen auf dem VPS, App antwortet HTTP 200, API HTTP 401 (korrekt)
- DEPLOYED TO IONOS VPS (Podman Quadlets, Rocky Linux 9.8)
- **Wichtig bei Podman-Updates:** supercronic hat einen PID-1-Bug — docker-entrypoint.sh verwendet nicht `exec` für die cron-Rolle

### 2026-06-02 — Ollama-Modelle + opencode.ai als zentraler Provider
- **Bug: AI Provider zeigte "Keine Models verfügbar"** — 3 Ursachen:
  1. App-Container auf `bewerbungen-net` (10.89.x.x), AI-Provider hatte nur Pasta-Netzwerk → unterschiedliche Netze, `10.88.0.1:8767` unerreichbar
  2. `OLLAMA_URL=http://host.containers.internal:11434` → DNS löst auf dem Host/Container nicht auf
  3. Container-Image hatte baked-in `.env` mit veralteter `AI_PROVIDER_SERVICE_URL` → Eintrypoint `source .env` überschrieb `EnvironmentFile`
- Fixes (VPS, rootless Podman):
  - `Network=bewerbungen-net` zum ai-provider Quadlet hinzugefügt
  - `AI_PROVIDER_SERVICE_URL=http://ai-provider:8767` (DNS auf Bridge)
  - `OLLAMA_URL=http://10.89.0.1:11434` (Host-Bridge-IP, SSH-Tunnel auf `0.0.0.0`)
  - Volume-Mount `/etc/bewerbungen/bewerbungen.env:/app/.env:Z` + chmod 644
- **Feature: opencode.ai als zentraler Provider** (`api/providers.py`, `index.html`):
  - `'opencode'` in `VALID_PROVIDERS` + `USER_PROVIDERS`
  - Config-UI mit API-Key + optionalem Endpoint im Frontend
  - Backup-KI (Fallback) zeigt opencode automatisch (filtert `configured=true`)
- **ai-provider-service (Image neugebaut):**
  - `config.py`: `OPENCODE_API_KEY` env var
  - `opencode.py`: Fallback auf `Config.OPENCODE_API_KEY`
   - Registry: `system: True`, `requires: []`, `UNGATED_PROVIDERS+=opencode`
- **Free-Model-Gating** (`opencode.py`, `dispatcher.py`):
  - `FREE_MODELS = frozenset({'deepseek-v4-flash-free'})`
  - `_require_paid()`: ohne eigenen User-Key sind nur Free-Modelle nutzbar
  - Paid-Modelle → ValueError "erfordert eigenen opencode.ai API-Key"
  - ValueError propagiert direkt → kein Fallback/Queue (fix in `dispatcher.py`)
- **Daily-Limit für Free-Modelle** (`config.py`, `dispatcher.py`):
  - `FREE_MODEL_DAILY_LIMIT=500` (Default, via env konfigurierbar)
  - `FREE_MODEL_ADMIN_RESERVE=100` (davon reserviert für Admin `harald`)
  - `FREE_MODEL_ADMIN_UID=harald`
  - Zählt via `UsageEvent`-DB (nur `status=success`)
  - Nicht-Admin-User werden bei `limit - reserve` gestoppt
  - Budget-Überschreitung = RuntimeError (kein ValueError) → löst Fallback/Queue aus
- **Modell-Liste gecached** (`opencode.py`): `get_models()` schreibt `.models_cache_opencode.json` mit 24h TTL → einmal täglich aktualisiert
- **Hotfix** (`api/profile.py:234`): `VALID_PROVIDERS` hatte eigenes Set ohne `opencode` → `cover_letter: unbekannter Provider opencode` beim Speichern von Pro-Task-Overrides
- Deployed to IONOS VPS (beide Images neugebaut + Container restarted)
- Getestet: App→AI-Provider kommuniziert, Ollama 15 Models, Opencode 45 Models (deepseek-v4-flash etc.)

### 2026-06-01 — Learned-Patterns-Table zeigt Custom-Plattformen
- Bug: `loadLearnedPatterns()` in `index.html:4089` hatte Plattformen hardcodiert auf `['indeed', 'linkedin', 'xing']` — Patterns für Custom-Plattformen (via PlatformProfileRow) wurden nie angezeigt
- Fix: iteriert jetzt über alle Einträge der API-Antwort + Built-in-Defaults, sortiert nach Name
- Feature: Training-Toasts zeigen jetzt die Quellen-Plattform an (z.B. `🧠 STEPSTONE: 30%…`)
- Nur JS-Änderungen in `index.html` (35 insertions, 13 deletions)
- Getestet: `pytest tests/api/test_pattern_learner_api.py` (12/12 passed)
- NICHT deployed to IONOS

### 2026-06-06 — ai-provider-service Memory-Layer verfügbar (kein Code-Change hier)

**Was sich ändert:** Der Gateway (`ai-provider-service`) stellt seit gestern (PR [#14](https://github.com/haraldweiss/ai-provider-service/pull/14) + Phase 1.5/2, deployed auf VPS) eine Markdown-Memory-Schicht bereit. **Bewerbungstracker schreibt aktuell NICHT** dorthin — der Eintrag ist nur informativ, damit künftige Erweiterungen wissen dass das da ist.

**Was Bewerbungstracker tun könnte** (wenn Bedarf entsteht):
- `POST https://bewerbungen.wolfinisoftware.de/ai-provider/memory/events` mit `{"user_id":"<...>", "app":"bewerbungstracker", "event_type":"application_created", "payload":{"company":"...", "position":"...", "platform":"..."}}` bei jedem neu erkannten Job
- `POST .../memory/notes` mit freien Markdown-Notizen wenn semi-strukturiert reicht
- `GET .../memory/search?q=<keyword>&user_id=<...>` zur FTS5-Suche über vergangene Jobs/Notizen (porter+unicode61)
- Vault per WebDAV unter `/ai-provider/memory/dav/?user_id=<...>` direkt in Obsidian öffnen

**Auth:** Bearer-Token (gleicher `SERVICE_TOKEN` den die App schon fürs Gateway nutzt). User-Scoping ist hart — Apps können nur auf den eigenen `user_id` schreiben außer der Token ist Admin.

**Rate-Limits seit Phase 1.5:** 60 POST/min, 120 GET/min, 5 vault-exports/min pro User — bei Bulk-Import einfach drosseln.

**Caveat:** Audit läuft automatisch beim Gateway (jeder `/chat`-Call landet in `memory_notes` mit `kind=audit`, `app=<X-Origin-App>`). Bewerbungstracker schickt schon `X-Origin-App: bewerbungstracker` — das taucht also als App-Label im audit-Vault auf. Kein Action erforderlich, nur wissen dass es so ist.

**Sibling-Repo:** [`ai-provider-service` AGENTS.md §7](https://github.com/haraldweiss/ai-provider-service/blob/main/AGENTS.md) hat den vollständigen Status. Spec/Plan: `docs/superpowers/{specs,plans}/2026-06-05-markdown-memory-*.md` im Gateway-Repo.

### 2026-06-12 — Fix: Docker-Volume-Split zwischen APP und WORKER (durch opencode)

**Root Cause:** APP- und WORKER-Container nutzten unterschiedliche Docker-Volumes:
- APP: `bewerbungen_data` (underscore, neu seit 06:31 UTC)
- WORKER: `bewerbungen-data` (hyphen, alt)
- EMAIL-SERVICE + IMAP-PROXY: `/opt/bewerbungen-data` (Host-Bind-Mount, dritte Kopie)
- CRON: kein Volume-Mount (benign, curl-only)

**Auswirkung:** Seit APP-Neustart ~06:31 UTC waren neu erstellte Tasks (6 Stück) für den WORKER unsichtbar → keine Pipeline-Verarbeitung (crawl/prefilter/claude-match/notify) seit 06:27. Email-Import lief noch bis 06:25-06:27 weil da alle Container dasselbe Volume teilten.

**Fix:**
1. `docker stop/rm bewerbungen-worker` → neuer Container mit `-v bewerbungen_data:/app/data:z`
2. `docker stop/rm bewerbungen-email-service` → neuer Container mit `-v bewerbungen_data:/app/data:z`
3. `docker stop/rm bewerbungen-imap-proxy` → neuer Container mit `-v bewerbungen_data:/app/data:z`
4. Altes Volume `bewerbungen-data` (hyphen) gelöscht
5. `deploy/container/crontab`: `Authorization: Bearer` → `X-Cron-Token` (Header matcht `require_cron_token`)

**Verifikation:** 2233 Tasks done, 0 queued, 0 running. Worker verarbeitet wieder.

**⚠ Lehre für künftige Container-Neustarts:** Bei `docker run` und Neu-Erzeugung von Containern aufpassen dass Volume-Namen identisch sind (keine Tippfehler underscore vs hyphen).

**Dokumentation:** `deploy/container/setup-oracle-vm.sh` neu erstellt — Single-Source-of-Truth für alle `docker run`-Befehle auf der Oracle VM. Commands: `setup`, `start`, `stop`, `restart`, `rebuild`, `status`, `volume-info`, `migrate`, `logs`.

### 2026-06-12 — Frontend: Import-Funktionen speicherten nur in localStorage → Refactored (durch opencode, Commit `a584dd4`)

**Root Cause:** 7 manuelle Import-Funktionen (`importScriptEmail`, `importAllScriptEmails`, `importSingleImapEmail`, `importEmlItem`, `importAllEmlEmails`, `importTextItem`, `importAllTextEmails`) in `index.html` haben Bewerbungen nur in `state.bewerbungen` + `localStorage` geschrieben, **nicht** per API auf dem Server.

**Auswirkung:** `loadFromStorage()` lädt Bewerbungen primär vom Server (`GET /api/applications`). Beim nächsten Seitenaufruf überschreibt der Server-Response den lokalen State — die manuell importierte Bewerbung war weg.

`importImapEmail` (der neuere IMAP-Pfad) machte es bereits korrekt mit `POST /api/applications` + `_mapBackendToDB()`.

**Refactoring:**
- Neue gemeinsame Funktion `_importSingleApplication(parsed, notes, sourceOverride)` — einmalige API-Logik für alle 7 Konsumenten
- `apiData` aus `parseEmailToApplication()`-Feldern gebaut (backend-Feldnamen: `company`, `position`, `status`, `applied_date`, …)
- `POST /api/applications` via `fetchAPI()`
- Response via `_mapBackendToDB(created)` in lokalen State eingefügt
- `importAll*`-Schleifen von `forEach` (async ohne await) auf `for…of` + `await` umgestellt
- Jeder Konsument ruft `_importSingleApplication` + `renderAll()` + source-spezifisches Rendering

**Betroffene Datei:** `index.html` (ca. +70 Zeilen netto).
**Deployed auf Oracle VM:** `index.html` per `docker cp` ins Container, Commit `a584dd4`, gepusht zu `github.com:haraldweiss/Bewerbungstracker`.

### 2026-06-12 — Fix: `</script>` im Template-Literal + leere Position bei Import (durch opencode)

**Problem 1:** `index.html:8080` enthielt `</script>` innerhalb eines JavaScript-Template-Literals (`...\`...<script src="..."></script>...\``). Der HTML-Parser beendete den äußeren `<script>`-Block vorzeitig → alle Funktionen danach (inkl. `_importSingleApplication`) wurden nie definiert → Seite zeigte JavaScript-Roh-Text.

**Fix:** `</script>` → `<\/script>` im Template-Literal (JS-escaped, HTML-Parser sieht es nicht).

**Problem 2:** Bei Absage-Mails wie "Deine Bewerbung / ControlExpert" extrahierte `parseEmailToApplication()` keine Position aus dem Subject → `POST /api/applications` gab 400 ("position required").

**Fix:** `_importSingleApplication` setzt `'(Keine Position)'` als Fallback wenn `parsed.position` leer ist.
**Deployed auf Oracle VM + gepusht (Commit `cd76de7`).**

### 2026-06-12 — Fix: BIND_HOST + Port-Publishing für email-service und imap-proxy (durch opencode)

**Root Cause:** Bei der Container-Neuerstellung (Volume-Fix) wurden `-p 127.0.0.1:8765:8765` / `-p 127.0.0.1:8766:8766` vergessen. Zudem fehlte `-e BIND_HOST=0.0.0.0`, wodurch die Dienste nur container-intern auf `127.0.0.1` lauschten.

**Auswirkung:** Apache auf dem Host konnte die Dienste nicht über `127.0.0.1:8765/8766` erreichen → "Email Service nicht erreichbar" im Frontend.

**Fix:**
- `-p 127.0.0.1:8765:8765` und `-p 127.0.0.1:8766:8766` zu `docker run` hinzugefügt
- `-e BIND_HOST=0.0.0.0` gesetzt (lauscht auf allen Interfaces)
- `setup-oracle-vm.sh` aktualisiert (Commit `1b96543`)

### 2026-06-12 — Fix: Service Worker Cache (v60→v61) + ai-provider unhealthy (durch opencode)

- **Service Worker:** `service-worker.js` cache auf v61 gebumpt, da die alte v60 die `index.html` mit dem Import-Fix cached hatte → Browser zeigte alte Version ohne API-Call.
- **ai-provider:** `OLLAMA_URLS` enthielt toten Endpoint `http://172.17.0.1:11434` → health-check hing → Provider als "unhealthy" markiert. Fix: nur noch `http://172.17.0.1:11435` (aktiver Ollama-Port). Container neugebaut mit korrigierten Env-Vars.

### 2026-06-12 — Browser-Use lokal aufgesetzt (MCP-Tool) (durch opencode)

**Problem:** `browser-use-mcp.py` lief via SSH auf Oracle VM, wo Ollama nur CPU hat (75s+ pro LLM-Call) → MCP-Timeout (30s).

**Fix:**
- Lokales venv (`/tmp/browser-use-env`) mit Playwright + browser-use installiert
- `browser-use-mcp.py` rewritten: läuft jetzt lokal mit GPU-Playwright (kein Ollama nötig für page-titles/content)
- Fallback: wenn lokal fehlschlägt → SSH mit opencode free über ai-provider
- Config in `~/.config/opencode/opencode.jsonc` aktualisiert

**Verifikation:** Seite geladen, Title + Buttons extrahiert in <3s (GPU).
**Nicht committed** — betrifft nur lokale MCP-Config + venv.

### 2026-06-12 — ÜBERGABE an opencode: technische Fehlbewertungen neu bewerten + Ollama-Fallback (Plan fertig, NICHT implementiert)

**Auftrag (User):** Verworfene JobMatches, deren KI-Begründung einen technischen Fehler zeigt ("Tunnel offline" / "ungültiges JSON von Provider"), sollen automatisch neu bewertet werden. Erweiterung: wenn das Free-Modell versagt, auf ein lokales **Ollama-Modell** zurückfallen.

**Was diese Session (Claude Code) fertig hat:**
- **Prod-Analyse** (Oracle VM, s.u.): 9 dismissed Matches mit `match_reasoning = "Bewertung fehlgeschlagen (ungültiges JSON von Provider)."`, Score 0, alle User `harald`. Ursache: Free-Modell `opencode/deepseek-v4-flash-free` liefert HTTP 200 + Prosa statt JSON; Backup-Provider war **dasselbe** Free-Modell → effektiv kein Fallback.
- **Spec** committed `765dec9` → `docs/superpowers/specs/2026-06-12-technical-failure-reeval-design.md`
- **Plan** committed `def16f1` → `docs/superpowers/plans/2026-06-12-technical-failure-reeval.md` (9 Tasks, TDD, vollständiger Code in jedem Step — opencode kann Task-für-Task abarbeiten).
- **Manuelle Prod-Daten-Änderung bereits gemacht:** 8 der 9 Matches auf `status='new'` zurückgesetzt (Score/Reasoning/notified geleert). IDs: `2451,2453,2473,2502,2554,2721,3057,3060`. Backup-JSON auf der VM: `/tmp/match_reeval_backup_20260612_041847.json`. Der 9. (Match `3053`) hat echtes `feedback_reasons=["wrong_seniority"]` → bewusst NICHT angefasst. **Diese 8 brauchen `eval_attempts=1`** (Plan Task 9 Step 4), sonst greift der neue Retry-Zweig sie nicht (prefilter < 50, Reasoning schon geleert).

**Was lokal NICHT committed / offen ist:** Nichts uncommitted im Tree (nur Spec+Plan, beide committed). **Code ist noch NICHT implementiert** — opencode startet bei Plan-Task 1.

**Wo genau weitermachen:** Plan Task 1 → Task 9 der Reihe nach. Branch `claude/hungry-euclid-56f7fd` (Worktree). NICHT zu `master` gemergt, NICHT deployed.

**⚠ Routing-Hinweis (§2/§3.2):** Der Kern liegt in `services/job_matching/claude_utils.py` = Claude-Code-Care-Gebiet (Anthropic/Cost-Tracking). opencode: `cost_tracker.record_call(...)`-Logik im Erfolgsfall **exakt** erhalten, **keinen** `anthropic.Anthropic(...)` direkt instanziieren (§3.2), AI-Calls nur über `ai_provider_client`. Bei Unsicherheit den Care-Pfad zurück an Claude Code geben.

**⚠ Infrastruktur-Korrektur:** Prod läuft auf der **Oracle VM**, nicht IONOS. Zugang: `ssh oracle-vm` (User `opc`), Container via **docker** (nicht podman). DB im Container `bewerbungen-app`: `/app/data/bewerbungstracker.db` (WAL, `busy_timeout` nutzen). Cron-Container `bewerbungen-cron` hat `JOB_CRON_TOKEN`+`APP_INTERNAL_URL` für manuelle Stage-Trigger. (Memory/AGENTS referenzieren noch IONOS — veraltet für dieses Deployment.)

**⚠ Provider-Status zum Handoff-Zeitpunkt:** Ollama-Tunnel **down** (`404 … http://172.17.0.1:11435/api/chat`), `opencode` + `claude` gesund. Der Smoke-Test (Plan Task 9 Step 5) braucht einen gesunden Provider — Ollama-Fallback erst sinnvoll testbar, wenn der Tunnel wieder steht.

**Verifikation vor Deploy:** `pytest tests/services/ tests/api/` grün; Alembic-Migration `c1d2e3f4a5b6` (down_revision `b0c1d2e3f4a5` = aktueller HEAD). Env-Defaults: `MATCH_FALLBACK_ENABLED=true`, `MATCH_OLLAMA_FALLBACK_MODEL=gemma4:12b`, `MATCH_MAX_EVAL_ATTEMPTS=5`.

### 2026-06-12 — Implementierung technische Fehlbewertung-Neubewertung + Ollama-Fallback (durch opencode)

**Tasks 1–8 vollständig implementiert (Plan Tasks 1–8), Task 9 (Deploy) noch ausstehend.**

**Commits** (7, auf Branch `claude/hungry-euclid-56f7fd`):
1. `7f193bb` — feat: JobMatch.eval_attempts Spalte für technische Retry-Logik
2. `e9bef20` — feat: MatchResult.failed unterscheidet technischen Fehler von echtem Score 0
3. `0c6de8f` — feat: Backoff-Kurve + Inhalts-Fehler-Erkennung + Match-Fallback-Konstanten
4. `0ecbb63` — feat: Ollama-Fallback-Kette + technische Fehlerklassifizierung im Match-Pfad
5. `8f2ea98` — feat: lokaler Match-Pfad schreibt keinen Fake-Score 0 mehr
6. `415f4eb` — feat: Retry-Zweig zieht technische Fehlschläge unabhängig vom prefilter-Gate
7. `41dab40` — feat: Einmal-Cleanup-Script für technische Fehlbewertungen im Altbestand

**Was implementiert wurde:**
- **Alembic-Migration** `c1d2e3f4a5b6` → `job_matches.eval_attempts` (Integer, default 0)
- **MatchResult.failed** Flag in `claude_matcher.py` — unterscheidet technischen Fehler von echtem Score 0
- **4 Env-Vars/Konstanten** in `claude_utils.py`: `MATCH_MAX_EVAL_ATTEMPTS=5`, `MATCH_FALLBACK_ENABLED=true`, `MATCH_OLLAMA_FALLBACK_MODEL=gemma4:12b`, `PERMANENT_FAIL_REASONING`
- **Backoff-Helper** `_retry_backoff_hours` (1,2,4,8,12h gekappt)
- **Content-Failure-Erkennung** `_result_is_content_failure` (failed-Flag + Reasoning-Heuristik)
- **Ollama-Fallback-Kette** in `_run_match_via_service`: Service-seitiger Fallback + eigener Ollama-Call bei Prosa
- **Content-Failure-Handling** in beiden Pfaden (Service + Local): kein Fake-Score 0, eval_attempts++ bei Prosa, PERMANENT_FAIL_REASONING ab 5. Versuch
- **`_run_claude_match_for` Guard** bei `eval_attempts >= 5`
- **Retry-Zweig** in `cron_claude_match.py`: zieht technische Fehlschläge (`eval_attempts 1–4`) unabhängig vom prefilter-Gate, mit Backoff per `updated_at`
- **Einmal-Cleanup-Script** `scripts/reeval_technical_failures.py` (Dry-run Default, `--apply` mit JSON-Backup)
- **14 neue Tests** (12 in `test_match_eval_retry.py`, 2 in `test_reeval_script.py`)

**Noch zu tun (Task 9 — Deploy + Daten-Reconciliation, siehe Plan für Details):**
1. Branch zu `master` mergen
2. Migration auf Oracle VM anwenden: `docker exec bewerbungen-app alembic upgrade head`
3. Spalte verifizieren
4. Cleanup-Script Dry-run + Apply: `python3 scripts/reeval_technical_failures.py --apply`
5. 8 bereits zurückgesetzte Matches `eval_attempts=1` setzen (IDs: 2451,2453,2473,2502,2554,2721,3057,3060)
6. Smoke via cron-Trigger: `docker exec bewerbungen-cron curl -X POST ...`

**Verifikation:** `pytest tests/services/test_match_eval_retry.py tests/services/test_reeval_script.py` → 14/14 passed. `pytest tests/services/ tests/api/test_jobs_cron.py tests/api/test_jobs_user.py` → 363 passed (7 failures in test_pattern_learner.py sind pre-existing AI-Key-abhängige Tests).

**⚠ MagicMock-Kompatibilität:** `_result_is_content_failure` prüft `isinstance(failed, bool)` — verhindert False Positives bei Tests die `MagicMock` statt `MatchResult` verwenden (Hotfix in diesem Commit).

### 2026-06-12 — opencode als System-Provider + Free-Tier + Browser-Use MCP + ai-provider Fixes (durch opencode)

**Browser-Use MCP rewritten:**
- Alte Agent-Variante (Ollama + browser-use, zu langsam, 75s Timeout) ersetzt durch **8 deterministische Tools** (navigate/click/fill/select/extract/screenshot/html/close)
- Stateful Session (ein Event-Loop über gesamte MCP-Lifetime)
- Kein LLM nötig – schnelle Playwright-Operationen (<3s pro Schritt)
- `opencode.jsonc` zeigt auf `/Library/WebServer/Documents/wolfinisoftware/scripts/browser-use-mcp.py`

**ai-provider-service (Hotfixes per SSH auf Oracle VM):**
1. **`Config`-Import fehlte** in `providers_api.py:42` → NameError → `/providers` gab 500 → alle Provider "nicht verfügbar"
2. **`opencode` war `system: False`** → Model-Endpoint blockierte (400 "nicht konfiguriert") für User ohne eigene opencode-Konfig, obwohl globaler `OPENCODE_API_KEY` existiert
3. **`opencode` in PROVIDER_REGISTRY** → `system: True`, `requires: []`, `optional: ['api_key','api_endpoint']`
4. **`_load_config` in dispatcher.py** → opencode-Check VOR system-Branch (sonst totes Code wegen system:True)
5. **`Config`-Import fehlte** in dispatcher.py → `name 'Config' is not defined` bei Chat-Calls
6. **`free_models` zum API-Response** hinzugefügt (statt Suffix-Raten im Frontend)

**Bewerbungstracker Backend Fixes (`api/providers.py`):**
1. **`allowed` fehlte im list_providers-Response** → Frontend filtert seit v62 mit `p.configured && p.allowed`, `allowed` war `undefined` → alle Provider rausgefiltert
2. **`free_models` fehlte im models-Proxy** → App-Proxy gibt jetzt `free_models` aus ai-provider-Response durch
3. **opencode-Prüfung** beim Settings-Save: `provider == 'opencode'` überspringt Config-Check (system provider mit Free-Tier)

**Frontend (`index.html`):**
1. Provider-Filter überall: `p.configured && p.allowed` (Backup, Override, Comparison-Modal)
2. `free_models` aus API-Response statt `endsWith('-free')`-Suffix
3. Paid-Modelle ausgeblendet wenn kein eigener opencode API-Key
4. Konfig-Formular: API-Key optional (Free-Modus ohne Key), Hinweise für Free/Paid
5. Service Worker v61→v62

**Wichtig bei Container-Neustart der Oracle VM:**
- ai-provider-service Änderungen sind per `sed`/`docker cp` im laufenden Container gemacht – **überleben keinen Image-Neubau**. Für dauerhaften Fix müssen `providers_api.py`, `dispatcher.py`, `providers/__init__.py`, `providers/opencode.py` und `health_tracker.py` im ai-provider-service Repo committed und Image neugebaut werden.
- Bewerbungstracker Änderungen sind committed und gepusht (s.u.).

**Nächste Schritte:**
- ai-provider-service Image neubauen mit den 6 Hotfixes
- `setup-oracle-vm.sh` ggf. aktualisieren

### 2026-06-12 — Review-Fixes der opencode-Session + ai-provider-Hotfixes persistiert (durch Claude Code)

**Review der opencode-Commits (a040252 u.a.) — 2 echte Probleme gefixt, Commit `582b765`:**
- `services/ai_provider_client.py`: neue öffentliche `get_models_raw()` (volles Dict inkl. `free_models`). `api/providers.py` griff vorher mit `client._get(...)` direkt auf den privaten HTTP-Helper zu (§3.1-Bruch) → jetzt `get_models_raw()`. `get_models()` unverändert.
- `index.html`: `_opencodeUserConfigured`-Cache nach erfolgreichem Speichern einer opencode-Config invalidiert — sonst blieben Paid-Modelle bis Reload versteckt.
- `service-worker.js`: v62→v63 (Frontend-Änderung → SW-Cache-Bump).
- 2 neue Tests in `tests/services/test_ai_provider_client.py`. `pytest tests/api tests/services` → 546 passed (7 pre-existing test_pattern_learner-Failures, lokal fehlendes `jsonschema`).
- Branch `claude/naughty-turing-5e5603`, NICHT zu master gemergt, NICHT deployed.

**ai-provider-service SSH-Hotfixes persistiert → [PR #21](https://github.com/haraldweiss/ai-provider-service/pull/21):**
- Vollständiger `.py`-Abgleich Container↔`origin/main`: nur 3 Dateien differierten (`api/providers_api.py`, `dispatcher.py`, `providers/__init__.py`); `config.py`/`opencode.py`/`health_tracker.py` auf main bereits korrekt/identisch. Der Handoff oben listete 5 Dateien — `config.py` war schon committed, daher hier präziser.
- **Kern-Bug auf main:** `Config.OPENCODE_API_KEY` wurde referenziert **ohne** `from config import Config` → NameError auf jedem opencode-Pfad. Plus opencode noch `system: False`.
- Fix übernimmt die produktiv laufende Container-Version 1:1 + Test auf neuen System-Provider-Vertrag aktualisiert. `pytest tests/` → 205 passed.
- **⚠ Image NICHT vor Merge neubauen** — `main` hat den Fix erst nach Merge; ein Rebuild aus aktuellem `main` würde Prod regredieren (Container läuft nur via SSH-Hotfix). Reihenfolge: **PR #21 mergen → dann Image neubauen.**

<!-- Example:
### 2026-05-27 — services/ extraction landed
- 924 lines out of api/, 797 into services/
- claude_utils.py and email_import_utils.py created
- Test mock paths updated in tests/api/test_jobs_cron.py and test_jobs_user.py
- NOT deployed to IONOS — needs manual deploy via DEPLOYMENT_IONOS.md
-->

### 2026-06-13 — Fix: Worker fehlte `DATABASE_URL` → Job-/Email-Import stumm `queued` (durch Claude Code)

**Symptom:** Indeed/IMAP-Job-Import in den Einstellungen nahm den Klick an (`POST /api/jobs/sources/<id>/import-from-email` → 202), aber der Task wurde NIE verarbeitet — `task_queue.status='queued'` für immer (`started_at=NULL`). Rückfall der Failure-Klasse vom 2026-06-12 Volume-Split (oben), diesmal via Env statt Volume.

**Root Cause:** `start_worker()` in `deploy/container/setup-oracle-vm.sh` mountete — anders als `start_app()` — KEINE `.env`, sondern reichte nur `-e ENCRYPTION_KEY` durch. → Worker ohne `DATABASE_URL` → Fallback auf relativen Default `sqlite:///bewerbungstracker.db` (= `/app/bewerbungstracker.db`, leere DB) statt `/app/data/bewerbungstracker.db`. Die API enqueued in die echte DB, der Worker pollte die leere → `pick_next_task()` lieferte immer `None`. Regression beim Container-Recreate am 2026-06-12. Diagnose: im Worker-App-Context lieferte `SELECT … WHERE status='queued'` 0 Zeilen vs. 3 in der echten DB; Worker-URI war `sqlite:///bewerbungstracker.db`.

**Fix — [PR #29](https://github.com/haraldweiss/Bewerbungstracker/pull/29) gemerged → master `d4c2890`:**
- `setup-oracle-vm.sh` `start_worker()`: mountet jetzt dieselbe `.env` wie die App (erbt `DATABASE_URL`+`ENCRYPTION_KEY`), fragiles manuelles ENCRYPTION_KEY-grep entfernt. Siehe neue Hard Rule §3.5.
- `database.py:_set_sqlite_pragmas`: `busy_timeout=10000` jetzt VOR `journal_mode=WAL` — sonst failt die WAL-Pragma sofort mit „database is locked" bei Multi-Writer-Contention (das crash-loopte den Worker-Subprozess `worker.py:139 create_app→create_all` am 06-12 beim Start).

**Deploy-Status: ERLEDIGT — running == committed (2026-06-13).**
- Zwischenstand (historisch): der `.env`-Fix lief zuerst als Incident-Recreate via ad-hoc `docker run` live (die 2 hängenden `email_import`-Tasks liefen sofort auf `done`), während der Pragma-Fix noch im alten Image `35e4215` fehlte.
- **Abschluss:** Image aus master `0f7b22b` neu gebaut + alle 5 Container über `setup-oracle-vm.sh rebuild` neu erstellt → laufend == committed, Worker wieder über das Skript (nicht mehr der manuelle Recreate). Verifiziert: alle 5 auf `localhost/bewerbungen:0f7b22b`, Worker-`DATABASE_URL=sqlite:////app/data/bewerbungstracker.db`, **0 Lock-Crashes** beim Start (Pragma-Härtung greift), App `/` 200, public https 200, `test_noop`-Task → `done`.

**Build-Mechanik (oracle-vm hat KEINEN dauerhaften Checkout):** `git archive <sha> | ssh oracle-vm 'tar -x -C /tmp/bwt-build'` → `cd /tmp/bwt-build && ./deploy/container/build.sh <sha>` (expliziter Tag-Arg, da Archive kein `.git` hat) → `IMAGE_TAG=<sha> deploy/container/setup-oracle-vm.sh rebuild`. **Rollback:** altes Image `35e4215` bleibt → `IMAGE_TAG=35e4215 setup-oracle-vm.sh rebuild`.

### 2026-06-13 — Add: Original-Stellenlink beim Übernehmen (Tracker-Auflösung) + Backfill (durch Claude Code)

**Problem:** „📥 Übernehmen" (`POST /matches/<id>/import`) kopierte `raw_job.url` 1:1 in `Application.link`. Bei E-Mail-Quellen ist das ein Klick-Tracking-Redirect (StepStone `click.stepstone.de/f/a/…`, LinkedIn `comm/jobs/view/…`, Indeed `cts.indeed.com/…`), nicht der echte Stellenlink.

**Lösung (PRs [#32](https://github.com/haraldweiss/Bewerbungstracker/pull/32) + [#33](https://github.com/haraldweiss/Bewerbungstracker/pull/33), gemerged → master `228a33e`):**
- Neues Modul `services/job_sources/url_resolver.py` → `resolve_original_url(url)` (best-effort, 10 Unit-Tests):
  - **LinkedIn**: `comm/jobs/view/<id>` → kanonisch `linkedin.com/jobs/view/<id>/` (reiner String, kein Netz).
  - **StepStone/Indeed**: Redirect folgen — **HEAD, dann GET mit Browser-UA** (StepStone-SendGrid timeoutet auf HEAD), nur Final-URL auf erwarteter Domain (SSRF-Guard, analog `email_jobs._resolve_indeed_tracker`).
  - **Generisch**: nur Tracking-Params (utm_*, trackingId) strippen, kein Netz.
  - Fehler / fremde Domain → Eingabe-Link bleibt (nie schlechter als der Tracker).
- `import_match` löst vor `Application.link` + „Original-Link"-Notiz auf.
- `scripts/backfill_application_links.py` zieht Bestand nach (`--check`, `--limit`, `--sleep`).

**Grenze StepStone:** Der öffentliche Posting-Link ist aus dem E-Mail-Tracker NICHT rekonstruierbar — die Kette endet bei einem personalisierten `www.stepstone.de/v2/magiclink/exchange?magicLink=<JWT>` (kann ablaufen). Das ist trotzdem besser als der opake `click.`-Tracker (echte Domain, browser-klickbar).

**Deployed:** Image `228a33e`, alle 5 Container neu erstellt, App/public 200, Resolver im Container verifiziert. **Backfill gelaufen:** 25 LinkedIn (→ saubere `jobs/view`) + 9 StepStone (→ Magic-Link) = 34 Bewerbungen bereinigt, 0 `click.`/`comm`-Tracker übrig.

### 2026-06-22 — 503 beim Match-Scoring gefixt + Ollama-Modell-Umstellung + Bulk-Scoring angestoßen (durch pi/Claude Code)

**Problem:** Klick auf "🤖 Bewerten lassen" (`POST /api/jobs/matches/{id}/score`) gab 503 zurück. Root Cause (via SSH auf Oracle VM, Docker-Logs + Traceback-Analyse):
- User-Konfiguration nutzte `opencode` / `opencode-deepseek-v4-flash-free`
- DeepSeek-Free lieferte unparsbares JSON zurück → Summarize-Retry → 2 AI-Provider-Calls pro Match
- Gesamtzeit > 60s → Gunicorn-Worker-Timeout → Worker stirbt → Apache 503
- ai-provider-service hatte ebenfalls Worker-Timeouts (120s) mit qwen3.6 (23 GB, zu langsam)

**Fix (Runtime-Konfig, kein Code-Commit):**
- **Modell umgestellt:** User `harald.weiss@wolfinisoftware.de` → `ai_provider=ollama`, `ai_model=mistral-nemo:12b-instruct-2407-q5_K_M` (vorher: `opencode`/`opencode-deepseek-v4-flash-free`)
- **Gunicorn-Timeout erhöht:** `GUNICORN_TIMEOUT=180` in `/etc/bewerbungen/bewerbungen.env` (vorher: default 60s)
- **Worker neugestartet** (`docker restart bewerbungen-worker`)
- **Bulk-Scoring** für 64 neue Matches angestoßen (Task-ID `3d5ea8a5`, läuft im Hintergrund)

**Verifikation:** Test-Score Match #592 → HTTP 200, `match_score: 87.0`, `provider_used: ollama`, `model_used: mistral-nemo:12b-instruct-2407-q5_K_M`.

**WordPress wolfinisoftware.de (gleiche Oracle VM):**
- **Kritisch:** File-Ownership `root:root` → `apache:apache` + `FS_METHOD=direct` → Auto-Updates repariert
- **Empfohlen:** System-Cron eingerichtet (`*/15 * * * * curl -s https://wolfinisoftware.de/wp-cron.php`) → verspätete Cron-Events behoben
- **Empfohlen:** Stale WP-Super-Cache-Config aus `wp-config.php` entfernt (Plugin nicht mehr installiert, Redis-Cache läuft als Object Cache)
