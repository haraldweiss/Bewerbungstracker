"""
AI Provider Management Endpoints
Unterstützt Claude, Ollama, OpenAI, Mammouth, Custom Endpoints
mit dynamischem Model-Fetching und per-User-Konfiguration
"""

from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import User
from database import db
from services.provider_service import ProviderFactory, ProviderConfig
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
import json
import logging

logger = logging.getLogger(__name__)

providers_bp = Blueprint('providers', __name__, url_prefix='/api/providers')


@providers_bp.route('', methods=['GET'])
@token_required
def list_providers(user):
    """Liste alle verfügbaren AI Provider und deren Models"""
    try:
        providers = ProviderFactory.get_available_providers(user)

        return {
            'providers': providers,
            'default': ProviderFactory.get_default_provider()
        }, 200
    except Exception as e:
        logger.error(f'Provider-List Error: {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/<provider_id>/models', methods=['GET'])
@token_required
def get_provider_models(user, provider_id):
    """Hole verfügbare Models für einen spezifischen Provider"""
    try:
        if provider_id == ProviderConfig.CLAUDE:
            models = ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['models']
            return {'models': models, 'default': ProviderConfig.PROVIDERS[ProviderConfig.CLAUDE]['default_model']}, 200

        elif provider_id == ProviderConfig.OLLAMA:
            from services.provider_service import OllamaClient
            import os
            ollama_url = os.getenv('OLLAMA_URL', ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_url'])
            ollama = OllamaClient(ollama_url)
            models = ollama.get_models()

            if not models:
                return {'error': 'Keine Models auf lokalem Ollama gefunden'}, 404

            model_names = [m['name'] for m in models]
            return {
                'models': model_names,
                'default': ProviderConfig.PROVIDERS[ProviderConfig.OLLAMA]['default_model'],
                'details': models
            }, 200

        elif provider_id in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
            # User-Provider: Hole Config + dekryptiere API Key
            config_json = user.ai_provider_config or '{}'
            config_dict = json.loads(config_json)
            provider_config = config_dict.get(provider_id)

            if not provider_config:
                return {'error': f'Provider {provider_id} ist nicht konfiguriert', 'configured': False}, 400

            # Dekryptiere API Key falls vorhanden
            if 'api_key_encrypted' in provider_config:
                dek = get_key_cache().get(user.id)
                if not dek:
                    return {'error': 'Sicherheits-Session abgelaufen, bitte neu anmelden'}, 401
                api_key = EncryptionService.decrypt_data(provider_config['api_key_encrypted'], dek)
                provider_config = {**provider_config, 'api_key': api_key}

            client = ProviderFactory.get_client(provider_id, provider_config)
            models = client.get_models()

            if not models:
                return {'error': f'Keine Models von {provider_id} erhalten'}, 404

            return {'models': models, 'default': models[0] if models else None}, 200

        else:
            return {'error': f'Unbekannter Provider: {provider_id}'}, 400

    except Exception as e:
        logger.error(f'Models-Fetch Error ({provider_id}): {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/user/settings', methods=['GET'])
@token_required
def get_user_provider_settings(user):
    """Hole aktuelle Provider-Einstellung des Users"""
    return {
        'provider': user.ai_provider or 'claude',
        'model': user.ai_provider_model
    }, 200


@providers_bp.route('/user/settings', methods=['PATCH'])
@token_required
def update_user_provider_settings(user):
    """Speichere Provider-Wahl und Model-Auswahl des Users"""
    data = request.get_json() or {}

    provider = data.get('provider', user.ai_provider or 'claude')
    model = data.get('model')

    valid_providers = [
        ProviderConfig.CLAUDE, ProviderConfig.OLLAMA,
        ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM
    ]
    if provider not in valid_providers:
        return {'error': f'Unbekannter Provider: {provider}'}, 400

    # Bei User-Providern (OpenAI, Mammouth, Custom) muss der Provider konfiguriert sein
    if provider in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        config_json = user.ai_provider_config or '{}'
        config = json.loads(config_json)
        if provider not in config:
            return {'error': f'Provider {provider} ist nicht konfiguriert'}, 400

    try:
        user.ai_provider = provider
        user.ai_provider_model = model

        db.session.commit()

        logger.info(f'✅ User {user.email} set provider={provider}, model={model}')

        return {
            'provider': user.ai_provider,
            'model': user.ai_provider_model,
            'message': 'Einstellungen gespeichert ✓'
        }, 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'Provider-Settings Error: {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/<provider_id>/config', methods=['GET'])
