"""
AI Provider Service – unterstützt Claude und lokales Ollama
Dynamisches Model-Fetching, CORS-Handling für lokale Services
"""

import os
import requests
import logging
from typing import Optional, List, Dict
from flask import current_app

logger = logging.getLogger(__name__)


class ProviderConfig:
    """Konfiguration für verfügbare AI Provider"""

    CLAUDE = 'claude'
    OLLAMA = 'ollama'

    PROVIDERS = {
        CLAUDE: {
            'name': 'Claude (Anthropic)',
            'api_key_env': 'CLAUDE_API_KEY',
            'models': ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
            'default_model': 'claude-haiku-4-5-20251001',
        },
        OLLAMA: {
            'name': 'Ollama (lokal)',
            'url_env': 'OLLAMA_URL',
            'default_url': 'http://127.0.0.1:11434',
            'default_model': 'mistral',
        }
    }


class OllamaClient:
    """Client für lokales Ollama mit CORS-Support"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 10

    def get_models(self) -> List[Dict]:
        """Fetcht verfügbare Models von lokalem Ollama"""
        try:
            response = requests.get(
                f'{self.base_url}/api/tags',
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get('models', []):
                models.append({
                    'name': model['name'],
                    'size': model.get('size', 0),
                    'modified': model.get('modified_at', '')
                })

            logger.info(f'✅ Ollama: {len(models)} Models gefunden')
            return models
        except requests.exceptions.ConnectionError:
            logger.error(f'❌ Ollama nicht erreichbar: {self.base_url}')
            return []
        except Exception as e:
            logger.error(f'❌ Ollama Models-Fehler: {e}')
            return []

    def create_message(self, model: str, messages: List[Dict], max_tokens: int = 600):
        """Erstellt Message mit Chat-API (compatible mit Claude API)"""
        try:
            payload = {
                'model': model,
                'messages': messages,
                'stream': False,
                'options': {
                    'num_predict': max_tokens,
                }
            }

            response = requests.post(
                f'{self.base_url}/api/chat',
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()

            return {
                'content': [{'text': data.get('message', {}).get('content', '')}],
                'usage': {
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            }
        except Exception as e:
            logger.error(f'❌ Ollama Chat-Fehler: {e}')
            raise


class ProviderFactory:
    """Factory um zwischen Claude und Ollama zu wechseln"""

    @staticmethod
    def get_client(provider: str, **kwargs):
        """Erstellt einen Client für den gewählten Provider"""

        if provider == ProviderConfig.CLAUDE:
            try:
                from anthropic import Anthropic
                api_key = os.getenv('CLAUDE_API_KEY')
                if not api_key:
                    raise ValueError('CLAUDE_API_KEY nicht gesetzt')
                return Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError('anthropic package nicht installiert')

        elif provider == ProviderConfig.OLLAMA:
            ollama_url = kwargs.get('ollama_url') or os.getenv(
                'OLLAMA_URL',
                ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_url']
            )
            return OllamaClient(ollama_url)

        else:
            raise ValueError(f'Unbekannter Provider: {provider}')

    @staticmethod
    def get_available_providers() -> List[Dict]:
        """Liste aller verfügbaren Provider mit Status"""
        providers = []

        if os.getenv('CLAUDE_API_KEY'):
            providers.append({
                'id': ProviderConfig.CLAUDE,
                'name': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['name'],
                'available': True,
                'default_model': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['default_model'],
                'models': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['models']
            })

        ollama_url = os.getenv('OLLAMA_URL', ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_url'])
        try:
            ollama = OllamaClient(ollama_url)
            models = ollama.get_models()
            if models:
                providers.append({
                    'id': ProviderConfig.OLLAMA,
                    'name': ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['name'],
                    'available': True,
                    'url': ollama_url,
                    'default_model': ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_model'],
                    'models': [m['name'] for m in models]
                })
        except Exception as e:
            logger.debug(f'Ollama nicht verfügbar: {e}')

        return providers

    @staticmethod
    def get_default_provider() -> str:
        """Bestimmt Standard-Provider (Claude, sonst Ollama)"""
        if os.getenv('CLAUDE_API_KEY'):
            return ProviderConfig.CLAUDE
        return ProviderConfig.OLLAMA
