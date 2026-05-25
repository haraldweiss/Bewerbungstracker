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
