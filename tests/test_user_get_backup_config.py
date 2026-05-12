# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für User.get_backup_config() Helper.

Verifiziert die Backup-/Fallback-Provider-Logik:
- Explizit gesetzt → (provider, model, False)
- Admin ohne Setting + env CLAUDE_API_KEY → ('claude', default, True)
- Non-Admin ohne Setting → None (egal ob env gesetzt)
"""
import os
import pytest
from unittest.mock import patch
from models import User


def make_user(is_admin=False, ai_provider_backup=None, ai_provider_backup_model=None):
    return User(
        email='test@example.com',
        password_hash='x',
        is_admin=is_admin,
        ai_provider_backup=ai_provider_backup,
        ai_provider_backup_model=ai_provider_backup_model,
    )


def test_admin_without_config_with_env_key():
    """Admin ohne explizite Backup-Config + env CLAUDE_API_KEY → ('claude', default, True)."""
    u = make_user(is_admin=True)
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test', 'CLAUDE_DEFAULT_MODEL': 'claude-haiku-4-5-20251001'}):
        result = u.get_backup_config()
    assert result == ('claude', 'claude-haiku-4-5-20251001', True)


def test_admin_without_config_uses_default_model_when_env_missing():
    """Admin: env CLAUDE_DEFAULT_MODEL fehlt → fallback auf claude-haiku-4-5-20251001."""
    u = make_user(is_admin=True)
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test'}, clear=False):
        # Sicherstellen dass CLAUDE_DEFAULT_MODEL nicht gesetzt ist
        os.environ.pop('CLAUDE_DEFAULT_MODEL', None)
        result = u.get_backup_config()
    assert result == ('claude', 'claude-haiku-4-5-20251001', True)


def test_admin_with_explicit_config_overrides_env():
    """Admin mit explizitem ai_provider_backup → DB-Werte (NICHT env-default)."""
    u = make_user(is_admin=True, ai_provider_backup='ollama', ai_provider_backup_model='qwen3-coder:30b')
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test'}):
        result = u.get_backup_config()
    assert result == ('ollama', 'qwen3-coder:30b', False)


def test_non_admin_without_config_returns_none():
    """Non-Admin ohne Backup-Config → None, egal ob env-Key gesetzt ist."""
    u = make_user(is_admin=False)
    with patch.dict(os.environ, {'CLAUDE_API_KEY': 'sk-ant-test'}):
        result = u.get_backup_config()
    assert result is None


def test_non_admin_with_config_returns_db_values():
    """Non-Admin mit Backup-Config → DB-Werte."""
    u = make_user(is_admin=False, ai_provider_backup='openai', ai_provider_backup_model='gpt-4o')
    result = u.get_backup_config()
    assert result == ('openai', 'gpt-4o', False)


def test_admin_without_env_returns_none():
    """Admin ohne explizite Config UND ohne env → None (kein Backup)."""
    u = make_user(is_admin=True)
    with patch.dict(os.environ, {}, clear=True):
        result = u.get_backup_config()
    assert result is None


def test_backup_with_provider_but_no_model():
    """ai_provider_backup gesetzt, model NULL → returns (provider, None, False)."""
    u = make_user(is_admin=False, ai_provider_backup='claude', ai_provider_backup_model=None)
    result = u.get_backup_config()
    assert result == ('claude', None, False)
