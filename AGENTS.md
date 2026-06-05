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

### 2026-06-05 — Quick-Reasons-UI Phase 1: Tasks 1+2+3 implementiert, Übergabe per §3.7

**Status:** Subagent-Driven-Development läuft. **3 von 9 Tasks fertig**, lokal committed, NICHT gepusht. Übergabe weil Session-Limit naht (neue Regel §3.7).

**Branch:** `claude/modest-goldberg-c98a13` (Worktree: `.claude/worktrees/modest-goldberg-c98a13/`).
**Offener PR:** [#20](https://github.com/haraldweiss/Bewerbungstracker/pull/20) (für Auto-Reject-Schärfung — Quick-Reasons-Commits liegen im selben Branch und würden beim Push den PR aufblähen; vor Push überlegen ob neuer Branch).

**Lokale Commits seit `9eda949` (origin/master):**
- `34d7152` Fix: Auto-Reject matcht Firmen mit/ohne Rechtsform-Suffix (PR #20)
- `82d301f` Add: AGENTS.md §3.6 — /loop-Regel
- `5c44fce` Fix: Status 'ghosting' zaehlt als Reject
- `8790048` Add: AGENTS.md §7 Handoff (Auto-Reject 2026-06-05)
- `c1a0e90` Add: Design-Spec Quick-Reasons-UI
- `d5c028c` Add: Implementation-Plan Quick-Reasons-UI (9 Tasks)
- `6037597` + `1b8ab56` **Task 1** ✅ — Migration `a9b8c7d6e5f4` + `User.job_type_blacklist TEXT NOT NULL DEFAULT '[]'`. Fix-Commit korrigiert `server_default="'[]'"` → `'[]'` (bare, war Bug im Plan). 2 Tests grün.
- `d957441` Add: AGENTS.md §3.7 — Pflicht-Handoff bei ~90 % Session-Limit
- `fdabc3b` + `2a31597` **Task 2** ✅ — `detect_job_type()` in `services/job_matching/prefilter.py` + 7 (→9) Unit-Tests. Fix-Commit nach Review: `auf rechnung` → `auf rechnungsbasis` (false-positive-Guard), `werkstudenten`-Plural ergänzt, Test-Import oben.
- `86c1abb` **Task 3** ✅ Implementer + Spec-Review noch offen — `cron_prefilter` integriert `detect_job_type` (Reihenfolge: rejected_company → wrong_job_type → duplicate → low_score). 3 neue Handler-Tests grün, 41/41 Regression grün. Return-Dict um `wrong_job_type_dismissed` erweitert.

**Wo genau weitermachen:**
- **Task 3 Spec-Review** noch nicht gelaufen. Dispatch-Prompt-Pattern siehe Task 1 + 2 (gleiche Struktur). BASE_SHA `2a31597`, HEAD_SHA `86c1abb`.
- **Task 3 Code-Quality-Review** nach Spec-Review.
- Danach **Tasks 4-9** aus dem Plan: [`docs/superpowers/plans/2026-06-05-quick-reasons-ui.md`](docs/superpowers/plans/2026-06-05-quick-reasons-ui.md).
- TaskCreate-Liste (#1-#9) ist persistiert; #1+#2 completed, #3 in_progress, #4-#9 pending.

**Wichtige Lessons-Learned für nächste Session:**
- Plan hatte `server_default="'[]'"` — falsch. Konvention im Repo (siehe `platform_profiles`-Migration) ist `server_default='[]'` bare. Sollte im Plan korrigiert werden bevor Task 1 wiederholt würde.
- `JobSource` hat kein `config_json`-Kwarg im Constructor, sondern Property-Setter `src.config = {}` (Pattern aus `test_handler_cron_indeed_email_import.py`).
- `auf rechnung` als Freelance-Signal ist zu breit — `auf rechnungsbasis` ist die saubere Variante.

**Nicht gepusht, nicht deployed.** PR #20 ist MERGEABLE aber stale gegenüber lokalem Stand. Beim Push entscheiden: PR #20 erweitern oder neuen Branch für Quick-Reasons.

### 2026-06-05 — Auto-Reject-Analyse + Quick-Win-Fixes
- **Analyse Prod-DB:** 1.786/1.891 JobMatches dismissed (94 %), aber `company_already_rejected` traf nur 7×. Den 138 manuellen User-Texten standen 12+ Fälle „X hat schon abgesagt" gegenüber → zwei Lücken identifiziert: (a) Suffix-Mismatch („Signal Iduna" vs. „Signal Iduna Group AG"), (b) Status `ghosting` nicht in Reject-Set.
- **Fix 1 — Company-Normalisierung:** Neuer Helper `services/email_import_utils.py::normalize_company()` (Rechtsformen-Strip GmbH/AG/KG/SE/Ltd/Inc + „Group/Holding/International" + Trailing-Klammern). `get_rejected_companies_lower()` liefert normalisiertes Set. Alle 4 Vergleichsstellen umgestellt (cron_prefilter, email_import, cron_indeed_email_import, api/jobs_user). Inline-Duplikat in cron_prefilter entfernt.
- **Fix 2 — Status-Set:** `'ghosting'` zum Reject-Set ergänzt (`_REJECTING_STATUSES`). Konsistent mit `feedback_bridge.py::_TERMINAL_STATES`-Mapping ghosting → rejected_after_apply. Prod-DB: 9 ghosting-Apps werden ab jetzt für Auto-Reject genutzt.
- **AGENTS.md §3.6:** Neue Regel — `/loop` bei Polling/wiederkehrenden Tasks (Claude Code) statt Sleep-Schleifen. opencode-Pendant aktuell unbekannt.
- **Tests:** 17 neue Tests (`tests/services/test_email_import_utils.py`) — Normalisierung + DB-Integration (Status-Set, Window, soft-deleted). 17/17 passed. Breiter Sweep `tests/services/ tests/api/` → 490 passed (7 Fehler durch lokal fehlendes jsonschema, unabhängig).
- NICHT deployed to IONOS. Backwards-kompatibel — alte Daten bleiben in DB, neuer Prefilter greift ab Deploy.
- **Backlog (offen für separate Sessions):** Body-Phrasen-Scan für „werden keine Bewerbungen mehr angenommen", User-Keyword-Blacklist („kein Freelancer/Werkstudent"), Cross-Portal-Duplicate via Fuzzy-Title-Match, stille Dismisses (812 mit leerem feedback_text) → Quick-Reasons-UI.

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
