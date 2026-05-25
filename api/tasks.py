# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Background-Tasks API: Status-Polling für asynchrone Jobs."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import desc

from database import db
from models import TaskQueue
from api.auth import token_required

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


@tasks_bp.get('')
@token_required
def list_tasks(user):
    """Return a list of tasks for the authenticated user.

    Query parameters:
        type: Filter by task type (optional)
        limit: Max tasks to return, capped at 100 (default: 20)

    Returns:
        200 + {'tasks': [task_dict, ...]}
    """
    q = TaskQueue.query.filter_by(user_id=user.id)
    task_type = request.args.get('type')
    if task_type:
        q = q.filter_by(type=task_type)
    limit = min(int(request.args.get('limit', 20)), 100)
    rows = q.order_by(desc(TaskQueue.created_at)).limit(limit).all()
    return jsonify({'tasks': [r.to_dict() for r in rows]}), 200


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
