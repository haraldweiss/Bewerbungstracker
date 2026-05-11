# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für /api/profile/feature-models Endpoints."""
import json
import pytest


def test_get_without_auth_returns_401(client):
    r = client.get('/api/profile/feature-models')
    assert r.status_code == 401


def test_get_returns_standard_and_empty_overrides(client, auth_header):
    headers, user = auth_header
    r = client.get('/api/profile/feature-models', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert 'standard' in body
    assert body['standard']['provider'] == user.ai_provider
    assert body['standard']['model'] == user.ai_provider_model
    assert body['overrides'] == {}


def test_patch_sets_override(client, auth_header):
    headers, user = auth_header
    payload = {'overrides': {
        'cover_letter': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    }}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'updated'
    assert body['overrides']['cover_letter']['provider'] == 'claude'

    r2 = client.get('/api/profile/feature-models', headers=headers)
    assert r2.get_json()['overrides']['cover_letter']['model'] == 'claude-haiku-4-5-20251001'


def test_patch_with_null_removes_override(client, auth_header, db_session):
    headers, user = auth_header
    user.feature_model_overrides = json.dumps({
        'match': {'provider': 'ollama', 'model': 'mistral-nemo:12b'},
    })
    db_session.commit()

    payload = {'overrides': {'match': None}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['overrides'] == {}


def test_patch_unknown_feature_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'unknown_feature': {'provider': 'claude'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400
    assert 'Unbekanntes Feature' in r.get_json()['error']


def test_patch_unknown_provider_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'match': {'provider': 'gpt-5-fake'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400
    assert 'unbekannter Provider' in r.get_json()['error']


def test_patch_non_dict_override_returns_400(client, auth_header):
    headers, _ = auth_header
    payload = {'overrides': {'match': 'not-a-dict'}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 400


def test_patch_overrides_not_dict_returns_400(client, auth_header):
    headers, _ = auth_header
    r = client.patch('/api/profile/feature-models', json={'overrides': 'foo'}, headers=headers)
    assert r.status_code == 400


def test_patch_empty_provider_string_does_not_save(client, auth_header):
    """Leerer Provider-String wird als 'nicht setzen' interpretiert."""
    headers, _ = auth_header
    payload = {'overrides': {'match': {'provider': '', 'model': 'foo'}}}
    r = client.patch('/api/profile/feature-models', json=payload, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['overrides'] == {}


def test_user_isolation(client, auth_header, user_factory, db_session):
    """User A sieht nicht die Overrides von User B."""
    headers_a, _ = auth_header
    user_b = user_factory()
    user_b.feature_model_overrides = json.dumps({
        'match': {'provider': 'ollama', 'model': 'should-not-leak'},
    })
    db_session.commit()

    r = client.get('/api/profile/feature-models', headers=headers_a)
    overrides = r.get_json()['overrides']
    assert 'match' not in overrides or overrides['match'].get('model') != 'should-not-leak'
