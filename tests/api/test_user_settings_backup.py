# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für die Backup-Provider-Erweiterung von /api/providers/user/settings."""
import os
import pytest
from unittest.mock import patch


def _auth(user_factory, is_admin=False):
    from auth_service import AuthService
    u = user_factory(is_admin=is_admin)
    token = AuthService.create_access_token(u.id)
    return {"Authorization": f"Bearer {token}"}, u


def test_get_returns_backup_fields(client, user_factory):
    headers, _ = _auth(user_factory)
    r = client.get('/api/providers/user/settings', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert 'backup_provider' in body
    assert 'backup_model' in body
    assert 'backup_auto' in body
    # Non-Admin ohne Setting → alles None/False
    assert body['backup_provider'] is None
    assert body['backup_model'] is None
    assert body['backup_auto'] is False


def test_get_admin_with_env_returns_auto_true(client, user_factory):
    headers, _ = _auth(user_factory, is_admin=True)
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test'}):
        r = client.get('/api/providers/user/settings', headers=headers)
    body = r.get_json()
    assert body['backup_provider'] == 'claude'
    assert body['backup_auto'] is True


def test_patch_sets_backup(client, user_factory):
    headers, user = _auth(user_factory)
    r = client.patch('/api/providers/user/settings', json={
        'backup_provider': 'ollama',
        'backup_model': 'qwen3-coder:30b',
    }, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['backup_provider'] == 'ollama'
    assert body['backup_model'] == 'qwen3-coder:30b'
    assert body['backup_auto'] is False


def test_patch_with_null_clears_backup(client, user_factory):
    headers, user = _auth(user_factory)
    # Erst setzen
    client.patch('/api/providers/user/settings', json={
        'backup_provider': 'ollama', 'backup_model': 'qwen3-coder:30b',
    }, headers=headers)
    # Dann löschen
    r = client.patch('/api/providers/user/settings', json={
        'backup_provider': None,
        'backup_model': None,
    }, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['backup_provider'] is None
    assert body['backup_model'] is None
    assert body['backup_auto'] is False


def test_patch_null_for_admin_falls_back_to_auto(client, user_factory):
    """Admin löscht eigenes Backup → backup_auto=True kommt zurück (env-Default)."""
    headers, user = _auth(user_factory, is_admin=True)
    # Zuerst explizit setzen
    client.patch('/api/providers/user/settings', json={
        'backup_provider': 'ollama', 'backup_model': 'qwen3-coder:30b',
    }, headers=headers)
    # Dann löschen — Admin fällt auf env-Default zurück
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test'}):
        r = client.patch('/api/providers/user/settings', json={
            'backup_provider': None, 'backup_model': None,
        }, headers=headers)
    body = r.get_json()
    assert body['backup_provider'] == 'claude'
    assert body['backup_auto'] is True


def test_patch_invalid_backup_provider_rejected(client, user_factory):
    headers, _ = _auth(user_factory)
    r = client.patch('/api/providers/user/settings', json={
        'backup_provider': 'unknown-provider',
        'backup_model': 'foo',
    }, headers=headers)
    assert r.status_code == 400
    assert 'Backup' in r.get_json()['error'] or 'Unbekannter' in r.get_json()['error']


def test_patch_primary_only_does_not_touch_backup(client, user_factory):
    """PATCH ohne backup_* Felder ändert das Backup nicht."""
    headers, user = _auth(user_factory)
    # Backup explizit setzen
    client.patch('/api/providers/user/settings', json={
        'backup_provider': 'ollama', 'backup_model': 'qwen3-coder:30b',
    }, headers=headers)
    # Nur Primary updaten
    r = client.patch('/api/providers/user/settings', json={
        'provider': 'claude',
        'model': 'claude-opus-4-7',
    }, headers=headers)
    body = r.get_json()
    assert body['provider'] == 'claude'
    assert body['model'] == 'claude-opus-4-7'
    # Backup bleibt erhalten
    assert body['backup_provider'] == 'ollama'
    assert body['backup_model'] == 'qwen3-coder:30b'


# --- Adaptive-Learning Settings (Task 9) -----------------------------------

def test_patch_settings_updates_learn_fields(client, user_factory):
    """Settings-PATCH speichert Adaptive-Learning Felder."""
    headers, user = _auth(user_factory)
    resp = client.patch(
        '/api/providers/user/settings',
        json={
            "job_learn_enabled": False,
            "job_learn_min_samples": 5,
            "job_learn_weight_pct": 50,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    from models import User
    from database import db
    updated = db.session.query(User).get(user.id)
    assert updated.job_learn_enabled is False
    assert updated.job_learn_min_samples == 5
    assert updated.job_learn_weight_pct == 50


def test_patch_settings_validates_weight_pct(client, user_factory):
    """weight_pct > 100 → 400."""
    headers, _ = _auth(user_factory)
    resp = client.patch(
        '/api/providers/user/settings',
        json={"job_learn_weight_pct": 150},
        headers=headers,
    )
    assert resp.status_code == 400


def test_patch_settings_validates_min_samples(client, user_factory):
    """min_samples = 0 → 400."""
    headers, _ = _auth(user_factory)
    resp = client.patch(
        '/api/providers/user/settings',
        json={"job_learn_min_samples": 0},
        headers=headers,
    )
    assert resp.status_code == 400
