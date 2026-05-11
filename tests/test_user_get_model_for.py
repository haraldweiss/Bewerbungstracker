# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für User.get_model_for() Helper."""
import json
import pytest
from models import User


def make_user(ai_provider='claude', ai_provider_model='claude-haiku-4-5-20251001',
              overrides=None):
    u = User(
        email='test@example.com',
        password_hash='x',
        ai_provider=ai_provider,
        ai_provider_model=ai_provider_model,
        feature_model_overrides=(json.dumps(overrides) if overrides is not None else None),
    )
    return u


def test_fallback_when_no_overrides():
    u = make_user()
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_fallback_when_overrides_empty():
    u = make_user(overrides={})
    assert u.get_model_for('cover_letter') == ('claude', 'claude-haiku-4-5-20251001')


def test_override_returned_when_present():
    u = make_user(overrides={
        'match': {'provider': 'ollama', 'model': 'mistral-nemo:12b'},
    })
    assert u.get_model_for('match') == ('ollama', 'mistral-nemo:12b')


def test_override_with_only_provider_returns_none_model():
    u = make_user(overrides={
        'cover_letter': {'provider': 'claude'},
    })
    assert u.get_model_for('cover_letter') == ('claude', None)


def test_override_null_falls_back():
    u = make_user(overrides={'match': None})
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_override_for_different_feature_does_not_affect_others():
    u = make_user(overrides={
        'cover_letter': {'provider': 'ollama', 'model': 'qwen2.5:32b'},
    })
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')
    assert u.get_model_for('cover_letter') == ('ollama', 'qwen2.5:32b')


def test_malformed_json_falls_back():
    u = User(
        email='t@t.de', password_hash='x',
        ai_provider='claude', ai_provider_model='claude-haiku-4-5-20251001',
        feature_model_overrides='{this is: not json',
    )
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')


def test_unknown_feature_falls_back():
    u = make_user(overrides={'match': {'provider': 'ollama', 'model': 'm'}})
    assert u.get_model_for('unknown_feature') == ('claude', 'claude-haiku-4-5-20251001')


def test_empty_provider_in_override_falls_back():
    u = make_user(overrides={'match': {'provider': '', 'model': 'foo'}})
    assert u.get_model_for('match') == ('claude', 'claude-haiku-4-5-20251001')
