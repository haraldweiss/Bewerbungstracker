# Background-Jobs P1+P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Asynchrone Background-Job-Verarbeitung über SQLite-Queue + systemd-Worker-Daemon. P1 liefert das Skelett, P2 migriert `/import-from-email` als ersten Konsumenten.

**Architecture:** Neue `task_queue`-Tabelle in `bewerbungen.db`; separater Python-Daemon (`bewerbungstracker-task-worker.service`) mit 2 Multiprocessing-Workers, der atomar Jobs pickt und Handler aus einer Registry ausführt; Flask-Endpoints schreiben nur Enqueue + lesen Status; Frontend pollt alle 2s/5s.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, Alembic, SQLite (WAL), Vanilla-JS Frontend, systemd

**Spec:** [docs/superpowers/specs/2026-05-25-background-jobs-design.md](../specs/2026-05-25-background-jobs-design.md)

---

## File Structure

**Neu erstellen:**
- `alembic/versions/<rev>_add_task_queue.py` — DB-Migration
- `models.py` (modify) — TaskQueue-Model anhängen
- `services/tasks/__init__.py` — Package-Marker
- `services/tasks/queue.py` — Atomic-Pickup, Stale-Recovery, Retry-Logik, enqueue_task()
- `services/tasks/registry.py` — Handler-Registry + `@register` Decorator
- `services/tasks/heartbeat.py` — Heartbeat-Thread
- `services/tasks/worker.py` — Worker-Loop + Multiprocessing-Entrypoint (`python -m services.tasks.worker`)
- `services/tasks/handlers/__init__.py` — importiert alle Handler-Module (triggert Registrierung)
- `services/tasks/handlers/test_noop.py` — Smoke-Handler für P1-Validation
- `services/tasks/handlers/email_import.py` — extrahiert aus `api/jobs_user.py:import_from_email` (P2)
- `api/tasks.py` — Flask-Blueprint mit `GET /api/tasks/<id>`, `GET /api/tasks`, `POST /api/tasks/<id>/cancel`
- `tests/services/tasks/test_queue.py`
- `tests/services/tasks/test_registry.py`
- `tests/services/tasks/test_worker.py`
- `tests/services/tasks/test_handlers_email_import.py`
- `tests/api/test_tasks_api.py`

**Modifizieren:**
- `api/jobs_user.py` (Zeile 1015–1148) — `import_from_email` schreibt nur noch Enqueue
- `tests/api/test_indeed_email_import.py` — Anpassung an Async-Verhalten
- `app.py` oder `wsgi.py` — neuen `tasks_bp` registrieren
- Frontend: JS-Datei mit Email-Import-Trigger (exakter Pfad in Task 19) — Polling-Logik
- Frontend: Admin-UI HTML + JS — Background-Jobs-Section

**Deploy:**
- `/etc/systemd/system/bewerbungstracker-task-worker.service` (neu auf VPS)
- `/usr/local/bin/bewerbungen-deploy.sh` (auf VPS) — Worker-Restart nach `git pull`

---

# PHASE 1: Job-Queue-Skelett

## Task 1: DB-Migration für `task_queue`

**Files:**
- Create: `alembic/versions/<rev>_add_task_queue.py`

- [ ] **Step 1: Generate revision**

```bash
venv/bin/alembic revision -m "add task_queue table"
```
Notiere die generierte Revision-ID (z.B. `a1b2c3d4e5f6`). Datei landet in `alembic/versions/`.

- [ ] **Step 2: Edit revision file**

Inhalt der `upgrade()`- und `downgrade()`-Funktionen ersetzen:

```python
def upgrade():
    op.create_table(
        'task_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('payload', sa.Text, nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('result', sa.Text, nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
        sa.Column('attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer, nullable=False, server_default='3'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('finished_at', sa.DateTime, nullable=True),
        sa.Column('heartbeat_at', sa.DateTime, nullable=True),
        sa.Column('worker_id', sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index(
        'idx_task_queue_pickup', 'task_queue',
        ['status', 'priority', 'created_at'],
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        'idx_task_queue_user', 'task_queue',
        ['user_id', 'created_at'],
    )


def downgrade():
    op.drop_index('idx_task_queue_user', table_name='task_queue')
    op.drop_index('idx_task_queue_pickup', table_name='task_queue')
    op.drop_table('task_queue')
```

- [ ] **Step 3: Apply migration locally**

```bash
venv/bin/alembic upgrade head
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> <rev>, add task_queue table`

- [ ] **Step 4: Verify schema**

```bash
sqlite3 instance/bewerbungen.db ".schema task_queue"
```
Expected: CREATE TABLE statement mit allen Columns + 2 Indexes.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*_add_task_queue.py
git commit -m "feat(tasks): add task_queue table migration"
```

---

## Task 2: TaskQueue SQLAlchemy-Model

**Files:**
- Modify: `models.py` (am Ende anhängen)

- [ ] **Step 1: Append model**

```python
class TaskQueue(db.Model):
    __tablename__ = 'task_queue'
    id = db.Column(db.String(36), primary_key=True)
    type = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    result = db.Column(db.Text)
    error = db.Column(db.Text)
    progress = db.Column(db.Integer, nullable=False, default=0)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    priority = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    heartbeat_at = db.Column(db.DateTime)
    worker_id = db.Column(db.String(128))

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status,
            'progress': self.progress,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'started_at': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'finished_at': self.finished_at.isoformat() + 'Z' if self.finished_at else None,
            'result': json.loads(self.result) if self.result else None,
            'error': self.error,
            'attempts': self.attempts,
        }
```

- [ ] **Step 2: Verify import works**

```bash
venv/bin/python -c "from models import TaskQueue; print(TaskQueue.__tablename__)"
```
Expected: `task_queue`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat(tasks): add TaskQueue model"
```

---

## Task 3: `enqueue_task()` helper

**Files:**
- Create: `services/tasks/__init__.py` (leer)
- Create: `services/tasks/queue.py`
- Create: `tests/services/tasks/__init__.py` (leer)
- Create: `tests/services/tasks/test_queue.py`

- [ ] **Step 1: Write failing test**

`tests/services/tasks/test_queue.py`:
```python
import json
import pytest
from datetime import datetime
from app import create_app
from database import db
from models import User, TaskQueue
from services.tasks.queue import enqueue_task


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def user(app):
    u = User(id='u1', email='t@example.com', name='T')
    db.session.add(u)
    db.session.commit()
    return u


def test_enqueue_creates_queued_row(app, user):
    task_id = enqueue_task('test_noop', user.id, {'foo': 'bar'})
    row = db.session.get(TaskQueue, task_id)
    assert row is not None
    assert row.status == 'queued'
    assert row.type == 'test_noop'
    assert row.user_id == user.id
    assert json.loads(row.payload) == {'foo': 'bar'}
    assert row.attempts == 0
    assert isinstance(row.created_at, datetime)
```

