# AGENTS.md — Bewerbungstracker

Shared instructions for all AI coding agents working in this repo. Both `CLAUDE.md` and `AGENTS.md` point here.

---

## 0. Before your first commit in a session

```bash
git config user.email   # must be: harald.weiss@wolfinisoftware.de
git config user.name    # must be: Harald Weiss
git fetch origin
```

If `user.email` is unset, empty, or fake — **stop, fix it, then proceed**. Past incident: 3 commits got pushed with **completely empty author and committer** (invisible on GitHub) because the local git config had `user.email=""`.

---

## 1. What this project is

- **Privacy-first application/job-application tracker** with email integration, PDF export, CV comparison
- Python Flask backend + IMAP/POP3/Gmail/Outlook integration + async task queue
- Deployed on IONOS VPS (see `DEPLOYMENT_IONOS.md`)
- **Default branch: `master`** (not `main`)
- Remote: `github.com:haraldweiss/Bewerbungstracker`
- No GitHub ruleset enforced

---

## 2. Agent routing

### opencode (Throughput)
- `api/` → `services/` extraction-style refactors (recent pattern in `816cd7c`)
- Test-mock-path cleanup after refactor
- README / doc updates
- Blacklist/keyword tuning in `services/job_sources/`

### Claude Code (Care)
- IMAP / OAuth-token handling (`services/email_*`, `services/calendar_*`)
- Anthropic-client cost-tracking changes (`services/cost_tracker.py`)
- Production deploys to IONOS (cron, gunicorn, supervisor)
- DB schema migrations
- CV file upload paths (security-sensitive)

---

## 3. Hard rules

### 3.1 Architecture invariant — `services/` is source of truth
- Business logic lives in `services/*.py`. `api/*.py` is **thin** routing only.
- After the 2026-05-27 refactor: `api/jobs_cron.py` and `api/jobs_user.py` shrank by ~920 lines because the logic moved to `services/job_matching/claude_utils.py` and `services/email_import_utils.py`.
- **Don't re-fatten `api/`**. If you find logic there, either it pre-dates the refactor (move it to `services/`) or this rule needs revisiting (discuss).

### 3.2 Anthropic client deduplication
- `_get_anthropic_client()` in `services/job_matching/claude_utils.py` is the **single source of truth**.
- Don't instantiate `anthropic.Anthropic(...)` directly anywhere else — go through the helper so cost tracking + retry + auth stay consistent.

### 3.3 Email parsing safety
- `services/email_import_utils.py` strips signatures/footers before keyword matching. The heyjobs blacklist had false-positives from email footers — fix `5390a77` hardened this. **Don't bypass the footer-strip** when adding new email-source parsers.

### 3.4 Privacy
- No telemetry, no external tracking, no analytics. Everything is local-or-on-the-user's-server.
- CV file uploads + email bodies + applications are sensitive. Don't log raw content; redact in logs.

### 3.5 Async task queue
- Long-running work goes through `services/tasks/handlers/`. Don't block the Flask request thread for >1s.
- Cron tasks defined in `services/tasks/handlers/cron_*.py`.

### 3.6 `/loop` für Polling / wiederkehrende Tasks (Claude Code)
- Wenn eine Aufgabe Polling, periodische Status-Checks oder wiederholtes Ausführen desselben Prompts / Slash-Commands erfordert, **`/loop` nutzen** statt sequenzieller Sleep-Schleifen oder manuellem Wiederausführen.
- Typische Fälle: Deploy-Status auf VPS überwachen, Cron-Run abwarten, `/babysit-prs`-artige Routinen, „prüfe alle 5 Minuten ob X fertig ist".
- Faustregel: ab **2 Wiederholungen mit Zeit-/Intervall-Komponente** ist `/loop` vorteilhaft. Für reine Hintergrund-Tasks, bei denen das System Claude ohnehin per Notification weckt (`run_in_background`), KEIN `/loop` — das ist Polling-Verschwendung.
- Nicht für einmalige Tasks. Nicht als Ersatz für `/schedule` / scheduled-tasks (das ist für längere/cron-artige Routinen außerhalb der laufenden Session).
- **opencode**: Stand 2026-06-05 ist kein direktes `/loop`-Äquivalent bekannt. Falls eine opencode-Session Polling braucht → Frage an User stellen oder die Polling-Aufgabe an Claude Code abgeben. Wenn ein opencode-Pendant auftaucht, hier ergänzen.

