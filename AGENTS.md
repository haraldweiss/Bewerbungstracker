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
- Deployed on Oracle VM (Docker, see `deploy/container/setup-oracle-vm.sh`)
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
- Production deploys to Oracle VM (docker, gunicorn, supervisor)
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
- **Der WORKER-Container MUSS dieselbe `.env` mounten wie die APP** (`-v /etc/bewerbungen/bewerbungen.env:/app/.env:ro`) — der Entrypoint sourct `/app/.env` für alle Rollen. Ohne sie fehlt dem Worker `DATABASE_URL`, er fällt auf den **relativen** Default `sqlite:///bewerbungstracker.db` (= `/app/bewerbungstracker.db`, leer) zurück und pollt eine ANDERE DB als die App → enqueued Tasks bleiben stumm `queued`, der Worker sieht sie nie. Gleiche Failure-Klasse wie der Volume-Split 2026-06-12 (§7), nur via Env statt Volume. Schnelldiagnose: `docker exec -i bewerbungen-worker python -` mit `from app import create_app; create_app().config['SQLALCHEMY_DATABASE_URI']` → muss `sqlite:////app/data/bewerbungstracker.db` zeigen (4 Slashes, absolut), nicht den relativen Default.

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

### 3.8 Keine persistenten Hotfixes in laufenden Containern (Pflicht)
**Änderungen an Produktions-Containern NIE per `sed`/`docker cp`/`docker exec`-Edit „dauerhaft" lassen.** Solche Hotfixes überleben keinen Image-Neubau und erzeugen stille **Drift** zwischen „was läuft" und „was im Repo/Image ist" — genau das hat die Session 2026-06-12 gekostet (opencode-Hotfixes nur im Container, dazu zwei latente master-Bugs `f6c2b28`/cron-Env, die erst beim Rebuild zuschlugen).

Erlaubt ist ein Hotfix **nur** zum sofortigen Service-Retten in einem Incident — und dann gilt **in derselben Session**:
1. Fix in den Repo committen (Code **oder** `deploy/container/*`), PR auf.
2. Image neu bauen (`deploy/container/build.sh` → SHA-Tag) und Container über `setup-oracle-vm.sh` neu erstellen, damit Laufendes == Committed.
3. Im Handoff (§7) festhalten, falls der Repo-Teil noch offen ist.

**Deploy-Disziplin:** Container immer über `setup-oracle-vm.sh` erzeugen (single source of truth für Volume-Namen/Env/Ports), nie per ad-hoc `docker run` aus dem Gedächtnis. Image immer mit `build.sh` bauen (taggt SHA + `:latest`) → Rollback via `IMAGE_TAG=<sha> setup-oracle-vm.sh rebuild`. Vor Merge müssen die CI-Gates grün sein (`.github/workflows/ci.yml`: pytest **und** Image-Build+Boot+Healthcheck — letzteres fängt die Bind-/Boot-Klasse, die Unit-Tests nicht sehen).
---

## 4. Verification standards

```
Verified: pytest tests/ (NNN passed), services/ refactor smoke-tested
locally, NOT deployed yet
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
| Production deploy | see `deploy/container/setup-oracle-vm.sh` |
| Container build | see `deploy/container/build.sh` |
| Services layer | `services/` — business logic |
| API layer | `api/` — thin routing only |
| Admin API | `api/admin.py` — Status-Übersicht, Health-Checks |
| Calendar API | `api/calendar.py` — Interview-Erkennung + Kalender-Ansicht |
| Async tasks | `services/tasks/handlers/` |
| Anthropic client | `services/job_matching/claude_utils.py::_get_anthropic_client` |
| Email parsing | `services/email_import_utils.py` |
| Cost tracking | `services/cost_tracker.py` |
| Cron handlers | `services/tasks/handlers/cron_*.py` |

---


## 7. Handoff zone

Session-Protokolle und Übergaben sind in [`CHANGELOG.md`](./CHANGELOG.md) dokumentiert.

Neue Handoffs bitte dort eintragen, nicht in AGENTS.md.

---

<!-- Append notes here with date and agent type. Use CHANGELOG.md for new entries. -->
