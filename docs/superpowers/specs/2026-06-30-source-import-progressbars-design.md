# Source Import Progressbars - Design

**Status:** approved 2026-06-30
**Source:** User feedback: the source import view is hard to follow. Each source should show what is being processed and roughly how long it will take. Scope explicitly includes single email import, "Alle importieren", and pattern learning.

## Goal

Make source operations understandable at source-row level. A user should be able to see, for each source, whether it is waiting, importing, learning, done, or failed, including percentage, elapsed time, and a rough ETA when enough progress data exists.

Out of scope:
- Parallelizing imports. The current sequential queue stays in place to avoid overloading IMAP and the Flask/Gunicorn workers.
- Persisting progress across page reloads beyond what existing task polling can infer for tasks started in the current page session.
- Adding a new database column for task messages in this iteration.

## UI

The existing sources table in `index.html` gets one compact progress area per source row, directly below the source name and metadata.

For idle sources the area is hidden, so the table keeps its current density.

For active operations the row shows:
- Operation label: `Import` or `Lernen`.
- State label: `Wartet`, `Startet`, `Laeuft`, `Fertig`, or `Fehler`.
- Progressbar using task `progress` from `GET /api/tasks/<id>`.
- Elapsed time, for example `seit 18s`.
- Rough ETA once progress is meaningful, for example `noch ca. 45s`.

For "Alle importieren":
- All enabled email sources are marked immediately.
- The first source shows an active import state once its task is enqueued.
- Later sources show `Wartet` with their queue position.
- As the sequential queue advances, the source currently being processed transitions from waiting to active.

For pattern learning:
- The same row progress area is reused with operation label `Lernen`.
- The existing toast can remain for final success/error feedback, but progress should no longer rely on repeated toasts as the main signal.

Completion behavior:
- Successful email import briefly shows a summary such as `Fertig: 42 Mails geprueft, 5 neu, 3 Duplikate`.
- Successful pattern learning briefly shows a summary such as `Fertig: 72% Hit-Rate`.
- After refresh, completed progress rows disappear unless an operation is still running.
- Failed rows stay visible in red until the next refresh or retry, so the affected source is obvious.

## Data Flow

No backend schema change is required.

Current flow:
1. `POST /api/jobs/sources/<id>/import-from-email` enqueues an `email_import` task and returns `task_id`.
2. `POST /api/jobs/sources/<id>/train-pattern` enqueues a `pattern_learner_train` task and returns `task_id`.
3. `pollTask(task_id, onProgress)` polls `GET /api/tasks/<id>`.
4. Task rows already expose `status`, `progress`, timestamps, result, and error.

Frontend state:
- Add a module-local map keyed by `sourceId`.
- Each entry stores operation, task id if known, status, progress, start time, queue position, ETA text, and final summary/error.
- Rendering the source table reads this state and includes the progress area for affected rows.
- Polling callbacks update the state and patch the relevant row without forcing full table refresh on every tick.

ETA calculation:
- Use local start time and current percentage.
- Show elapsed time immediately.
- Show ETA only when progress is above 5 and below 100.
- Clamp or omit nonsensical values, for example if percentage regresses or elapsed time is too short.

## Error Handling

- Enqueue failure: source row shows `Fehler` with the enqueue error; button is re-enabled.
- Task failure/cancel: source row shows `Fehler` with the task error.
- Polling/network error: source row shows a concise error message and keeps the source identifiable.
- Queue duplicate clicks keep current behavior: duplicate active source clicks are ignored, queued source clicks are not duplicated.

No raw email body, CV content, credentials, or sensitive job text should be logged or shown in debug messages.

## Testing

Backend:
- No new backend behavior is expected. Existing task endpoint tests remain relevant.
- If implementation touches API serialization, extend `tests/api/test_tasks_api.py`.

Frontend/manual:
- Single email source import: row shows progress, elapsed time, ETA, and final import summary.
- "Alle importieren" with at least three email sources: all rows show waiting/active states in sequence and no duplicate queue entries.
- Pattern learning: row shows learning progress and final hit-rate summary.
- Error case: simulate or force a failed task; affected row remains red with a concise error.
- Mobile-width check: progressbar text must fit without overlapping action buttons.

Automated JS tests are not currently established for this vanilla `index.html` module. If a lightweight test harness is present or easy to reuse, add tests for ETA formatting and progress-state rendering helpers; otherwise keep verification manual and document it in the final handoff.

## Implementation Notes

Expected files:
- `index.html` for the source-row progress UI and orchestration changes.
- Optional: `frontend/js/task-poller.js` only if the polling helper needs a backward-compatible enhancement.
- Tests only if API behavior changes or helper code becomes extractable.

Keep API routes thin and avoid moving import business logic into `api/`. Existing async task handling remains the source of truth for long-running work.
