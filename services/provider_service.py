"""
AI Provider Service – unterstützt Claude, Ollama, OpenAI, Mammouth, Custom Endpoints
Dynamisches Model-Fetching, CORS-Handling, per-User API Key Management
"""

import os
import json
import requests
import logging
from typing import Optional, List, Dict
from flask import current_app

logger = logging.getLogger(__name__)


class ProviderConfig:
    """Konfiguration für verfügbare AI Provider"""

    CLAUDE = 'claude'
    OLLAMA = 'ollama'
    OPENAI = 'openai'
    MAMMOUTH = 'mammouth'
    CUSTOM = 'custom'
    OPENCODE = 'opencode'

    PROVIDERS = {
        CLAUDE: {
            'name': 'Claude (Anthropic)',
            'api_key_env': 'ANTHROPIC_API_KEY',
            'models': ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
            'default_model': 'claude-haiku-4-5-20251001',
            'scope': 'system',
        },
        OLLAMA: {
            'name': 'Ollama (lokal)',
            'url_env': 'OLLAMA_URL',
            'default_url': 'http://127.0.0.1:11434',
            'default_model': 'mistral',
            'scope': 'system',
        },
        OPENAI: {
            'name': 'ChatGPT / OpenAI',
            'requires': ['api_key'],
            'optional': ['organization_id'],
            'scope': 'user',
        },
        MAMMOUTH: {
            'name': 'Mammouth',
            'requires': ['api_endpoint'],
            'scope': 'user',
            'local': True,
        },
        CUSTOM: {
            'name': 'Custom OpenAI-compatible Endpoint',
            'requires': ['api_endpoint'],
            'optional': ['api_key', 'name'],
            'scope': 'user',
        },
        OPENCODE: {
            'name': 'Opencode.ai (Zen)',
            'requires': ['api_key'],
            'scope': 'user',
        },
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


class OpenAIClient:
    """Wrapper für OpenAI API (ChatGPT, etc.)"""

    def __init__(self, api_key: str, organization_id: str = None):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, organization=organization_id)
        except ImportError:
            raise ImportError('openai package nicht installiert')
        self.timeout = 30

    def get_models(self) -> List[str]:
        """Fetch available models from OpenAI API"""
        try:
            models = self.client.models.list()
            model_ids = [m.id for m in models.data if 'gpt' in m.id.lower()]
            logger.info(f'✅ OpenAI: {len(model_ids)} Models gefunden')
            return sorted(model_ids, reverse=True)
        except Exception as e:
            logger.error(f'❌ OpenAI Models-Fehler: {e}')
            return []

    def create_message(self, model: str, messages: List[Dict], max_tokens: int = 600):
        """Create message with OpenAI API (compatible with Claude format)"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens
            )

            return {
                'content': [{'text': response.choices[0].message.content}],
                'usage': {
                    'input_tokens': response.usage.prompt_tokens,
                    'output_tokens': response.usage.completion_tokens
                }
            }
        except Exception as e:
            logger.error(f'❌ OpenAI Chat-Fehler: {e}')
            raise


class MammouthClient:
    """Wrapper für Mammouth (lokales Modell)"""

    def __init__(self, api_endpoint: str):
        self.endpoint = api_endpoint.rstrip('/')
        self.timeout = 30

    def get_models(self) -> List[str]:
        """Fetch models from Mammouth endpoint"""
        try:
            response = requests.get(
                f'{self.endpoint}/models',
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            models = data.get('models', []) if isinstance(data.get('models'), list) else []
            if not models and 'data' in data:
                models = [m.get('id', m.get('name', '')) for m in data['data']]

            logger.info(f'✅ Mammouth: {len(models)} Models gefunden')
            return [m['name'] if isinstance(m, dict) else m for m in models]
        except Exception as e:
            logger.error(f'❌ Mammouth Models-Fehler: {e}')
            return []

    def create_message(self, model: str, messages: List[Dict], max_tokens: int = 600):
        """Create message with Mammouth API (OpenAI-compatible)"""
        try:
            payload = {
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
            }

            response = requests.post(
                f'{self.endpoint}/chat/completions',
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return {
                'content': [{'text': data['choices'][0]['message']['content']}],
                'usage': {
                    'input_tokens': data.get('usage', {}).get('prompt_tokens', 0),
                    'output_tokens': data.get('usage', {}).get('completion_tokens', 0)
                }
            }
        except Exception as e:
            logger.error(f'❌ Mammouth Chat-Fehler: {e}')
            raise


class CustomEndpointClient:
    """Generic OpenAI-compatible endpoint wrapper"""

    def __init__(self, api_endpoint: str, api_key: str = None):
        self.endpoint = api_endpoint.rstrip('/')
        self.api_key = api_key
        self.timeout = 30

    def get_models(self) -> List[str]:
        """Fetch models from custom endpoint (/v1/models)"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            response = requests.get(
                f'{self.endpoint}/v1/models',
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # OpenAI-compatible format
            models = [m['id'] for m in data.get('data', [])]
            logger.info(f'✅ Custom Endpoint: {len(models)} Models gefunden')
            return models
        except Exception as e:
            logger.error(f'❌ Custom Endpoint Models-Fehler: {e}')
            return []

    def create_message(self, model: str, messages: List[Dict], max_tokens: int = 600):
        """Create message with custom OpenAI-compatible API"""
        try:
            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            payload = {
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
            }

            response = requests.post(
                f'{self.endpoint}/v1/chat/completions',
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return {
                'content': [{'text': data['choices'][0]['message']['content']}],
                'usage': {
                    'input_tokens': data.get('usage', {}).get('prompt_tokens', 0),
                    'output_tokens': data.get('usage', {}).get('completion_tokens', 0)
                }
            }
        except Exception as e:
            logger.error(f'❌ Custom Endpoint Chat-Fehler: {e}')
            raise


class ProviderFactory:
    """Factory um zwischen verschiedenen Providern zu wechseln"""

    @staticmethod
    def get_client(provider: str, user_config: dict = None, **kwargs):
        """
        Erstellt einen Client für den gewählten Provider

        Args:
            provider: Provider-ID (claude, ollama, openai, mammouth, custom)
            user_config: Dict mit provider-spezifischem Config (für User-Provider)
            **kwargs: Zusätzliche Argumente (z.B. ollama_url)
        """
        user_config = user_config or {}

        if provider == ProviderConfig.CLAUDE:
            try:
                from anthropic import Anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError('ANTHROPIC_API_KEY nicht gesetzt')
                return Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError('anthropic package nicht installiert')

        elif provider == ProviderConfig.OLLAMA:
            ollama_url = kwargs.get('ollama_url') or os.getenv(
                'OLLAMA_URL',
                ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_url']
            )
            return OllamaClient(ollama_url)

        elif provider == ProviderConfig.OPENAI:
            api_key = user_config.get('api_key')
            if not api_key:
                raise ValueError('OpenAI API Key erforderlich')
            org_id = user_config.get('organization_id')
            return OpenAIClient(api_key, org_id)

        elif provider == ProviderConfig.MAMMOUTH:
            endpoint = user_config.get('api_endpoint')
            if not endpoint:
                raise ValueError('Mammouth API Endpoint erforderlich')
            return MammouthClient(endpoint)

        elif provider == ProviderConfig.CUSTOM:
            endpoint = user_config.get('api_endpoint')
            if not endpoint:
                raise ValueError('Custom Endpoint erforderlich')
            api_key = user_config.get('api_key')
            return CustomEndpointClient(endpoint, api_key)

        else:
            raise ValueError(f'Unbekannter Provider: {provider}')

    @staticmethod
    def get_available_providers(user=None) -> List[Dict]:
        """
        Liste aller verfügbaren Provider mit Status

        Args:
            user: User-Objekt (optional, um user-spezifische Provider zu laden)

        Returns:
            List von Provider-Dicts mit id, name, models, etc.
        """
        providers = []

        # System-Provider: Claude
        if os.getenv('ANTHROPIC_API_KEY'):
            providers.append({
                'id': ProviderConfig.CLAUDE,
                'name': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['name'],
                'scope': 'system',
                'default_model': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['default_model'],
                'models': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['models']
            })

        # System-Provider: Ollama (auto-detect)
        ollama_url = os.getenv('OLLAMA_URL', ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_url'])
        try:
            ollama = OllamaClient(ollama_url)
            models = ollama.get_models()
            if models:
                providers.append({
                    'id': ProviderConfig.OLLAMA,
                    'name': ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['name'],
                    'scope': 'system',
                    'url': ollama_url,
                    'default_model': ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_model'],
                    'models': [m['name'] for m in models]
                })
        except Exception as e:
            logger.debug(f'Ollama nicht verfügbar: {e}')

        # User-Provider aus Datenbank
        if user and user.ai_provider_config:
            try:
                config = json.loads(user.ai_provider_config)
                for provider_id, provider_config in config.items():
                    if provider_id in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
                        providers.append({
                            'id': provider_id,
                            'name': ProviderConfig.PROVIDERS.get(provider_id, {}).get('name', provider_id),
                            'scope': 'user',
                            'configured': True,
                            'endpoint': provider_config.get('api_endpoint'),
                            'custom_name': provider_config.get('name')  # Für CUSTOM Provider
                        })
            except json.JSONDecodeError:
                logger.warning(f'Invalid ai_provider_config JSON for user {user.id}')

        return providers

    @staticmethod
    def get_default_provider() -> str:
        """Bestimmt Standard-Provider (Claude > Ollama)"""
        if os.getenv('ANTHROPIC_API_KEY'):
            return ProviderConfig.CLAUDE
        return ProviderConfig.OLLAMA
