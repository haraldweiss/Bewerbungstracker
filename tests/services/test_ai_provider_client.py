"""Unit-Tests fuer ai_provider_client.ChatResponse-Parsing.

Insbesondere das `model`-Feld: ai-provider-service liefert seit 2026-05-19
den tatsaechlich genutzten Modellnamen mit (bei Fallback != Wunschmodell).
"""
from unittest.mock import patch, MagicMock


def _client():
    """Minimaler AIProviderClient ohne env-Reads."""
    from services.ai_provider_client import AIProviderClient
    c = AIProviderClient.__new__(AIProviderClient)
    c.base_url = "http://test"
    c.token = "test-token"
    c.timeout = 10
    return c


def test_chat_returns_model_from_service_response():
    """Service liefert 'model' im Response → ChatResponse.model = das."""
    from services.ai_provider_client import ChatResponse
    fake_resp = {
        "result": {
            "content": [{"text": "hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        "via": "claude",
        "model": "claude-haiku-4-5-20251001",
        "fallback_used": True,
    }
    with patch.object(_client().__class__, "_post", return_value=fake_resp):
        c = _client()
        r = c.chat(
            user_id="u1", provider="ollama", model="qwen:latest",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert isinstance(r, ChatResponse)
    assert r.via == "claude"
    assert r.fallback_used is True
    assert r.model == "claude-haiku-4-5-20251001"


def test_chat_falls_back_to_requested_model_if_service_omits_it():
    """Backward-compat: alter Service ohne 'model'-Feld → ChatResponse.model = Wunschmodell."""
    fake_resp = {
        "result": {
            "content": [{"text": "hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        "via": "ollama",
        # NO 'model' key — simulates old service version
        "fallback_used": False,
    }
    with patch.object(_client().__class__, "_post", return_value=fake_resp):
        c = _client()
        r = c.chat(
            user_id="u1", provider="ollama", model="qwen:latest",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert r.model == "qwen:latest"
    assert r.fallback_used is False


def test_chat_primary_path_returns_requested_model():
    """Primary-Path: Service liefert 'model' = Wunschmodell → ChatResponse.model = das."""
    fake_resp = {
        "result": {
            "content": [{"text": "hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        "via": "ollama",
        "model": "qwen:latest",
        "fallback_used": False,
    }
    with patch.object(_client().__class__, "_post", return_value=fake_resp):
        c = _client()
        r = c.chat(
            user_id="u1", provider="ollama", model="qwen:latest",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert r.model == "qwen:latest"
    assert r.via == "ollama"
