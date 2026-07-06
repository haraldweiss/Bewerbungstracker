# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""OpenRouter provider integration tests."""
from unittest.mock import MagicMock, patch


def test_openrouter_models_are_proxied(client, auth_header):
    headers, user = auth_header
    mock_client = MagicMock()
    mock_client.get_models_raw.return_value = {
        "models": [
            "cohere/north-mini-code:free",
            "openai/gpt-4o-mini",
        ],
        "free_models": ["cohere/north-mini-code:free"],
    }

    with patch("api.providers.ai_provider_client.is_enabled", return_value=True), \
         patch("api.providers.ai_provider_client.get_client", return_value=mock_client):
        r = client.get("/api/providers/openrouter/models", headers=headers)

    assert r.status_code == 200
    body = r.get_json()
    assert body["models"][0] == "cohere/north-mini-code:free"
    assert body["free_models"] == ["cohere/north-mini-code:free"]
    mock_client.get_models_raw.assert_called_once_with("openrouter", user_id=user.id)


def test_openrouter_can_be_saved_as_backup_provider(client, auth_header):
    headers, _ = auth_header
    mock_client = MagicMock()
    mock_client.get_models.return_value = ["cohere/north-mini-code:free"]

    with patch("api.providers.ai_provider_client.is_enabled", return_value=True), \
         patch("api.providers.ai_provider_client.get_client", return_value=mock_client):
        r = client.patch(
            "/api/providers/user/settings",
            json={
                "backup_provider": "openrouter",
                "backup_model": "cohere/north-mini-code:free",
            },
            headers=headers,
        )

    assert r.status_code == 200
    body = r.get_json()
    assert body["backup_provider"] == "openrouter"
    assert body["backup_model"] == "cohere/north-mini-code:free"


def test_openrouter_can_be_saved_as_feature_model(client, auth_header):
    headers, _ = auth_header
    r = client.patch(
        "/api/profile/feature-models",
        json={
            "overrides": {
                "match": {
                    "provider": "openrouter",
                    "model": "cohere/north-mini-code:free",
                }
            }
        },
        headers=headers,
    )

    assert r.status_code == 200
    body = r.get_json()
    assert body["overrides"]["match"]["provider"] == "openrouter"