@token_required
def get_provider_config(user, provider_id):
    """Hole aktuelle Konfiguration für einen User-Provider"""
    if provider_id not in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        return {'error': f'Provider {provider_id} unterstützt keine benutzerdefinierte Konfiguration'}, 400

    try:
        config_json = user.ai_provider_config or '{}'
        config = json.loads(config_json)
        provider_config = config.get(provider_id, {})

        if not provider_config:
            return {
                'provider_id': provider_id,
                'configured': False,
                'message': 'Provider nicht konfiguriert'
            }, 200

        # Rückgabe ohne sensitive Daten (API Key wird nicht zurückgegeben)
        return {
            'provider_id': provider_id,
            'configured': True,
            'endpoint': provider_config.get('api_endpoint'),
            'name': provider_config.get('name'),
            'model': provider_config.get('model'),
        }, 200
    except json.JSONDecodeError:
        return {'error': 'Ungültige Provider-Konfiguration'}, 500
    except Exception as e:
        logger.error(f'Get Provider Config Error: {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/<provider_id>/config', methods=['POST'])
@token_required
def save_provider_config(user, provider_id):
    """Speichere Provider-Konfiguration mit Encryption"""
    if provider_id not in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        return {'error': f'Provider {provider_id} wird nicht unterstützt'}, 400

    data = request.get_json() or {}

    # Validiere erforderliche Felder pro Provider
    required_fields = ProviderConfig.PROVIDERS[provider_id].get('requires', [])
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return {'error': f'Erforderliche Felder: {", ".join(missing)}'}, 400

    try:
        # Hole DEK aus Cache (User ist nach Login authentifiziert)
        dek = get_key_cache().get(user.id)
        if not dek:
            return {'error': 'Sicherheits-Session abgelaufen, bitte neu anmelden'}, 401

        # Lade aktuelle Config
        config_json = user.ai_provider_config or '{}'
        config = json.loads(config_json)

        # Verschlüssele API Key falls vorhanden
        provider_config = {}
        for key, value in data.items():
            if key == 'api_key' and value:
                encrypted = EncryptionService.encrypt_data(value, dek)
                provider_config['api_key_encrypted'] = encrypted
            else:
                provider_config[key] = value

        # Speichere in Config
        config[provider_id] = provider_config
        user.ai_provider_config = json.dumps(config)
        db.session.commit()

        logger.info(f'✅ User {user.email} configured provider={provider_id}')

        return {
            'message': f'Provider {provider_id} konfiguriert ✓',
            'provider_id': provider_id,
            'configured': True
        }, 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'Save Provider Config Error: {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/<provider_id>/test', methods=['POST'])
@token_required
def test_provider_connection(user, provider_id):
    """Teste Verbindung zu einem Provider (Models-Abfrage)"""
    if provider_id not in [ProviderConfig.OPENAI, ProviderConfig.MAMMOUTH, ProviderConfig.CUSTOM]:
        return {'error': f'Provider {provider_id} wird nicht unterstützt'}, 400

    try:
        # Hole Config
        config_json = user.ai_provider_config or '{}'
        config_dict = json.loads(config_json)
        provider_config = config_dict.get(provider_id)

        if not provider_config:
            return {'error': f'Provider {provider_id} ist nicht konfiguriert'}, 400

        # Dekryptiere API Key falls vorhanden
        if 'api_key_encrypted' in provider_config:
            dek = get_key_cache().get(user.id)
            if not dek:
                return {'error': 'Sicherheits-Session abgelaufen, bitte neu anmelden'}, 401
            api_key = EncryptionService.decrypt_data(provider_config['api_key_encrypted'], dek)
            provider_config = {**provider_config, 'api_key': api_key}

        # Erstelle Client und hole Models
        client = ProviderFactory.get_client(provider_id, provider_config)
        models = client.get_models()

        return {
            'status': 'connected',
            'provider_id': provider_id,
            'models_available': len(models),
            'sample_models': models[:5] if models else []
        }, 200

    except Exception as e:
        logger.error(f'Test Provider Connection Error ({provider_id}): {e}')
        return {
            'status': 'error',
            'provider_id': provider_id,
            'error': str(e)
        }, 400
