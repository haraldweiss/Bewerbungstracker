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

<!-- Example:
### 2026-05-27 — services/ extraction landed
- 924 lines out of api/, 797 into services/
- claude_utils.py and email_import_utils.py created
- Test mock paths updated in tests/api/test_jobs_cron.py and test_jobs_user.py
- NOT deployed to IONOS — needs manual deploy via DEPLOYMENT_IONOS.md
-->
