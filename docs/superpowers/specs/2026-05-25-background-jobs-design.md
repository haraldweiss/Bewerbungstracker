# Background-Job-Architektur — Design (P1 + P2)

**Status:** approved — ready for plan
**Datum:** 2026-05-25
**Scope:** P1 (Job-Queue-Skelett) + P2 (`/import-from-email` als erster Konsument)
**Out of Scope:** P3 (weitere User-Endpoints), P4 (Cron in Queue) — eigene Specs später

## Motivation

User-getriggerte Email-Imports (`/api/jobs/sources/<id>/import-from-email`) lieferten 502er, weil gunicorn-Worker durch lange IMAP/AI-Pfade gekillt wurden. Sofortmaßnahmen A (`--workers 6 --timeout 240`) und B (Wall-Clock-Budget über IMAP + dyn. AI-Timeout, Commit `75f94ad`) sind deployed und reduzieren das akute Risiko, lösen aber die Architektur-Grundsache nicht: Web-Worker führen lange Operationen synchron aus und blockieren bei parallelen Triggern (User + Cron). C verschiebt lange Operationen in einen Background-Worker; Web-Worker bedienen nur noch kurze Requests.

## Architektur

```
┌─────────────────┐   POST /api/jobs/sources/X/import-from-email
│ Frontend (SPA)  │ ──────────────────────────► ┌──────────────┐
│                 │ ◄─── 202 {task_id: ...} ─── │ Flask /      │
│ poll status     │                              │ gunicorn     │
│ every 2s        │ ◄── GET /api/tasks/<id> ──── │ (6 workers)  │
│                 │                              └──────┬───────┘
└─────────────────┘                                     │
                                                        ▼ INSERT/SELECT
                                                ┌──────────────┐
                                                │ task_queue   │ ← SQLite (WAL)
                                                │ (bewerbungen │
                                                │  .db)        │
                                                └──────┬───────┘
                                                       │ pickup
                                                       ▼
                                                ┌──────────────┐
                                                │ task-worker  │
                                                │ .service     │
                                                │ (systemd,    │
                                                │  2 workers)  │
                                                └──────────────┘
```

**Drei Komponenten:**
1. `task_queue`-Tabelle in `bewerbungen.db` (persistent Job-State)
2. `bewerbungstracker-task-worker.service` (systemd-Unit, Daemon mit 2 Worker-Subprozessen)
3. `/api/tasks/*`-Endpoints in Flask

Web-Worker schreiben nur Rows + lesen Status. Job-Execution ausschließlich im Daemon. Wenn der Daemon stirbt, akkumulieren Jobs in DB; werden beim Restart abgearbeitet. Kein Datenverlust.

## Datenmodell

```sql
CREATE TABLE task_queue (
    id           TEXT PRIMARY KEY,           -- UUID4
    type         TEXT NOT NULL,              -- 'email_import', …
    user_id      TEXT NOT NULL,              -- FK → user.id, ownership-check
    payload      TEXT NOT NULL,              -- JSON, type-spezifisch

    status       TEXT NOT NULL,              -- queued | running | done | failed | cancelled
    result       TEXT,                       -- JSON bei status='done'
    error        TEXT,                       -- message + traceback-Excerpt
    progress     INTEGER DEFAULT 0,          -- 0–100

    attempts     INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    priority     INTEGER DEFAULT 0,          -- höher = vorzugsweise

    created_at   TIMESTAMP NOT NULL,
    started_at   TIMESTAMP,
    finished_at  TIMESTAMP,
    heartbeat_at TIMESTAMP,                  -- alle 10s vom Worker
    worker_id    TEXT,                       -- hostname:pid

    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE INDEX idx_task_queue_pickup
  ON task_queue(status, priority DESC, created_at)
  WHERE status IN ('queued', 'running');
CREATE INDEX idx_task_queue_user
  ON task_queue(user_id, created_at DESC);
```

**Status-Übergänge:**
```
queued ──pick──► running ──ok──►  done
                   │
                   ├──exc──► queued  (attempts < max_attempts, Backoff)
                   ├──exc──► failed  (attempts >= max_attempts)
                   └──stale─ recovery durch anderen Worker
```