- [ ] **Step 2: Run test, verify FAIL**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py::test_enqueue_creates_queued_row -v
```
Expected: ImportError / ModuleNotFoundError on `services.tasks.queue`.

- [ ] **Step 3: Implement `enqueue_task`**

`services/tasks/__init__.py`: leer
`services/tasks/queue.py`:
```python
"""Job-Queue: enqueue, atomic pickup, stale recovery, retry."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from database import db
from models import TaskQueue


def enqueue_task(task_type: str, user_id: str, payload: dict[str, Any],
                 *, max_attempts: int = 3, priority: int = 0) -> str:
    """Schreibt eine neue Job-Row, returnt task_id."""
    task_id = str(uuid.uuid4())
    row = TaskQueue(
        id=task_id,
        type=task_type,
        user_id=user_id,
        payload=json.dumps(payload),
        status='queued',
        max_attempts=max_attempts,
        priority=priority,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    return task_id
```

- [ ] **Step 4: Run test, verify PASS**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py::test_enqueue_creates_queued_row -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/tasks/ tests/services/tasks/
git commit -m "feat(tasks): add enqueue_task helper"
```

---

## Task 4: `pick_next_task()` atomic pickup

**Files:**
- Modify: `services/tasks/queue.py`
- Modify: `tests/services/tasks/test_queue.py`

- [ ] **Step 1: Write failing test (single-pickup happy path)**

Anhängen an `test_queue.py`:
```python
from services.tasks.queue import pick_next_task


def test_pick_next_task_marks_running(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    picked = pick_next_task(worker_id='w1')
    assert picked is not None
    assert picked.id == task_id
    assert picked.status == 'running'
    assert picked.worker_id == 'w1'
    assert picked.attempts == 1
    assert picked.started_at is not None
    assert picked.heartbeat_at is not None


def test_pick_next_task_returns_none_when_empty(app, user):
    assert pick_next_task(worker_id='w1') is None


def test_pick_next_task_skips_running(app, user):
    enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    assert pick_next_task(worker_id='w2') is None
```

- [ ] **Step 2: Run tests, verify FAIL**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py -v
```
Expected: 3 fails on missing `pick_next_task`.

- [ ] **Step 3: Implement `pick_next_task`**

Append to `services/tasks/queue.py`:
```python
from sqlalchemy import text


def pick_next_task(worker_id: str) -> TaskQueue | None:
    """Atomar einen queued-Task auf running setzen und zurückgeben.

    Nutzt UPDATE ... RETURNING (SQLite >= 3.35). Verhindert Race zwischen
    parallelen Workern.
    """
    now = datetime.utcnow()
    stmt = text("""
        UPDATE task_queue
           SET status = 'running',
               worker_id = :worker_id,
               started_at = :now,
               heartbeat_at = :now,
               attempts = attempts + 1
         WHERE id = (
           SELECT id FROM task_queue
            WHERE status = 'queued'
              AND created_at <= :now
            ORDER BY priority DESC, created_at
            LIMIT 1
         )
           AND status = 'queued'
        RETURNING id
    """)
    result = db.session.execute(stmt, {'worker_id': worker_id, 'now': now})
    row = result.fetchone()
    db.session.commit()
    if row is None:
        return None
    return db.session.get(TaskQueue, row[0])
```

- [ ] **Step 4: Run tests, verify PASS**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py -v
```
Expected: alle 4 Tests PASS.

- [ ] **Step 5: Atomicity-Test mit 2 Threads**

Anhängen:
```python
import threading


def test_pick_next_task_is_atomic_under_concurrency(app, user):
    """2 Threads picken gleichzeitig — nur einer kriegt den Job."""
    enqueue_task('test_noop', user.id, {})
    results = []
    lock = threading.Lock()

    def worker(wid):
        with app.app_context():
            t = pick_next_task(worker_id=wid)
            with lock:
                results.append(t)

    threads = [threading.Thread(target=worker, args=(f'w{i}',)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [r for r in results if r is not None]
    assert len(successes) == 1, f"expected 1 pick, got {len(successes)}"
```

```bash
venv/bin/pytest tests/services/tasks/test_queue.py::test_pick_next_task_is_atomic_under_concurrency -v
```
Expected: PASS (kann bei SQLite-Concurrency flaky sein; bei Failure WAL-Mode prüfen).

- [ ] **Step 6: Commit**

```bash
git add services/tasks/queue.py tests/services/tasks/test_queue.py
git commit -m "feat(tasks): atomic pick_next_task with UPDATE...RETURNING"
```

---

## Task 5: `recover_stale_tasks()`

**Files:**
- Modify: `services/tasks/queue.py`
- Modify: `tests/services/tasks/test_queue.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import timedelta
from services.tasks.queue import recover_stale_tasks


def test_recover_stale_tasks_requeues_old_running(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    row = db.session.get(TaskQueue, task_id)
    row.heartbeat_at = datetime.utcnow() - timedelta(seconds=90)
    db.session.commit()

    recovered = recover_stale_tasks(stale_seconds=60)
    assert recovered == 1
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'queued'
    assert row.worker_id is None


def test_recover_stale_tasks_skips_fresh(app, user):
    enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    assert recover_stale_tasks(stale_seconds=60) == 0
```

- [ ] **Step 2: Run, verify FAIL**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py::test_recover_stale_tasks_requeues_old_running tests/services/tasks/test_queue.py::test_recover_stale_tasks_skips_fresh -v
```

- [ ] **Step 3: Implement**

Append to `services/tasks/queue.py`:
```python
def recover_stale_tasks(stale_seconds: int = 60) -> int:
    """Re-queued Tasks deren Worker offenbar gestorben ist.

    Returns: Anzahl recoverter Tasks (für Monitoring).
    """
    threshold = datetime.utcnow() - timedelta(seconds=stale_seconds)
    stmt = text("""
        UPDATE task_queue
           SET status = 'queued',
               worker_id = NULL
         WHERE status = 'running'
           AND heartbeat_at < :threshold
    """)
    result = db.session.execute(stmt, {'threshold': threshold})
    db.session.commit()
    return result.rowcount or 0
```

Plus `from datetime import timedelta` zum Import hinzufügen.

- [ ] **Step 4: Run, verify PASS**

```bash
venv/bin/pytest tests/services/tasks/test_queue.py -v
```
Expected: alle Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/tasks/queue.py tests/services/tasks/test_queue.py
git commit -m "feat(tasks): recover_stale_tasks for crashed workers"
```

---

## Task 6: `mark_done`, `mark_failed`, `requeue_with_backoff`

**Files:**
- Modify: `services/tasks/queue.py`
- Modify: `tests/services/tasks/test_queue.py`

- [ ] **Step 1: Write failing tests**

```python
from services.tasks.queue import mark_done, mark_failed, requeue_with_backoff


def test_mark_done_sets_result(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    mark_done(task_id, {'imported': 5})
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'done'
    assert row.finished_at is not None
    assert json.loads(row.result) == {'imported': 5}


def test_mark_failed_sets_error(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    mark_failed(task_id, RuntimeError("boom"))
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'failed'
    assert 'boom' in row.error
    assert row.finished_at is not None


def test_requeue_with_backoff(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    requeue_with_backoff(task_id, RuntimeError("transient"))
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'queued'
    assert row.created_at > datetime.utcnow()
    assert 'transient' in row.error
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

Append to `services/tasks/queue.py`:
```python
import traceback as _tb

_BACKOFF_SECONDS = {1: 5, 2: 30, 3: 300}


def mark_done(task_id: str, result: Any) -> None:
    row = db.session.get(TaskQueue, task_id)
    if row is None:
        return
    row.status = 'done'
    row.result = json.dumps(result)
    row.finished_at = datetime.utcnow()
    db.session.commit()


def mark_failed(task_id: str, exc: BaseException) -> None:
    row = db.session.get(TaskQueue, task_id)
    if row is None:
        return
    row.status = 'failed'
    row.error = f"{type(exc).__name__}: {exc}\n{_tb.format_exc()[-1500:]}"
    row.finished_at = datetime.utcnow()
    db.session.commit()


def requeue_with_backoff(task_id: str, exc: BaseException) -> None:
    """Setzt zurück auf queued, mit created_at in der Zukunft (Backoff)."""
    row = db.session.get(TaskQueue, task_id)
    if row is None:
        return
    delay = _BACKOFF_SECONDS.get(row.attempts, 300)
    row.status = 'queued'
    row.worker_id = None
    row.created_at = datetime.utcnow() + timedelta(seconds=delay)
    row.error = f"{type(exc).__name__}: {exc}"
    db.session.commit()
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/tasks/queue.py tests/services/tasks/test_queue.py
git commit -m "feat(tasks): mark_done, mark_failed, requeue_with_backoff"
```

---

## Task 7: Handler-Registry

**Files:**
- Create: `services/tasks/registry.py`
- Create: `tests/services/tasks/test_registry.py`

- [ ] **Step 1: Failing test**

`tests/services/tasks/test_registry.py`:
```python
import pytest
from services.tasks.registry import register, HANDLERS, get_handler


def test_register_decorator_adds_to_registry():
    @register('foo')
    def handler(payload, *, progress_cb=None):
        return {'ok': True}
    assert HANDLERS['foo'] is handler
    assert get_handler('foo') is handler


def test_get_handler_unknown_type_raises():
    with pytest.raises(KeyError):
        get_handler('nonexistent_xyz')
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

`services/tasks/registry.py`:
```python
"""Task-Handler Registry. Handler werden via @register('type') registriert."""
from __future__ import annotations
from typing import Callable

HANDLERS: dict[str, Callable] = {}


def register(task_type: str):
    def decorator(fn: Callable) -> Callable:
        HANDLERS[task_type] = fn
        return fn
    return decorator


def get_handler(task_type: str) -> Callable:
    if task_type not in HANDLERS:
        raise KeyError(f"No handler registered for task type {task_type!r}")
    return HANDLERS[task_type]
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/tasks/registry.py tests/services/tasks/test_registry.py
git commit -m "feat(tasks): handler registry with @register decorator"
```

---

## Task 8: Heartbeat-Thread

**Files:**
- Create: `services/tasks/heartbeat.py`
- Modify: `tests/services/tasks/test_queue.py`

- [ ] **Step 1: Failing test**

Append to `test_queue.py`:
```python
import time
from services.tasks.heartbeat import HeartbeatThread


def test_heartbeat_updates_heartbeat_at(app, user):
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    row = db.session.get(TaskQueue, task_id)
    initial = row.heartbeat_at

    hb = HeartbeatThread(app, task_id, interval=0.1)
    hb.start()
    time.sleep(0.3)
    hb.stop()
    hb.join(timeout=1.0)

    db.session.expire_all()
    row = db.session.get(TaskQueue, task_id)
    assert row.heartbeat_at > initial
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

`services/tasks/heartbeat.py`:
```python
"""Heartbeat-Thread: schreibt heartbeat_at alle N Sekunden für einen aktiven Job."""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from database import db
from models import TaskQueue

logger = logging.getLogger(__name__)


class HeartbeatThread(threading.Thread):
    def __init__(self, app, task_id: str, interval: float = 10.0):
        super().__init__(daemon=True)
        self._app = app
        self._task_id = task_id
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(self._interval):
            try:
                with self._app.app_context():
                    row = db.session.get(TaskQueue, self._task_id)
                    if row is None or row.status != 'running':
                        return
                    row.heartbeat_at = datetime.utcnow()
                    db.session.commit()
            except Exception:
                logger.exception("Heartbeat update failed for task %s", self._task_id)

    def stop(self):
        self._stop_event.set()
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add services/tasks/heartbeat.py tests/services/tasks/test_queue.py
git commit -m "feat(tasks): heartbeat thread for stale-detection"
```

---

## Task 9: Worker-Loop (single-iteration)

**Files:**
- Create: `services/tasks/worker.py`
- Create: `services/tasks/handlers/__init__.py`
- Create: `services/tasks/handlers/test_noop.py`
- Create: `tests/services/tasks/test_worker.py`

- [ ] **Step 1: Implement test_noop handler**

`services/tasks/handlers/__init__.py`:
```python
"""Lädt alle Handler-Module → triggert Registrierung via @register."""
from services.tasks.handlers import test_noop  # noqa: F401
```

`services/tasks/handlers/test_noop.py`:
```python
"""Smoke-Test-Handler. Schläft x Sekunden, returnt {ok: True}."""
import time
from services.tasks.registry import register


@register('test_noop')
def handle_test_noop(payload: dict, *, progress_cb=None) -> dict:
    duration = float(payload.get('sleep_seconds', 0.1))
    if progress_cb:
        progress_cb(0, 'starting')
    time.sleep(duration)
    if progress_cb:
        progress_cb(100, 'done')
    return {'ok': True, 'slept': duration}
```

- [ ] **Step 2: Failing test for worker single-iteration**

`tests/services/tasks/test_worker.py`:
```python
import json
import pytest
from app import create_app
from database import db
from models import User, TaskQueue
from services.tasks.queue import enqueue_task
from services.tasks.worker import run_one_iteration
import services.tasks.handlers  # noqa: F401 — registers handlers


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def user(app):
    u = User(id='u1', email='t@example.com', name='T')
    db.session.add(u)
    db.session.commit()
    return u


def test_run_one_iteration_completes_task(app, user):
    task_id = enqueue_task('test_noop', user.id, {'sleep_seconds': 0.01})
    picked = run_one_iteration(app, worker_id='w-test')
    assert picked is True
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'done'
    assert json.loads(row.result) == {'ok': True, 'slept': 0.01}


def test_run_one_iteration_marks_failed_on_unknown_type(app, user):
    task_id = enqueue_task('does_not_exist', user.id, {})
    picked = run_one_iteration(app, worker_id='w-test')
    assert picked is True
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'failed'
    assert 'does_not_exist' in row.error


def test_run_one_iteration_returns_false_when_idle(app, user):
    assert run_one_iteration(app, worker_id='w-test') is False


def test_run_one_iteration_retries_on_exception(app, user):
    from services.tasks.registry import register

    @register('always_fails')
    def _h(payload, *, progress_cb=None):
        raise RuntimeError("nope")

    task_id = enqueue_task('always_fails', user.id, {}, max_attempts=2)
    run_one_iteration(app, worker_id='w-test')
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'queued'
    assert row.attempts == 1
    from datetime import datetime
    row.created_at = datetime.utcnow()
    db.session.commit()
    run_one_iteration(app, worker_id='w-test')
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'failed'
    assert row.attempts == 2
```

- [ ] **Step 3: Run, verify FAIL**

- [ ] **Step 4: Implement worker.run_one_iteration**

`services/tasks/worker.py`:
```python
"""Worker-Loop: pickt Tasks, ruft Handler, schreibt Result/Error."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from services.tasks.queue import (
    pick_next_task, recover_stale_tasks,
    mark_done, mark_failed, requeue_with_backoff,
)
from services.tasks.registry import get_handler
from services.tasks.heartbeat import HeartbeatThread

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)