### 3.7 Session-Limit-Handoff bei ~90 % (Pflicht, gilt allgemein)
**Sobald Anzeichen vorliegen, dass die Session ~90 % des Context-/Token-Limits erreicht hat — VOR weiteren Aktionen Übergabe schreiben und stoppen.**

Anzeichen (eines reicht): wiederholte System-Compression-Hinweise; sehr viele/große Tool-Outputs in der laufenden Session; lange ununterbrochene Arbeit mit mehreren Subagent-Dispatches; Auto-Compression-Trigger feuert demnächst.

**Übergabe = neuer datierter Eintrag in §7 (Handoff zone)** mit mindestens:
- Was fertig wurde in dieser Session: Commits (SHA), Branches, PRs (Link).
- Was lokal noch nicht committed / nicht gepusht ist (Pfad + Kurzbeschreibung).
- Was als nächstes ansteht und WO exakt weitergemacht werden kann (Datei + Zeile, oder Task-Nummer im Plan).
- Bei Subagent-Driven-Development aktiv: zuletzt abgeschlossener Task, nächster auszuführender Task, offene Reviewer-Issues.

**Nach der Übergabe:**
- KEINE weiteren Subagents dispatchen.
- KEINE Pushes / PR-Updates / Merges / Deploys.
- Eine knappe Schluss-Nachricht: „Session bei ~90 %, Übergabe in §7 geschrieben, hier ist Schluss."

**Faustregel:** Im Zweifel zu früh übergeben statt zu spät. Eine zu früh geschriebene Übergabe kostet wenig; eine bei einem Subagent-Push abgebrochene Session kostet richtig (verlorener Kontext + halbe Reviews + möglicherweise inkonsistente Commit-Reihenfolge).
---

## 4. Verification standards

```
Verified: pytest tests/ (NNN passed), services/ refactor smoke-tested
locally, NOT deployed to IONOS yet
```
or
```
Verified: pytest tests/api/test_jobs_user.py (12/12 passed), did not test
the email cron path (requires real IMAP)
```

For changes that touch IMAP / email cron / Anthropic API: state explicitly whether you tested with real credentials or mocks only.

---

## 5. Commit style

- Granular: 3–8 small commits per topic
- Concrete numbers ("796 lines extracted from api/ to services/")
- Bug reproducer in body
- Polish pass as separate commit
- Default branch is `master` — PR base is `master`, not `main`

---

## 5.1 Sync discipline — git, AGENTS.md, README must stay current

Cross-project rule (canonical statement in `wolfini_de_web` AGENTS.md §5.1). Every non-trivial change in this repo must update three artifacts in lockstep:

1. **Git** — commit the change. Don't end a session with uncommitted operational work in the tree. If a session can't commit (blocked hook, etc.), say so in the handoff entry (§7).
2. **AGENTS.md** — update whenever the change adds/modifies/invalidates a hard rule (§3), a deploy/verify procedure (§4-§6), or a follow-up the next session needs (§7). Includes *removing* stale entries in the same commit they go obsolete.
3. **README** — update when the change affects setup, env vars, ports, ownership/permission expectations, deploy steps, or known caveats. Create one if missing AND the change warrants it.

If a sibling repo is touched in the same session (`wolfini_de_web`, `ai-provider-service`, `Claude-KI-Usage-Tracker`), the same three artifacts must be updated *there too* — link the sibling PR from the handoff entry.

---

## 6. Quick reference

| What | Path / command |
|---|---|
| Run dev | `python app.py` (or per `DEPLOYMENT.md`) |
| Tests | `pytest tests/` |
| Production deploy (bare-metal) | see `DEPLOYMENT_IONOS.md` |
| Container deploy (Podman Quadlet) | see `deploy/container/setup-vps.sh` |
| Services layer | `services/` — business logic |
| API layer | `api/` — thin routing only |
| Async tasks | `services/tasks/handlers/` |
| Anthropic client | `services/job_matching/claude_utils.py::_get_anthropic_client` |
| Email parsing | `services/email_import_utils.py` |
| Cost tracking | `services/cost_tracker.py` |
| Cron handlers | `services/tasks/handlers/cron_*.py` |

---

