# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Background-Tasks API: Status-Polling für asynchrone Jobs."""
from __future__ import annotations

from flask import Blueprint, jsonify

from database import db
from models import TaskQueue
from api.auth import token_required

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


@tasks_bp.get('/<task_id>')
@token_required
def get_task(user, task_id: str):
    """Return the status of a task by ID.

    Args:
        user: Authenticated user (from @token_required)
        task_id: UUID of the task

    Returns:
        200 + task dict if found and belongs to user
        404 if not found or belongs to other user
    """
    row = db.session.get(TaskQueue, task_id)
    if row is None or row.user_id != user.id:
        return jsonify({'error': 'Not Found'}), 404
    return jsonify(row.to_dict()), 200