def run_one_iteration(app: 'Flask', worker_id: str) -> bool:
    """Eine Iteration: Stale-Recovery + Pick + Handle.

    Returns: True wenn ein Task verarbeitet wurde, False wenn idle.
    """
    with app.app_context():
        recover_stale_tasks(stale_seconds=60)
        task = pick_next_task(worker_id)
        if task is None:
            return False
        task_id = task.id
        task_type = task.type
        task_attempts = task.attempts
        task_max = task.max_attempts
        try:
            payload = json.loads(task.payload)
        except Exception as exc:
            mark_failed(task_id, exc)
            return True

    hb = HeartbeatThread(app, task_id, interval=10.0)
    hb.start()
    try:
        with app.app_context():
            try:
                handler = get_handler(task_type)
            except KeyError as exc:
                mark_failed(task_id, exc)
                return True

            def progress_cb(pct: int, msg: str = ''):
                from database import db
                from models import TaskQueue
                row = db.session.get(TaskQueue, task_id)
                if row is not None:
                    row.progress = int(max(0, min(100, pct)))
                    db.session.commit()

            try:
                result = handler(payload, progress_cb=progress_cb)
                mark_done(task_id, result)
            except Exception as exc:
                logger.exception("Handler %s failed for task %s", task_type, task_id)
                if task_attempts < task_max:
                    requeue_with_backoff(task_id, exc)
                else:
                    mark_failed(task_id, exc)
    finally:
        hb.stop()
        hb.join(timeout=2.0)
    return True