**Atomares Pick (SQLite ≥ 3.35):**
```sql
UPDATE task_queue
   SET status = 'running',
       worker_id = ?,
       started_at = ?,
       heartbeat_at = ?,
       attempts = attempts + 1
 WHERE id = (
   SELECT id FROM task_queue
    WHERE status = 'queued'
      AND created_at <= ?              -- für Backoff-Delay
    ORDER BY priority DESC, created_at
    LIMIT 1
 )
   AND status = 'queued'
RETURNING *;
```
Verhindert Race zwischen parallelen Workern.

**Stale-Recovery (Pre-Pickup):**
```sql
UPDATE task_queue
   SET status = 'queued', worker_id = NULL
 WHERE status = 'running'
   AND heartbeat_at < datetime('now', '-60 seconds');
```
Heartbeat alle 10s, Schwelle 60s.

**Retry-Backoff:** `5s, 30s, 300s` (über `created_at += backoff` und `status = 'queued'`).

**Migration:** Alembic-Revision `add_task_queue.py`, läuft im `bewerbungen-deploy.sh` via `alembic upgrade head`.

## Worker-Daemon

**Layout:** 1 Master-Prozess + 2 Worker-Subprozesse (multiprocessing). Skalierbar via `TASK_WORKER_COUNT` env-var.

**Worker-Loop (Pseudo):**
```python
def worker_loop(worker_id):
    app = create_app()
    while not _stop:
        with app.app_context():
            recover_stale_tasks()
            task = pick_next_task(worker_id)
        if task is None:
            time.sleep(2)
            continue
        try:
            handler = HANDLERS[task.type]   # KeyError → failed, no retry
            heartbeat = HeartbeatThread(task.id, interval=10).start()
            result = handler(task.payload, progress_cb=...)
            heartbeat.stop()
            mark_done(task.id, result)
        except Exception as exc:
            heartbeat.stop()
            if task.attempts < task.max_attempts:
                requeue_with_backoff(task.id, exc)
            else:
                mark_failed(task.id, exc)
```

**Handler-Registry:**
```python
# services/tasks/registry.py
HANDLERS: dict[str, Callable] = {}

def register(task_type: str):
    def decorator(fn):
        HANDLERS[task_type] = fn
        return fn
    return decorator
```

**Heartbeat:** Hintergrund-Thread schreibt `UPDATE task_queue SET heartbeat_at = now() WHERE id = ?` alle 10s während Job aktiv.

**Graceful Shutdown:** SIGTERM/SIGINT setzt `_stop`, Worker beendet aktuellen Job, schreibt Status, exitet. `TimeoutStopSec=300` in systemd damit ein 150s-Email-Import nicht abgewürgt wird.

**App-Context:** Jeder Worker initialisiert eigenen Flask-App-Context (eigene DB-Session). Explizit `with app.app_context()` (Lesson aus Auto-Backup-Incident 2026-05-04).

**systemd-Unit:**
```ini
[Unit]
Description=Bewerbungstracker Task Worker (Background-Jobs)
After=network.target

[Service]
WorkingDirectory=/var/www/bewerbungen
ExecStart=/bin/bash -c 'source /var/www/bewerbungen/.env && \
  exec /var/www/bewerbungen/venv/bin/python -m services.tasks.worker'
Restart=always
RestartSec=10
TimeoutStopSec=300

[Install]
WantedBy=multi-user.target
```

## API-Endpoints

| Methode | Pfad | Auth | Zweck |
|---|---|---|---|
| `GET` | `/api/tasks/<id>` | `@token_required` + ownership | Status (für Polling) |
| `GET` | `/api/tasks?type=&limit=20` | `@token_required` | Eigene Jobs, neueste zuerst |
| `POST` | `/api/tasks/<id>/cancel` | `@token_required` + ownership | Setzt `cancelled` wenn noch `queued` (P1); running-Cancel → P3 |

**Enqueue ist kein API-Endpoint.** Bestehende Endpoints wie `import-from-email` rufen intern `enqueue_task(type, user_id, payload)` auf.

**Response `GET /api/tasks/<id>`:**
```json
{
  "id": "a3f1...",
  "type": "email_import",
  "status": "running",
  "progress": 47,
  "created_at": "2026-05-25T15:30:00Z",
  "started_at": "2026-05-25T15:30:02Z",
  "finished_at": null,
  "result": null,
  "error": null,
  "attempts": 1
}
```

