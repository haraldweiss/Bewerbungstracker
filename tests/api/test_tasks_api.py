# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests for GET /api/tasks/<id> endpoint."""
import pytest
from database import db
from models import User, TaskQueue
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


def test_list_tasks_returns_users_own(client, auth_header):
    """GET /api/tasks returns user's own tasks."""
    headers, user = auth_header
    t1 = enqueue_task('test_noop', user.id, {})
    t2 = enqueue_task('test_noop', user.id, {})
    resp = client.get('/api/tasks', headers=headers)
    assert resp.status_code == 200
    ids = [t['id'] for t in resp.get_json()['tasks']]
    assert set(ids) == {t1, t2}


def test_list_tasks_filters_by_type(client, auth_header):
    """GET /api/tasks?type=<type> filters by task type."""
    headers, user = auth_header
    enqueue_task('test_noop', user.id, {})
    enqueue_task('other_type', user.id, {})
    resp = client.get('/api/tasks?type=test_noop', headers=headers)
    assert resp.status_code == 200
    types = [t['type'] for t in resp.get_json()['tasks']]
    assert types == ['test_noop']


def test_cancel_queued_task(client, auth_header):
    """POST /api/tasks/<id>/cancel transitions queued task to cancelled."""
    headers, user = auth_header
    task_id = enqueue_task('test_noop', user.id, {})
    resp = client.post(f'/api/tasks/{task_id}/cancel', headers=headers)
    assert resp.status_code == 200
    row = db.session.get(TaskQueue, task_id)
    assert row.status == 'cancelled'


def test_cancel_running_task_returns_409(client, auth_header):
    """POST /api/tasks/<id>/cancel returns 409 if task is already running."""
    from services.tasks.queue import pick_next_task
    headers, user = auth_header
    task_id = enqueue_task('test_noop', user.id, {})
    pick_next_task(worker_id='w1')
    resp = client.post(f'/api/tasks/{task_id}/cancel', headers=headers)
    assert resp.status_code == 409