## 7. Handoff zone (free-form, append-only)

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

---

## 9. Docker-Container: Host-Erreichbarkeit (127.0.0.1-Falle)

**Problem:** `AI_PROVIDER_SERVICE_URL=http://127.0.0.1:8767` funktioniert **nicht** innerhalb eines Docker-Containers, weil `127.0.0.1` auf den Container-Loopback zeigt, nicht auf den Host.

**Lösung:** Auf dem Oracle-VPS (Docker-Bridge-Netz) den Host über die Gateway-IP `172.17.0.1` erreichen:

```bash
AI_PROVIDER_SERVICE_URL=http://172.17.0.1:8767
APP_INTERNAL_URL=http://172.17.0.1:5000
```

Diese Werte stehen in `/etc/bewerbungen/bewerbungen.env` auf dem VPS und werden per `-v` ins Container-Mount eingebunden (`/app/.env:ro`).

**Nicht vergessen:** Nach Änderung der `.env` den Container neustarten:
```bash
docker stop bewerbungen-app && docker rm bewerbungen-app && docker run -d ...
```

**Warum das immer wieder auftritt:** In lokalen Dev-Umgebungen und alten IONOS-Podman-Setups war `127.0.0.1` korrekt. Bei jedem Docker-Rebuild/Neuaufsetzen muss `AI_PROVIDER_SERVICE_URL` geprüft werden. Siehe auch `deploy/container/setup-vps.sh` für die korrekten Werte.

### 2026-06-09 — Forgot-Password + toggle-job-discovery + Rene Account

**Add: `/api/auth/forgot-password` + `/api/auth/reset-password`**
- `api/auth.py`: New routes — generates EmailConfirmationToken (1h TTL), sends reset email, validates token, updates password + DEK
- `services/email_service.py`: New `send_password_reset_email()` with styled HTML template
- `frontend/pages/login.html`: "Passwort vergessen?" link + `showForgotPassword()` JS (prompt → fetch → toast)

**Add: `POST /api/auth/change-password`** — authenticated user changes own password (old_pw + new_pw, re-encrypts DEK)

**Add: `POST /api/admin/users/<id>/toggle-job-discovery`** — direct toggle with optional `{enabled: bool}` body

**Fix: `GET /api/admin/users` — now returns `job_discovery_enabled`**

**Fix: `models.py` — `job_discovery_enabled` default changed to `True`** (was `False`)

**New user: ri-lampe@t-online.de (Rene Lampe)** — Bürokaufmann IHK + Lager/Logistik CV uploaded, job_discovery enabled, pipeline triggered

**Container fix:** DATABASE_URL pointed to `/app/data/instance/` instead of `/app/data/` — real DB was in parent dir. Fixed during container recreate.

**Verified:** forgot-password sends email ✓, users 3 in DB ✓, login works ✓, toggle-job-discovery endpoint 401 (needs auth) ✓

### 2026-06-09 — Fix: Region-Filter localStorage war pro Domain, nicht pro User

**Bug:** `loadJobDiscoveryFilters()` lud den Region-Filter (PLZ) aus `localStorage` mit Key `jdFiltersCache`. Da localStorage pro Browser-Domain (nicht pro User) geteilt wird, sah User A nach Login die PLZ von User B.

**Fix:**
1. Region-Filter wird jetzt aus dem Backend geladen (`GET /profile/job-discovery/status` → `filters.job_region_filter`) — autoritativ
2. localStorage-Key ist jetzt pro User: `jdFilters_<email>` — nur noch Cache für UI-State zwischen Seitenaufrufen
3. Backend-Status-Endpoint (`profile.py:200`) lieferte `job_region_filter` bereits — wurde nur vom Frontend ignoriert

**Lehre:** localStorage nie als Source of Truth für User-Daten — nur als Cache. DB (via API) ist immer autoritativ.

**Verified:** index.html deployed ✓, Image neugebaut ✓, Container restarted ✓

### 2026-06-09 — SSL-Monitoring + AI-Email-Klassifizierung + Pro-User-Phrasen