def worker_loop(app: 'Flask', worker_id: str, stop_event) -> None:
    """Endlos-Loop für einen Worker-Prozess. stop_event.set() → graceful exit."""
    logger.info("Worker %s started", worker_id)
    while not stop_event.is_set():
        try:
            did_work = run_one_iteration(app, worker_id)
            if not did_work:
                stop_event.wait(2.0)
        except Exception:
            logger.exception("Worker %s loop error — sleeping 5s", worker_id)
            stop_event.wait(5.0)
    logger.info("Worker %s stopped", worker_id)
```

- [ ] **Step 5: Run tests, verify PASS**

```bash
venv/bin/pytest tests/services/tasks/test_worker.py -v
```
Expected: 4 Tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/tasks/worker.py services/tasks/handlers/ tests/services/tasks/test_worker.py
git commit -m "feat(tasks): worker loop with retry, heartbeat, progress"
```

---

## Task 10: Multiprocessing-Entrypoint

**Files:**
- Modify: `services/tasks/worker.py` (Hauptblock anhängen)

- [ ] **Step 1: Entrypoint anhängen**

An `services/tasks/worker.py` anhängen:
```python
def main():
    """Entrypoint: python -m services.tasks.worker

    Spawnt N Worker-Subprozesse (env TASK_WORKER_COUNT, default 2).
    """
    import multiprocessing as mp
    import os
    import signal
    import socket

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    n_workers = int(os.getenv('TASK_WORKER_COUNT', '2'))
    hostname = socket.gethostname()

    import services.tasks.handlers  # noqa: F401 — Registry füllen

    stop_events = []
    processes = []
    for i in range(n_workers):
        stop = mp.Event()
        stop_events.append(stop)
        p = mp.Process(
            target=_worker_subprocess_main,
            args=(f'{hostname}:{os.getpid()}:{i}', stop),
            name=f'task-worker-{i}',
        )
        p.start()
        processes.append(p)
        logger.info("Spawned worker %s (PID %s)", p.name, p.pid)

    def _shutdown(signum, _frame):
        logger.info("Received signal %s, stopping workers", signum)
        for ev in stop_events:
            ev.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    for p in processes:
        p.join()
    logger.info("All workers exited")


def _worker_subprocess_main(worker_id: str, stop_event) -> None:
    """Wird im Subprozess ausgeführt: Flask-App bauen, worker_loop laufen."""
    import services.tasks.handlers  # noqa: F401 — Registry im Subprozess füllen
    from app import create_app
    app = create_app()
    worker_loop(app, worker_id, stop_event)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Manual smoke-Test lokal**

```bash
TASK_WORKER_COUNT=1 venv/bin/python -m services.tasks.worker
```
In zweitem Terminal:
```bash
venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    from services.tasks.queue import enqueue_task
    from models import User
    u = User.query.first()
    print('enqueue:', enqueue_task('test_noop', u.id, {'sleep_seconds': 1}))
"
```
Expected: Worker-Log zeigt Job-Pickup + Completion innerhalb 2s.

- [ ] **Step 3: Commit**

```bash
git add services/tasks/worker.py
git commit -m "feat(tasks): multiprocessing entrypoint for task-worker daemon"
```

---

## Task 11: systemd-Unit + Deploy-Skript-Integration

**Files:**
- Create: `deploy/bewerbungstracker-task-worker.service`

- [ ] **Step 1: Unit-File im Repo ablegen**

`deploy/bewerbungstracker-task-worker.service`:
```ini
[Unit]
Description=Bewerbungstracker Task Worker (Background-Jobs)
After=network.target

[Service]
WorkingDirectory=/var/www/bewerbungen
ExecStart=/bin/bash -c 'source /var/www/bewerbungen/.env && exec /var/www/bewerbungen/venv/bin/python -m services.tasks.worker'
Restart=always
RestartSec=10
TimeoutStopSec=300
Environment="TASK_WORKER_COUNT=2"

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Auf VPS deployen**

```bash
scp deploy/bewerbungstracker-task-worker.service ionos-vps:/etc/systemd/system/
ssh ionos-vps "systemctl daemon-reload && systemctl enable bewerbungstracker-task-worker.service"
```
Noch NICHT starten — erst nach P1-Endpoints (Task 12-14).

