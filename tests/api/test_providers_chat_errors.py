# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Fehlermapping für POST /api/providers/chat (CV-Vergleich: "Direkt mit
konfiguriertem Provider analysieren").

Fix 2026-09-17: Ein 401 vom ai-provider-service wurde roh als
"401: ..." mit HTTP 502 durchgereicht — nicht erkennbar, ob das
Service-Token (App ↔ Service, typisch nach Rebuild, AGENTS.md §3.9)
oder der User-API-Key des konfigurierten Providers faul ist.
Erwartung: klassifizierte Meldung + passender Status
(service_auth → 503, provider_auth → 400).

Mocks only — kein echter Service, keine echten Credentials.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.ai_provider_client import AIProviderServiceError


def _mock_service(chat_side_effect=None, chat_return=None):
    is_enabled = patch(
        'api.providers.ai_provider_client.is_enabled', return_value=True
    )
    mock_client = MagicMock()
    if chat_side_effect is not None:
        mock_client.chat.side_effect = chat_side_effect
    else:
        mock_client.chat.return_value = chat_return
    get_client = patch(
        'api.providers.ai_provider_client.get_client',
        return_value=mock_client,
    )
    return is_enabled, get_client, mock_client


def _ok_chat_response():
    return SimpleNamespace(
        content=[SimpleNamespace(text='Analyse-Ergebnis')],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        via='claude',
        fallback_used=False,
    )


def test_chat_service_token_401_maps_to_503(client, auth_header):
    """Service-Bearer-Token ungültig → 503 + Admin-Anweisung (Token-Sync)."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError(
            '401: Missing or invalid Bearer token'
        )
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 503
    body = r.get_json()
    assert body['code'] == 'service_auth'
    assert 'Service-Token' in body['error']
    assert 'AI_PROVIDER_SERVICE_TOKEN' in body['error']


def test_chat_provider_key_401_maps_to_400(client, auth_header):
    """Ungültiger Provider-API-Key → 400 + User-Anweisung (Key/Wechsel)."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError(
            "401: {'error': {'message': 'invalid x-api-key', "
            "'type': 'authentication_error'}}"
        )
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 400
    body = r.get_json()
    assert body['code'] == 'provider_auth'
    assert 'API-Key' in body['error']
    assert 'opencode' in body['error']


def test_chat_ambiguous_401_stays_502_with_guidance(client, auth_header):
    """Nicht klassifizierbarer 401 → 502, nennt aber beide Prüfpunkte."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError('401: Unauthorized')
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 502
    body = r.get_json()
    assert body['code'] == 'auth'
    assert 'Service-Token' in body['error']
    assert 'Provider-Key' in body['error']


def test_chat_generic_error_stays_502_backward_compat(client, auth_header):
    """Nicht-401-Fehler: Raw-Message + 502 wie bisher (Frontend-kompatibel)."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError('500: upstream overloaded')
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 502
    body = r.get_json()
    assert body['code'] == 'provider'
    assert 'overloaded' in body['error']


def test_chat_stale_model_opencode_401(client, auth_header):
    """opencode meldet totes Free-Modell als 401 'not supported' → stale_model/400."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError(
            '401: Provider opencode rejected the request (HTTP 401)'
            ' {"type":"ModelError","message":"Model hy3-free is not supported"}'
        )
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 400
    body = r.get_json()
    assert body['code'] == 'stale_model'
    assert 'nicht mehr angeboten' in body['error']


def test_chat_stale_model_404(client, auth_header):
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(
        chat_side_effect=AIProviderServiceError(
            "404: {'error': 'No such model: xyz'}"
        )
    )
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 400
    assert r.get_json()['code'] == 'stale_model'


def test_chat_success_path_unchanged(client, auth_header):
    """Erfolgspfad: 200 mit response/via/usage wie bisher."""
    headers, _ = auth_header
    is_enabled, get_client, _ = _mock_service(chat_return=_ok_chat_response())
    with is_enabled, get_client:
        r = client.post(
            '/api/providers/chat',
            json={'prompt': 'Analysiere mein CV', 'max_tokens': 100},
            headers=headers,
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body['response'] == 'Analyse-Ergebnis'
    assert body['fallback_used'] is False
