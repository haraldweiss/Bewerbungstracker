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


def test_get_client_passes_timeout_override():
    """get_client(timeout=N) erzeugt Client mit angepasstem Timeout — wichtig
    fuer Best-Effort-AI-Calls innerhalb eines Request-Handlers, damit
    requests.Timeout greift bevor gunicorn-Worker stirbt."""
    from unittest.mock import patch
    from services.ai_provider_client import get_client

    with patch('services.ai_provider_client.Config') as mock_config:
        mock_config.AI_PROVIDER_SERVICE_URL = "http://test"
        mock_config.AI_PROVIDER_SERVICE_TOKEN = "tok"

        default_client = get_client()
        assert default_client is not None
        assert default_client.timeout == 180  # alter Default bleibt

        fast_client = get_client(timeout=60)
        assert fast_client is not None
        assert fast_client.timeout == 60


# Phase 2A: Backup-Whitelist
def test_build_fallback_kwargs_without_feature_returns_empty():
    """Default-Aufruf ohne feature= darf KEIN Backup mehr aktivieren.
    Safe by default."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    assert build_fallback_kwargs(user) == {}


def test_build_fallback_kwargs_non_whitelisted_feature_returns_empty():
    """Features ausserhalb der Whitelist bekommen KEIN Backup."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    assert build_fallback_kwargs(user, feature='email_parse') == {}
    assert build_fallback_kwargs(user, feature='cover_letter') == {}
    assert build_fallback_kwargs(user, feature='cv_summarize') == {}
    assert build_fallback_kwargs(user, feature='pattern_learn') == {}


def test_build_fallback_kwargs_match_feature_returns_kwargs():
    """match steht in der Whitelist und bekommt Backup-kwargs."""
    from services.ai_provider_client import build_fallback_kwargs
    user = type('U', (), {
        'get_backup_config': lambda self: ('claude', 'claude-haiku-4-5-20251001', False)
    })()
    kw = build_fallback_kwargs(user, feature='match')
    assert kw['fallback_provider'] == 'claude'
    assert kw['fallback_model'] == 'claude-haiku-4-5-20251001'


# Phase 2B: Budget-Cap im chat()-Wrapper
def test_chat_strips_claude_fallback_when_budget_exhausted(monkeypatch):
    """Wenn user heute schon ueber Budget: fallback_* aus dem Service-Body strippen."""
    import services.ai_provider_client as aip
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 600)
    monkeypatch.setattr(aip, '_lookup_user_budget_cents', lambda uid: 500)
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(aip.AIProviderClient, '_post', fake_post)

    client = aip.AIProviderClient.__new__(aip.AIProviderClient)
    client.base_url = "http://test"
    client.token = "test-token"
    client.timeout = 10
    client.chat(user_id='u1', provider='ollama', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='claude',
                fallback_model='claude-haiku-4-5-20251001')
    assert 'fallback_provider' not in captured['body']
    assert 'fallback_model' not in captured['body']


def test_chat_keeps_fallback_when_budget_remaining(monkeypatch):
    """Budget noch da → kwargs bleiben unveraendert."""
    import services.ai_provider_client as aip
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 100)
    monkeypatch.setattr(aip, '_lookup_user_budget_cents', lambda uid: 500)
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(aip.AIProviderClient, '_post', fake_post)

    client = aip.AIProviderClient.__new__(aip.AIProviderClient)
    client.base_url = "http://test"
    client.token = "test-token"
    client.timeout = 10
    client.chat(user_id='u1', provider='ollama', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='claude',
                fallback_model='claude-haiku-4-5-20251001')
    assert captured['body'].get('fallback_provider') == 'claude'
    assert captured['body'].get('fallback_model') == 'claude-haiku-4-5-20251001'


def test_chat_keeps_non_claude_fallback_unconditionally(monkeypatch):
    """Ollama-Fallback ist kostenlos und wird nicht gestripped — egal Budget-Status."""
    import services.ai_provider_client as aip
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 9999)
    captured = {}
    def fake_post(self, path, body):
        captured['body'] = body
        return {'result': {'content': [{'text': 'hi'}], 'model': 'm'}}
    monkeypatch.setattr(aip.AIProviderClient, '_post', fake_post)

    client = aip.AIProviderClient.__new__(aip.AIProviderClient)
    client.base_url = "http://test"
    client.token = "test-token"
    client.timeout = 10
    client.chat(user_id='u1', provider='claude', model='x',
                messages=[{'role': 'user', 'content': 'hi'}],
                fallback_provider='ollama',
                fallback_model='qwen3-coder')
    assert captured['body']['fallback_provider'] == 'ollama'