- [ ] **Step 3: Deploy-Skript anpassen**

```bash
ssh ionos-vps "grep -q 'task-worker' /usr/local/bin/bewerbungen-deploy.sh || \
  sed -i '/systemctl restart bewerbungen$/a systemctl restart bewerbungstracker-task-worker.service' /usr/local/bin/bewerbungen-deploy.sh"
ssh ionos-vps "cat /usr/local/bin/bewerbungen-deploy.sh | grep -A1 'restart bewerbungen'"
```
Expected: beide systemctl-restart-Zeilen.

- [ ] **Step 4: Commit**

```bash
git add deploy/bewerbungstracker-task-worker.service
git commit -m "ops(tasks): systemd unit for task-worker daemon"
```

---

## Task 12: `GET /api/tasks/<id>` endpoint

**Files:**
- Create: `api/tasks.py`
- Create: `tests/api/test_tasks_api.py`
- Modify: `app.py` (Blueprint registrieren)

- [ ] **Step 1: Failing test**

`tests/api/test_tasks_api.py`:
```python
import pytest
from app import create_app
from database import db
from models import User
from services.tasks.queue import enqueue_task


def auth_header(user):
    # An die Pattern in tests/api/test_indeed_email_import.py anpassen:
    # grep -n "Authorization\|Bearer" tests/api/test_indeed_email_import.py
    from services.auth import generate_token  # Pfad ggf. anpassen
    return {'Authorization': f'Bearer {generate_token(user.id)}'}


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    u = User(id='u1', email='t@example.com', name='T')
    db.session.add(u)
    db.session.commit()
    return u


def test_get_task_returns_status(app, client, user):
    task_id = enqueue_task('test_noop', user.id, {'k': 'v'})
    resp = client.get(f'/api/tasks/{task_id}', headers=auth_header(user))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['id'] == task_id
    assert body['status'] == 'queued'
    assert body['type'] == 'test_noop'


def test_get_task_404_for_unknown(app, client, user):
    resp = client.get('/api/tasks/00000000-0000-0000-0000-000000000000',
                      headers=auth_header(user))
    assert resp.status_code == 404


def test_get_task_404_for_other_user(app, client, user):
    other = User(id='u2', email='o@example.com', name='O')
    db.session.add(other)
    db.session.commit()
    task_id = enqueue_task('test_noop', other.id, {})
    resp = client.get(f'/api/tasks/{task_id}', headers=auth_header(user))
    assert resp.status_code == 404
```

**Hinweis** zu `auth_header`: Vor dem Test ausführen
`grep -n "Authorization\|Bearer\|token_required" tests/api/test_indeed_email_import.py | head`
und das Pattern dort 1:1 kopieren.

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement endpoint**

`api/tasks.py`:
```python
"""Background-Tasks API: Status-Polling für asynchrone Jobs."""
from __future__ import annotations

from flask import Blueprint, jsonify

from database import db
from models import TaskQueue
from services.auth import token_required  # Pfad analog zu jobs_user.py

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


@tasks_bp.get('/<task_id>')
@token_required
def get_task(user, task_id: str):
    row = db.session.get(TaskQueue, task_id)
    if row is None or row.user_id != user.id:
        return jsonify({'error': 'Not Found'}), 404
    return jsonify(row.to_dict()), 200
```

In `app.py` (oder wo Blueprints registriert werden — `grep -n "register_blueprint" app.py`):
```python
from api.tasks import tasks_bp
app.register_blueprint(tasks_bp)
```

- [ ] **Step 4: Run tests, verify PASS**

```bash
venv/bin/pytest tests/api/test_tasks_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/tasks.py app.py tests/api/test_tasks_api.py
git commit -m "feat(tasks-api): GET /api/tasks/<id> status endpoint"
```

---

## Task 13: `GET /api/tasks` list endpoint

**Files:**
- Modify: `api/tasks.py`
- Modify: `tests/api/test_tasks_api.py`

- [ ] **Step 1: Failing test**

Anhängen an `test_tasks_api.py`:
```python
def test_list_tasks_returns_users_own(app, client, user):
    t1 = enqueue_task('test_noop', user.id, {})
    t2 = enqueue_task('test_noop', user.id, {})
    resp = client.get('/api/tasks', headers=auth_header(user))
    assert resp.status_code == 200
    ids = [t['id'] for t in resp.get_json()['tasks']]
    assert set(ids) == {t1, t2}


def test_list_tasks_filters_by_type(app, client, user):
    enqueue_task('test_noop', user.id, {})
    enqueue_task('other_type', user.id, {})
    resp = client.get('/api/tasks?type=test_noop', headers=auth_header(user))
    assert resp.status_code == 200
    types = [t['type'] for t in resp.get_json()['tasks']]
    assert types == ['test_noop']
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

Append to `api/tasks.py`:
```python
from flask import request
from sqlalchemy import desc


@tasks_bp.get('')
@token_required
def list_tasks(user):
    q = TaskQueue.query.filter_by(user_id=user.id)
    task_type = request.args.get('type')
    if task_type:
        q = q.filter_by(type=task_type)
    limit = min(int(request.args.get('limit', 20)), 100)
    rows = q.order_by(desc(TaskQueue.created_at)).limit(limit).all()
    return jsonify({'tasks': [r.to_dict() for r in rows]}), 200
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add api/tasks.py tests/api/test_tasks_api.py
git commit -m "feat(tasks-api): GET /api/tasks list endpoint"
```

---

## Task 14: `POST /api/tasks/<id>/cancel`

**Files:**
- Modify: `api/tasks.py`
- Modify: `tests/api/test_tasks_api.py`

- [ ] **Step 1: Failing tests**

```python
def test_cancel_queued_task(app, client, user):
    from models import TaskQueue
    task_id = enqueue_task('test_noop', user.id, {})
    resp = client.post(f'/api/tasks/{task_id}/cancel', headers=auth_header(user))
    assert resp.status_code == 200
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'cancelled'


def test_cancel_running_task_returns_409(app, client, user):
    from services.tasks.queue import pick_next_task
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    resp = client.post(f'/api/tasks/{task_id}/cancel', headers=auth_header(user))
    assert resp.status_code == 409
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

Append to `api/tasks.py`:
```python
from datetime import datetime


@tasks_bp.post('/<task_id>/cancel')
@token_required
def cancel_task(user, task_id: str):
    row = db.session.get(TaskQueue, task_id)
    if row is None or row.user_id != user.id:
        return jsonify({'error': 'Not Found'}), 404
    if row.status != 'queued':
        return jsonify({
            'error': f"Task ist {row.status}, kann nur 'queued' gecancelt werden"
        }), 409
    row.status = 'cancelled'
    row.finished_at = datetime.utcnow()
    db.session.commit()
    return jsonify(row.to_dict()), 200
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add api/tasks.py tests/api/test_tasks_api.py
git commit -m "feat(tasks-api): POST /api/tasks/<id>/cancel for queued tasks"
```