`status: "done"` → `result` enthält vollständiges Payload (kompatibel zum heutigen Sync-Response — Frontend-Render-Logik bleibt).

**Status-Codes:**
- `202 Accepted` beim Enqueue (am ursprünglichen Endpoint)
- `200 OK` beim Status-Polling
- `404` wenn job_id unbekannt oder fremder User
- `409 Conflict` beim Cancel wenn Job nicht mehr `queued`

## Frontend-Flow (`/import-from-email`)

```
[User klickt Import]
     │
     ▼
POST /api/jobs/sources/19/import-from-email
     │
     ▼
202 Accepted { "task_id": "a3f1...", "status": "queued" }
     │
     ▼  Spinner + "In Bearbeitung..."
     ▼  GET /api/tasks/a3f1 alle 2s (30s lang), dann alle 5s
     │
     ├─► running, progress=47    → Progress-Bar
     ├─► done, result={...}       → wie heute rendern
     ├─► failed, error="..."      → Fehler-Toast
     └─► nach 5 Min ohne Fortschritt: Timeout-Hinweis, weiter pollen
```

**Backwards-compatibility:** Keine. Alter Sync-Pfad wird ersetzt. Kein Feature-Flag — das Risiko des Sync-Pfads ist genau das Problem das wir lösen.

## Testing

| Ebene | Test | Mechanik |
|---|---|---|
| Unit | `pick_next_task` atomar | 2 Threads gleichzeitig, assert nur einer kriegt Job |
| Unit | Stale-Recovery | heartbeat_at >60s alt → re-queued |
| Unit | Retry-Backoff | Exception → attempts++, created_at verschoben |
| Unit | `enqueue_task` schreibt korrekten JSON-Payload | DB-Read nach Enqueue |
| Integration | `email_import`-Handler liefert gleiche result-Form wie Sync | Vergleich mit Fixtures aus `tests/api/test_indeed_email_import.py` |
| Integration | `GET /api/tasks/<id>` ownership-check | User A → Job von User B → 404 |
| E2E (manuell) | Realer Email-Import via Worker auf VPS | curl trigger, polle Status, assert done |

**Bestehende Tests** (`tests/api/test_indeed_email_import.py`): Handler-Logik wird aus `api/jobs_user.py` in `services/tasks/handlers/email_import.py` extrahiert. Tests kriegen kleinen Import-Pfad-Refactor; Logik unverändert.

## Edge-Cases — explizit gehandhabt

- Worker crashed mitten im Job → Heartbeat veraltet → re-queue (attempts++)
- DB locked (parallele Cron + User) → Exponential-Backoff statt Worker-Tod
- User löscht Source während Job läuft → FK/Lookup-Fail → `failed` mit klarer message
- Worker startet während Job `running` → Stale-Recovery nach 60s
- Job-Type fehlt in HANDLERS → sofort `failed`, kein Retry (sinnlos)

## Edge-Cases — bewusst NICHT in P1+P2

- Cancel während `running` (P3)
- Multi-User-Rate-Limiting (YAGNI: Single-User-System)
- Job-Dependencies (YAGNI)
- Persistente Worker-Logs pro Job neben `error`-Spalte (P3 ggf.)

## Rollout

1. **P1 deployen**: `task_queue`-Tabelle + Worker-Daemon + Status-Endpoints. Niemand nutzt sie noch.
2. **P1 validieren**: 24h mit künstlichem `test_noop`-Task laufen lassen (Cron triggert stündlich). Logs prüfen.
3. **P2 deployen**: `import-from-email` schreibt nur noch enqueue, Frontend pollt. Alter Pfad ersetzt.
4. **Rollback**: `git revert` der P2-Commits → Sync-Pfad zurück. P1-Tabelle bleibt liegen, schadet nicht.

## Monitoring

- Worker-Logs via `journalctl -u bewerbungstracker-task-worker`
- Pro-Job-Log-Zeile: `task=email_import id=a3f1 user=... duration=42.3s status=done`
- Admin-Tab erweitert um Section "Background Jobs": Liste mit Status + Dauer + Error-Excerpt der letzten 50 Jobs des Users

## Offene Punkte (für Implementation-Plan)

Nichts ist offen — Design ist vollständig für P1+P2. Implementation-Plan kann starten.
