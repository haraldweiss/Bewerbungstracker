# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für Modell-Validierung in /api/providers/user/settings PATCH.

Verhindert dass nicht-existente Modelle (z.B. 'qwen3.6:latest', umbenannte Claude-Modelle)
in user.ai_provider_model gespeichert werden.
"""
from unittest.mock import patch, MagicMock


def _auth(user_factory, is_admin=False):
    from auth_service import AuthService
    u = user_factory(is_admin=is_admin)
    token = AuthService.create_access_token(u.id)
    return {"Authorization": f"Bearer {token}"}, u


def _mock_service_with_models(models_by_provider):
    """Patcht ai_provider_client so, dass get_models() definierte Listen liefert."""
    mock_client = MagicMock()
    mock_client.get_models.side_effect = lambda provider, user_id=None: models_by_provider.get(provider, [])
    mock_client.get_config.return_value = {'configured': True}
    is_enabled = patch('api.providers.ai_provider_client.is_enabled', return_value=True)
    get_client = patch('api.providers.ai_provider_client.get_client', return_value=mock_client)
    return is_enabled, get_client


def test_patch_invalid_model_rejected(client, user_factory):
    """Ungültiges Primary-Modell → 400 mit hilfreicher Nachricht."""
    headers, _ = _auth(user_factory)
    is_enabled, get_client = _mock_service_with_models({
        'ollama': ['qwen2.5:latest', 'llama3:8b'],
    })
    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'ollama',
            'model': 'qwen3.6:latest',  # existiert nicht
        }, headers=headers)
    assert r.status_code == 400
    err = r.get_json()['error']
    assert 'qwen3.6:latest' in err
    assert 'ollama' in err
    # Verfügbare Modelle werden gelistet
    assert 'qwen2.5:latest' in err or 'llama3:8b' in err


def test_patch_valid_model_accepted(client, user_factory):
    """Gültiges Modell wird akzeptiert."""
    headers, _ = _auth(user_factory)
    is_enabled, get_client = _mock_service_with_models({
        'ollama': ['qwen2.5:latest', 'llama3:8b'],
    })
    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'ollama',
            'model': 'qwen2.5:latest',
        }, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['provider'] == 'ollama'
    assert body['model'] == 'qwen2.5:latest'


def test_patch_invalid_backup_model_rejected(client, user_factory):
    """Ungültiges Backup-Modell → 400."""
    headers, _ = _auth(user_factory)
    is_enabled, get_client = _mock_service_with_models({
        'claude': ['claude-haiku-4-5-20251001', 'claude-opus-4-7'],
    })
    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'backup_provider': 'claude',
            'backup_model': 'claude-3-5-sonnet-20241022',  # alt, gibts nicht mehr
        }, headers=headers)
    assert r.status_code == 400
    err = r.get_json()['error']
    assert 'Backup' in err
    assert 'claude-3-5-sonnet-20241022' in err


def test_patch_validation_lenient_when_service_down(client, user_factory):
    """Wenn ai-provider-service nicht antwortet, wird die Validierung übersprungen."""
    headers, _ = _auth(user_factory)
    mock_client = MagicMock()
    mock_client.get_models.side_effect = Exception("Service unreachable")
    mock_client.get_config.return_value = {'configured': True}
    with patch('api.providers.ai_provider_client.is_enabled', return_value=True), \
         patch('api.providers.ai_provider_client.get_client', return_value=mock_client):
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'ollama',
            'model': 'irgendein-modell',
        }, headers=headers)
    # Sollte trotzdem durchgehen — wir blockieren nicht wenn Service down
    assert r.status_code == 200


def test_patch_validation_lenient_when_models_list_empty(client, user_factory):
    """Wenn der Service keine Modell-Liste liefert, wird nicht blockiert."""
    headers, _ = _auth(user_factory)
    is_enabled, get_client = _mock_service_with_models({'ollama': []})
    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'ollama',
            'model': 'whatever',
        }, headers=headers)
    assert r.status_code == 200


def test_patch_no_model_skips_validation(client, user_factory):
    """Wenn kein Modell-Feld gesendet wird, läuft die Validierung nicht."""
    headers, _ = _auth(user_factory)
    is_enabled, get_client = _mock_service_with_models({'ollama': ['valid-model']})
    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'ollama',
            # 'model' fehlt
        }, headers=headers)
    assert r.status_code == 200