---

## Task 15: Admin-UI Section "Background Jobs"

**Files:**
- Modify: Admin-HTML-Datei (Pfad in Step 1 finden)
- Modify: Admin-JS-Datei

- [ ] **Step 1: Pfade finden**

```bash
find static/ -name '*admin*' -type f | head
grep -rln "Settings.*Admin\|admin.*tab\|adminTab" static/js/ 2>/dev/null | head
```
Notiere die Datei(en).

- [ ] **Step 2: HTML-Section anhängen**

Im Admin-Tab-Container neue Section ergänzen:
```html
<section id="bg-jobs-section">
  <h3>Background Jobs (Letzte 20)</h3>
  <button id="bg-jobs-refresh">Refresh</button>
  <table id="bg-jobs-table">
    <thead>
      <tr>
        <th>Type</th>
        <th>Status</th>
        <th>Created</th>
        <th>Duration</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</section>
```

- [ ] **Step 3: JS für Daten-Load (XSS-safe via textContent)**

In der zugehörigen JS-Datei:
```javascript
async function loadBackgroundJobs() {
  const res = await fetch('/api/tasks?limit=20', { headers: authHeaders() });
  if (!res.ok) return;
  const { tasks } = await res.json();
  const tbody = document.querySelector('#bg-jobs-table tbody');
  // Vorhandene Rows entfernen — alle Children löschen, kein innerHTML.
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

  for (const t of tasks) {
    const tr = document.createElement('tr');
    const duration = t.finished_at && t.started_at
      ? Math.round((new Date(t.finished_at) - new Date(t.started_at)) / 1000) + 's'
      : (t.started_at ? 'läuft …' : '—');

    function cell(text, className) {
      const td = document.createElement('td');
      if (className) td.className = className;
      td.textContent = text ?? '';
      return td;
    }

    tr.appendChild(cell(t.type));
    tr.appendChild(cell(t.status, 'status-' + t.status));
    tr.appendChild(cell(new Date(t.created_at).toLocaleString('de-DE')));
    tr.appendChild(cell(duration));
    tr.appendChild(cell(t.error ? t.error.slice(0, 100) : ''));
    tbody.appendChild(tr);
  }
}
document.getElementById('bg-jobs-refresh').addEventListener('click', loadBackgroundJobs);
// Beim Tab-Open ebenfalls aufrufen (an bestehendes Tab-Switch-Pattern anbinden).
```
`authHeaders` existiert bereits — von einer benachbarten Fetch-Funktion adaptieren wenn der Name lokal anders heißt.

- [ ] **Step 4: Service-Worker-Cache bumpen**

`static/service-worker.js`: `CACHE_NAME` inkrementieren (`v42` → `v43` o.ä., abhängig vom aktuellen Wert).

- [ ] **Step 5: Lokal verifizieren**

Dev-Server starten, Admin-Tab öffnen, leere Tabelle sollte erscheinen. Mit One-Liner aus Task 10 Step 2 einen test_noop enqueuen → Refresh → Row erscheint.

- [ ] **Step 6: Commit**

```bash
git add static/
git commit -m "feat(admin-ui): background jobs section in admin tab"
```

---

## Task 16: P1-Integration-Smoke auf Staging

- [ ] **Step 1: Deploy auf VPS**

```bash
git push origin master
ssh ionos-vps "/usr/local/bin/bewerbungen-deploy.sh"
```
Expected: pull, migration läuft (task_queue erstellt), bewerbungen + task-worker neu gestartet, smoke 200.

- [ ] **Step 2: Worker-Daemon hochfahren**

```bash
ssh ionos-vps "systemctl start bewerbungstracker-task-worker.service && \
  sleep 2 && systemctl status bewerbungstracker-task-worker.service --no-pager | head -15"
```
Expected: Active (running), 2 Subprozesse + 1 Master.

- [ ] **Step 3: Manuelle Enqueue auf VPS**

```bash
ssh ionos-vps "cd /var/www/bewerbungen && venv/bin/python -c \"
from app import create_app
app = create_app()
with app.app_context():
    from services.tasks.queue import enqueue_task
    from models import User
    u = User.query.filter(User.email != None).first()
    print('user:', u.email, 'task:', enqueue_task('test_noop', u.id, {'sleep_seconds': 5}))
\""
```

- [ ] **Step 4: Status in der UI**

Admin-Tab → Background-Jobs-Section → Refresh-Button. Job sollte als `queued`→`running`→`done` durchlaufen (mehrmals refreshen).

- [ ] **Step 5: Worker-Crash-Test**

```bash
ssh ionos-vps "systemctl kill -s SIGKILL bewerbungstracker-task-worker.service"
sleep 5
ssh ionos-vps "systemctl start bewerbungstracker-task-worker.service"
sleep 70
ssh ionos-vps "sqlite3 /var/www/bewerbungen/instance/bewerbungen.db \
  'SELECT id, status, attempts FROM task_queue ORDER BY created_at DESC LIMIT 5;'"
```
Expected: zuvor-running-Tasks haben `attempts=2` und `status=done` (oder running mit frischem heartbeat).

- [ ] **Step 6: Logs prüfen wenn Probleme**

```bash
ssh ionos-vps "journalctl -u bewerbungstracker-task-worker -n 100 --no-pager"
```

---

# PHASE 2: `/import-from-email` async migrieren

## Task 17: Handler-Extraktion in `services/tasks/handlers/email_import.py`

**Files:**
- Create: `services/tasks/handlers/email_import.py`
- Create: `tests/services/tasks/test_handlers_email_import.py`
- Modify: `services/tasks/handlers/__init__.py`

- [ ] **Step 1: Quelle lesen**

`api/jobs_user.py:1015-1148` (Funktion `import_from_email`). Die Logik wandert; die Request/Response-Hülle fällt weg.

- [ ] **Step 2: Failing test**

`tests/services/tasks/test_handlers_email_import.py`:
```python
import pytest
from app import create_app
from database import db
from models import User, JobSource
from services.tasks.handlers.email_import import handle_email_import


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def user(app):
    u = User(id='u1', email='t@example.com', name='T')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def indeed_source(app, user):
    src = JobSource(
        user_id=user.id, name='Indeed', type='email_indeed',
        config={'folder': 'INBOX'}, enabled=True,
    )
    db.session.add(src)
    db.session.commit()
    return src


def test_handle_email_import_apps_script_mode(app, user, indeed_source):
    """Apps-Script-Mode: keine IMAP-Connection."""
    payload = {
        'user_id': user.id,
        'source_id': indeed_source.id,
        'emails': [{
            'message_id': 'm1',
            'subject': 'New Indeed Job: Python Dev at Acme',
            'from': 'jobs@indeed.com',
            'body': '<a href="https://indeed.com/jobs/123">Python Dev at Acme - Berlin</a>',
        }],
    }
    result = handle_email_import(payload, progress_cb=None)
    assert 'imported' in result
    assert 'total_emails' in result
    assert result['fetch_mode'] == 'apps_script'
```

