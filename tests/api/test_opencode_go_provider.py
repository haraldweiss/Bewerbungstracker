# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""opencode_go provider integration tests.

Context: OpenCode invalidated the Zen/Console keys with its 2026-10-17 breach
response and the Zen free tier is unusable, so the ai-provider-service serves
opencode.ai models through its Go subscription as `opencode_go/<model>`. The
tracker therefore has to accept `opencode_go` as a provider (and stop defaulting
users to retired Zen free models like `muse-spark-1.3-contributor-free`).
"""
from unittest.mock import MagicMock, patch


def _service(models_by_provider, configured=True):
    """Mock the ai-provider-service client for both patch targets."""
    mock_client = MagicMock()
    mock_client.get_models.side_effect = (
        lambda provider, user_id=None: models_by_provider.get(provider, []))
    mock_client.get_models_raw.side_effect = (
        lambda provider, user_id=None: {'models': models_by_provider.get(provider, [])})
    mock_client.get_config.return_value = {'configured': configured}
    return (
        patch('api.providers.ai_provider_client.is_enabled', return_value=True),
        patch('api.providers.ai_provider_client.get_client', return_value=mock_client),
        mock_client,
    )


def test_opencode_go_is_a_valid_and_user_configurable_provider():
    from api.providers import USER_PROVIDERS, VALID_PROVIDERS
    from api.profile import VALID_PROVIDERS as PROFILE_VALID_PROVIDERS

    assert 'opencode_go' in VALID_PROVIDERS
    assert 'opencode_go' in USER_PROVIDERS
    assert 'opencode_go' in PROFILE_VALID_PROVIDERS


def test_opencode_go_default_model_is_not_a_retired_free_model():
    """The default must exist in the Go catalog — the old opencode default
    (`opencode-deepseek-v4-flash-free`) points at a model that no longer
    exists upstream."""
    from api.providers import _DEFAULT_MODELS

    assert _DEFAULT_MODELS['opencode_go'] == 'deepseek-v4.1-flash'
    assert 'free' not in _DEFAULT_MODELS['opencode_go']


def test_opencode_go_settings_saved_without_personal_key(client, auth_header):
    """The service funds opencode_go with its own server key, so saving the
    provider must not require a personal key/config (the opencode bypass)."""
    headers, user = auth_header
    is_enabled, get_client, mock_client = _service(
        {'opencode_go': ['deepseek-v4.1-flash', 'beam-free']}, configured=False)

    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'opencode_go',
            'model': 'deepseek-v4.1-flash',
        }, headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body['provider'] == 'opencode_go'
    assert body['model'] == 'deepseek-v4.1-flash'


def test_opencode_go_rejects_model_outside_catalog(client, auth_header):
    headers, _ = auth_header
    is_enabled, get_client, _ = _service({'opencode_go': ['deepseek-v4.1-flash']})

    with is_enabled, get_client:
        r = client.patch('/api/providers/user/settings', json={
            'provider': 'opencode_go',
            'model': 'muse-spark-1.3-contributor-free',
        }, headers=headers)

    assert r.status_code == 400
    assert 'muse-spark-1.3-contributor-free' in r.get_json()['error']


def test_opencode_go_models_are_proxied(client, auth_header):
    headers, user = auth_header
    is_enabled, get_client, mock_client = _service(
        {'opencode_go': ['deepseek-v4.1-flash', 'beam-free',
                         'longcat-2.5-preview-free']})

    with is_enabled, get_client:
        r = client.get('/api/providers/opencode_go/models', headers=headers)

    assert r.status_code == 200
    assert 'deepseek-v4.1-flash' in r.get_json()['models']
    mock_client.get_models_raw.assert_called_once_with('opencode_go', user_id=user.id)
