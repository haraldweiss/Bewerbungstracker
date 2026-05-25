# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests for GET /api/tasks/<id> endpoint."""
import pytest
from database import db
from models import User
from services.tasks.queue import enqueue_task


def test_get_task_returns_status(client, auth_header):
    """GET /api/tasks/<id> returns the task status."""
    headers, user = auth_header
    task_id = enqueue_task('test_noop', user.id, {'k': 'v'})
    resp = client.get(f'/api/tasks/{task_id}', headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['id'] == task_id
    assert body['status'] == 'queued'
    assert body['type'] == 'test_noop'


def test_get_task_404_for_unknown(client, auth_header):
    """GET /api/tasks/<unknown_id> returns 404."""
    headers, _ = auth_header
    resp = client.get('/api/tasks/00000000-0000-0000-0000-000000000000',
                      headers=headers)
    assert resp.status_code == 404


def test_get_task_404_for_other_user(client, auth_header, user_factory):
    """GET /api/tasks/<other_user_task_id> returns 404 (unauthorized access)."""
    headers, user = auth_header
    other_user = user_factory(email='other@test.de')
    task_id = enqueue_task('test_noop', other_user.id, {})
    resp = client.get(f'/api/tasks/{task_id}', headers=headers)
    assert resp.status_code == 404