- [ ] **Step 3: Run, verify FAIL**

- [ ] **Step 4: Implement handler**

`services/tasks/handlers/email_import.py`:
```python
"""Async-Handler für /import-from-email. Logik 1:1 aus api/jobs_user.py."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from database import db
from models import User, JobSource
from services.job_sources import get_adapter, dedup as _dedup
from services.tasks.registry import register


@register('email_import')
def handle_email_import(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt einen Email-Import durch.

    Payload-Format:
        user_id (str): UUID des Users.
        source_id (int): JobSource.id.
        emails (list[dict], optional): Apps-Script-Mode.
        script_url (str, optional): Apps-Script-Proxy-Mode.
        force_refresh (bool, optional): default False.

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    """
    user = User.query.get(payload['user_id'])
    src = JobSource.query.get(payload['source_id'])
    if user is None:
        raise ValueError(f"user_id {payload['user_id']!r} nicht gefunden")
    if src is None or src.user_id != user.id:
        raise ValueError(f"source_id {payload['source_id']!r} nicht zugänglich")

    provided_emails = payload.get('emails')
    script_url = payload.get('script_url')
    force_refresh = bool(payload.get('force_refresh'))

    if progress_cb:
        progress_cb(5, 'fetching')

    cache_hit = False
    adapter = get_adapter(src.type, src.config, user=user)
    adapter._source_id_for_tracking = src.id
    if isinstance(provided_emails, list):
        fetched = adapter.parse_emails(provided_emails)
        fetch_mode = 'apps_script'
    elif isinstance(script_url, str) and script_url:
        from api.jobs_user import _fetch_apps_script_emails
        emails, cache_hit = _fetch_apps_script_emails(
            script_url, user_id=user.id, use_cache=not force_refresh,
        )
        fetched = adapter.parse_emails(emails)
        fetch_mode = 'apps_script_proxy'
    else:
        fetched = adapter.fetch()
        fetch_mode = 'imap'

    if progress_cb:
        progress_cb(60, f'parsed {len(fetched)} jobs')

    src.consecutive_failures = 0
    src.last_error = None

    existing_urls = _dedup.get_existing_job_urls()
    fresh = _dedup.deduplicate(fetched, existing_urls)
    duplicates_count = len(fetched) - len(fresh)

    window_days = int(user.job_reject_window_days or 180)
    reject_enabled = bool(user.job_reject_filter_enabled)
    from api.jobs_user import _get_rejected_companies_lower
    rejected_companies = (
        _get_rejected_companies_lower(user.id, window_days) if reject_enabled else set()
    )

    new_for_dialog: list[dict] = []
    blocked_for_dialog: list[dict] = []
    for fjob in fresh:
        company_lower = (fjob.company or '').strip().lower()
        is_blocked = bool(company_lower) and company_lower in rejected_companies
        payload_job = {
            'title': fjob.title, 'company': fjob.company, 'location': fjob.location,
            'url': fjob.url, 'external_id': fjob.external_id,
            'description': fjob.description, 'raw': fjob.raw or {},
        }
        if is_blocked:
            blocked_for_dialog.append(payload_job)
        else:
            new_for_dialog.append(payload_job)

    if progress_cb:
        progress_cb(85, 'persisting')

    from api.jobs_user import _create_raw_job_and_match
    imported_count = 0
    for payload_job in new_for_dialog:
        raw, match = _create_raw_job_and_match(
            src, user.id, payload_job, match_status='new',
        )
        if raw is not None and match is not None:
            imported_count += 1
        else:
            duplicates_count += 1

    src.last_crawled_at = datetime.utcnow()
    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        'imported': imported_count,
        'blocked': blocked_for_dialog,
        'duplicates': duplicates_count,
        'total_emails': len(fetched),
        'rejection_window_days': window_days,
        'reject_filter_enabled': reject_enabled,
        'fetch_mode': fetch_mode,
        'cache_hit': cache_hit,
    }
```

`services/tasks/handlers/__init__.py` ergänzen:
```python
from services.tasks.handlers import test_noop  # noqa: F401
from services.tasks.handlers import email_import  # noqa: F401
```

- [ ] **Step 5: Run test, verify PASS**

```bash
venv/bin/pytest tests/services/tasks/test_handlers_email_import.py -v
```

- [ ] **Step 6: Bestehende Email-Import-Tests prüfen** (sollten noch grün sein)

```bash
venv/bin/pytest tests/api/test_indeed_email_import.py -v
```
Expected: 37/37 PASS.

- [ ] **Step 7: Commit**

```bash
git add services/tasks/handlers/ tests/services/tasks/test_handlers_email_import.py
git commit -m "feat(tasks): email_import handler — logic extracted from api/jobs_user.py"
```

---

## Task 18: Endpoint `/import-from-email` auf Enqueue umstellen

**Files:**
- Modify: `api/jobs_user.py:1015-1148`
- Modify: `tests/api/test_indeed_email_import.py`

- [ ] **Step 1: Endpoint umschreiben**

In `api/jobs_user.py`, ersetze die `import_from_email`-Funktion komplett durch:

```python
@jobs_user_bp.post('/sources/<int:source_id>/import-from-email')
@token_required
def import_from_email(user, source_id: int):
    """Enqueued einen email_import-Task und returnt 202 + task_id.

    Frontend pollt anschließend GET /api/tasks/<id>. Die eigentliche
    Logik lebt in services/tasks/handlers/email_import.py.
    """
    from services.tasks.queue import enqueue_task

    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    if not _is_email_source_type(src.type):
        return jsonify({"error": f"Source ist kein Email-Typ (ist '{src.type}')"}), 400

    payload = request.get_json(silent=True) or {}
    task_payload = {
        'user_id': user.id,
        'source_id': src.id,
        'emails': payload.get('emails'),
        'script_url': payload.get('script_url'),
        'force_refresh': bool(payload.get('force_refresh')),
    }
    task_id = enqueue_task('email_import', user.id, task_payload)
    return jsonify({
        'task_id': task_id,
        'status': 'queued',
    }), 202
```

- [ ] **Step 2: Test-Helper anlegen**

In `tests/api/test_indeed_email_import.py` oben einfügen:
```python
def _run_enqueued_handler_sync(client_response):
    """Führt den gerade enqueueten Handler synchron aus, returnt result-dict."""
    import json
    from models import TaskQueue
    from services.tasks.handlers.email_import import handle_email_import
    task_id = client_response.get_json()['task_id']
    row = db.session.get(TaskQueue, task_id)
    return handle_email_import(json.loads(row.payload), progress_cb=None)
```

- [ ] **Step 3: Tests refactoren**

Pattern für jeden Test, der vorher `r.get_json()['imported']` etc. prüfte:

VORHER:
```python
r = client.post(f"/api/jobs/sources/{indeed_source.id}/import-from-email", headers=headers)
assert r.status_code == 200
data = r.get_json()
assert data['imported'] == 2
```