**SSL-Zertifikat-Überwachung (scripts/oracle/cert-monitor/):**
- `/usr/local/bin/wolfini-cert-monitor.sh` prüft täglich 06:00 UTC alle 7 LE-Zertifikate
- E-Mail an harald.weiss@... bei <30 Tagen (Warnung) oder <14 Tagen (Kritisch)
- Certbot Deploy-Hook kopiert erneuerte Zerts nach `/etc/pki/tls/certs/` (SELinux-kompatibel) + reload Apache
- Alle LE-live-Pfade in Apache-Konfig auf `/etc/pki/tls/certs/` umgestellt (cert_t-SELinux-Problem auf OL9)

**AI-Email-Klassifizierung (`email_service.py`):**
- `classify_email_with_ai()` sendet Email-Betreff + Absender + Snippet an `opencode-deepseek-v4-flash-free`
- Erkennt: `absage`, `interview`, `zusage` oder `null` (neutral)
- Ergebnis wird in `email_monitoring`-Tabelle gespeichert (`ai_status`, `ai_reasoning`)
- `GET /api/monitoring/log` gibt die letzten 100 Einträge zurück
- Background-Scheduler nutzt KI automatisch bei jedem Durchlauf

**Monitoring-Dashboard (Frontend):**
- Aufklappbarer "📋 Monitoring-Verlauf" unter den Monitoring-Einstellungen
- Tabelle: Datum, Unternehmen, Status, KI-Badge (❌=Absage, 📅=Interview, ✅=Zusage)
- Lädt per `loadMonitoringLog()` via `callEmailService('/api/monitoring/log')`

**Pro-User-Ablehnungs-Phrasen:**
- `models.py`: neue Spalte `job_body_reject_phrases` (JSON-Array, default `[]`)
- `scan_body_reject()` akzeptiert optionale `extra_phrases` — merged mit globalen `BODY_REJECT_PHRASES`
- `cron_prefilter.py`: lädt User-Phrasen in Cache, übergibt sie an `scan_body_reject()`
- `api/profile.py`: `GET /profile/job-discovery/status` + `PATCH` unterstützen `job_body_reject_phrases`
- Frontend: neues Textarea "Ablehnungs-Phrasen" im Job-Filter-Bereich, pro Zeile eine Phrase

**Verified:** email_service.py deployed ✓, index.html deployed ✓, Docker neugebaut ✓, alle Container restarted ✓

### 2026-06-09 — Email-Service Proxy + Absage-Status-Schutz + Script-Escape-Fix

**Email-Service über Apache Proxy:** Die `/email-service/` und `/imap-proxy/` Pfade wurden nicht an die entsprechenden Container weitergeleitet → Email-Monitoring zeigte "undefined". Fix: ProxyPass-Regeln in der Apache-Vhost-Konfiguration ergänzt (MÜSSEN vor dem allgemeinen `ProxyPass /` stehen, da Apache first-match-wins verwendet). `ai-admin`-Vhost deaktiviert (fehlendes SSL-Zertifikat).

**Status-Schutz für "Absage":** `handleAppsScriptAnswers()` in `index.html` übersprang abgesagte Bewerbungen nicht — eine erneute automatische Antwort-Erkennung konnte `absage` überschreiben. Fix: vor dem Auto-Update `if (existingApp.status === 'absage') continue;` — nur manuelle Änderungen können den Status noch ändern.

**Script-Escape-Fix:** In einem Template-Literal (`const html = \`...\``) stand `</script>` → der HTML-Parser schloss den Script-Tag vorzeitig → `SyntaxError: Unexpected end of input`. Fix: `<\/script>` statt `</script>` — JS wertet `\` vor `/` als No-Op aus, der HTML-Parser sieht aber kein gültiges `</script>` und lässt den Script-Block intakt. Gleiches für `</body>` und `</html>`.

**Apache Config:** `ai-admin`-Vhost deaktiviert (`mv .conf .conf.disabled`) wegen fehlendem SSL-Zertifikat (muss erneuert werden bevor ai-admin wieder geht).

**Verified:** index.html escaped ✓, Email-Service via Proxy erreichbar (HTTP 200) ✓, Container neugebaut ✓, Apache neugeladen ✓

<!-- Example:
### 2026-05-27 — services/ extraction landed
- 924 lines out of api/, 797 into services/
- claude_utils.py and email_import_utils.py created
- Test mock paths updated in tests/api/test_jobs_cron.py and test_jobs_user.py
- NOT deployed to IONOS — needs manual deploy via DEPLOYMENT_IONOS.md
-->
