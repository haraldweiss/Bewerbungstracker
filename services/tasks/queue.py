# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
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
    """Schreibt eine neue Job-Row, returnt task_id.

    Args:
        task_type: Type of task (e.g., 'test_noop', 'job_match', etc.)
        user_id: Owner of the task
        payload: Task parameters as dict (will be JSON-encoded)
        max_attempts: Maximum number of retry attempts (default 3)
        priority: Priority queue value (default 0, higher = more urgent)

    Returns:
        task_id (UUID string) of the newly created TaskQueue row
    """
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