NACHHER:
```python
r = client.post(f"/api/jobs/sources/{indeed_source.id}/import-from-email", headers=headers)
assert r.status_code == 202
data = _run_enqueued_handler_sync(r)
assert data['imported'] == 2
```

Tests, die nur Pre-Enqueue-Errors prüfen (`403 Forbidden`, `400 Bad Source-Type`), bleiben unverändert.

Liste der zu ändernden Test-Funktionen aus dem File ableiten (`grep -n "def test_" tests/api/test_indeed_email_import.py`). Vermutlich ~15 von 37.

- [ ] **Step 4: Run all tests**

```bash
venv/bin/pytest tests/api/test_indeed_email_import.py -v
```
Expected: 37/37 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_indeed_email_import.py
git commit -m "feat(email-import): endpoint enqueues task instead of sync execution"
```

---

## Task 19: Frontend-Polling-Logik

**Files:**
- Create: `static/js/task-poller.js`
- Modify: bestehende JS-Datei mit Email-Import-Trigger
- Modify: HTML-Datei (script-Tag für task-poller.js)
- Modify: `static/service-worker.js` (CACHE_NAME bump)

- [ ] **Step 1: Trigger-Stelle finden**

```bash
grep -rln "import-from-email\|importFromEmail" static/ | head
```

- [ ] **Step 2: Polling-Helper schreiben**

`static/js/task-poller.js`:
```javascript
/**
 * Polled einen Task bis er done/failed/cancelled ist.
 * @param {string} taskId
 * @param {(task: object) => void} onProgress
 * @returns {Promise<object>} final result-payload
 */
async function pollTask(taskId, onProgress) {
  const startMs = Date.now();
  let interval = 2000;
  while (true) {
    const res = await fetch(`/api/tasks/${taskId}`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Task fetch failed: ${res.status}`);
    const task = await res.json();
    if (onProgress) onProgress(task);
    if (task.status === 'done') return task.result;
    if (task.status === 'failed') throw new Error(task.error || 'Task failed');
    if (task.status === 'cancelled') throw new Error('Task cancelled');
    if (Date.now() - startMs > 30_000) interval = 5000;
    await new Promise(r => setTimeout(r, interval));
  }
}
```

In der HTML-Datei das Script einbinden (vor der Datei mit dem Import-Trigger):
```html
<script src="/static/js/task-poller.js"></script>
```

- [ ] **Step 3: Import-Trigger umschreiben**

Im File aus Step 1, an der Stelle wo aktuell `fetch('/api/jobs/sources/.../import-from-email')` aufgerufen wird:

```javascript
// VORHER (Sync):
const res = await fetch(`/api/jobs/sources/${sourceId}/import-from-email`, {
  method: 'POST', headers: authHeaders(), body: JSON.stringify(body),
});
const data = await res.json();
renderImportResult(data);

// NACHHER (Async + Poll):
const enqRes = await fetch(`/api/jobs/sources/${sourceId}/import-from-email`, {
  method: 'POST', headers: authHeaders(), body: JSON.stringify(body),
});
if (enqRes.status !== 202) {
  const err = await enqRes.json().catch(() => ({}));
  showError(err.error || `Unerwarteter Status ${enqRes.status}`);
  return;
}
const { task_id } = await enqRes.json();
showSpinner('Importiere …');
try {
  const result = await pollTask(task_id, task => {
    if (task.progress) updateSpinner(`${task.progress}%`);
  });
  renderImportResult(result);  // gleiches result-Shape wie früher
} catch (err) {
  showError(err.message);
} finally {
  hideSpinner();
}
```

`showSpinner`/`updateSpinner`/`hideSpinner`/`showError`/`renderImportResult` an die bestehenden Funktionsnamen anpassen (vermutlich existieren ähnliche; ggf. inline minimal implementieren).

- [ ] **Step 4: Service-Worker-Cache bumpen**

`static/service-worker.js`: `CACHE_NAME` inkrementieren.

- [ ] **Step 5: Lokal im Browser testen**

Dev-Server starten, einloggen, Email-Source importieren. Erwartung: Spinner zeigt Progress, danach Result-Dialog wie früher.

- [ ] **Step 6: Commit**

```bash
git add static/
git commit -m "feat(frontend): poll task status after import-from-email enqueue"
```

---

## Task 20: P2-Deploy + E2E + Monitoring

- [ ] **Step 1: Pre-Deploy-Tests**

```bash
venv/bin/pytest tests/api/test_indeed_email_import.py tests/services/tasks/ tests/api/test_tasks_api.py -v
```
Expected: alle PASS.

- [ ] **Step 2: Push + Deploy**

```bash
git push origin master
ssh ionos-vps "/usr/local/bin/bewerbungen-deploy.sh"
```

- [ ] **Step 3: Worker-Status**

```bash
ssh ionos-vps "systemctl status bewerbungstracker-task-worker.service --no-pager | head -15"
```
Expected: active, 2 Worker-Subprozesse.

- [ ] **Step 4: E2E im Browser**

Auf https://bewerbung.wolfinisoftware.de eine Email-Source importieren.
- Erwartung: 202 + Spinner sofort
- Erwartung: kein 502 selbst bei langsamem Folder
- Erwartung: nach <60s Result-Dialog wie früher

- [ ] **Step 5: Sofort-Monitoring**

```bash
ssh ionos-vps "journalctl -u bewerbungstracker-task-worker.service --since '15 min ago' | \
  grep -iE 'email_import|done|failed' | tail -30"
```

```bash
ssh ionos-vps "sqlite3 /var/www/bewerbungen/instance/bewerbungen.db \
  'SELECT type, status, attempts, datetime(created_at) FROM task_queue \
   ORDER BY created_at DESC LIMIT 10;'"
```

- [ ] **Step 6: 24h-Beobachtung**

```bash
ssh ionos-vps "grep -c 'AH01102.*import-from-email' /var/log/httpd/bewerbungen_error.log"
ssh ionos-vps "sqlite3 /var/www/bewerbungen/instance/bewerbungen.db \
  \"SELECT status, COUNT(*) FROM task_queue WHERE type='email_import' GROUP BY status;\""
```
Erwartung: 502er für `import-from-email` = 0. Tasks sind `done` (oder vereinzelt `failed` mit klarer error-message statt 502).

---

## Done-Definition

- ✅ `task_queue`-Tabelle in Prod
- ✅ `bewerbungstracker-task-worker.service` läuft (2 Worker)
- ✅ 3 `/api/tasks/*`-Endpoints + Tests grün
- ✅ Admin-UI zeigt Background-Jobs
- ✅ `/import-from-email` retourniert 202 + task_id
- ✅ Frontend pollt + rendert wie früher
- ✅ Bestehende 37 indeed-email-import-Tests grün
- ✅ Keine 502er für `/import-from-email` über 24h

P3 (weitere User-Endpoints) und P4 (Cron in Queue) folgen als eigene Specs.
