"""
AI Provider Management Endpoints
Unterstützt Claude und lokales Ollama mit dynamischem Model-Fetching
"""

from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import User
from database import db
from services.provider_service import ProviderFactory, ProviderConfig
import logging

logger = logging.getLogger(__name__)

providers_bp = Blueprint('providers', __name__, url_prefix='/api/providers')


@providers_bp.route('', methods=['GET'])
@token_required
def list_providers(user):
    """Liste alle verfügbaren AI Provider und deren Models"""
    try:
        providers = ProviderFactory.get_available_providers()

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

    if provider not in [ProviderConfig.CLAUDE, ProviderConfig.OLLAMA]:
        return {'error': f'Unbekannter Provider: {provider}'}, 400

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
