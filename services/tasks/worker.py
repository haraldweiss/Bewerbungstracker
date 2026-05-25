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
