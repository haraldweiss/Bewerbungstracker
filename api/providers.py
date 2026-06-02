"""AI Provider Management Endpoints.

Wenn `AI_PROVIDER_SERVICE_URL` gesetzt ist (Production), delegieren die Endpoints
an den zentralen ai-provider-service. Sonst Fallback auf die lokale
ProviderFactory (Local-Dev ohne Service).

Frontend bleibt unverändert — die API-Surface ist identisch zum Vor-Migrations-Stand.
"""

from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import User
from database import db
from services import ai_provider_client
from services.ai_provider_client import AIProviderQueuedError
import json
import logging

logger = logging.getLogger(__name__)

providers_bp = Blueprint('providers', __name__, url_prefix='/api/providers')

VALID_PROVIDERS = {'claude', 'ollama', 'openai', 'mammouth', 'custom', 'opencode'}
# Provider die User-spezifisch konfiguriert werden können (eigener API-Key etc).
# Claude ist hier drin, weil neue User (außer dem Server-Key-Allowlist-Owner)
# einen eigenen Anthropic-Key hinterlegen müssen, um Claude nutzen zu können.
USER_PROVIDERS = {'claude', 'openai', 'mammouth', 'custom', 'opencode'}


def _validate_model_for_provider(user_id: str, provider: str, model: str) -> str | None:
    """Prüft, ob `model` für `provider` verfügbar ist (via ai-provider-service).

    Returns None bei Erfolg oder einen Fehlerstring bei ungültigem Modell.
    Lenient: Wenn der Service nicht antwortet oder keine Modell-Liste zurückgibt,
    wird die Validierung übersprungen (statt den Save zu blockieren).
    """
    if not model or not ai_provider_client.is_enabled():
        return None
    try:
        client = ai_provider_client.get_client()
        models = client.get_models(provider, user_id=user_id) or []
    except Exception as e:
        logger.warning(f'Model-Validation für {provider} übersprungen (Service-Fehler): {e}')
        return None
    if not models:
        # Kein Wissen über verfügbare Modelle → nicht blockieren
        return None
    if model in models:
        return None
    preview = ', '.join(models[:5])
    return (
        f'Model {model!r} ist für Provider {provider!r} nicht verfügbar. '
        f'Verfügbare Modelle: {preview}'
    )


def _service_or_400():
    """Holt den AIProviderClient; gibt JSON-Fehler zurück wenn nicht konfiguriert."""
    if not ai_provider_client.is_enabled():
        return None, ({'error': 'AI Provider Service nicht konfiguriert (AI_PROVIDER_SERVICE_URL fehlt)'}, 503)
    return ai_provider_client.get_client(), None


@providers_bp.route('', methods=['GET'])
@token_required
def list_providers(user):
    """Liste verfügbarer Provider via ai-provider-service."""
    client, err = _service_or_400()
    if err:
        return err

    try:
        providers = client.list_providers(user_id=user.id)
        # Frontend-Kompatibilität: unsere alten Frontend-Felder mappen
        out = []
        for p in providers:
            out.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'scope': 'system' if p.get('system') else 'user',
                'configured': p.get('configured', False),
                'healthy': p.get('healthy'),
                'models': [],  # wird per /<id>/models nachgeladen
            })
        return {'providers': out, 'default': 'claude'}, 200
    except Exception as e:
        logger.error(f'Provider-List Error: {e}')
        return {'error': str(e)}, 502


@providers_bp.route('/<provider_id>/models', methods=['GET'])
@token_required
def get_provider_models(user, provider_id):
    """Hole verfügbare Models für einen Provider."""
    if provider_id not in VALID_PROVIDERS:
        return {'error': f'Unbekannter Provider: {provider_id}'}, 400

    client, err = _service_or_400()
    if err:
        return err

    try:
        models = client.get_models(provider_id, user_id=user.id)
        if not models:
            return {'error': f'Keine Models von {provider_id}', 'configured': False}, 404
        return {'models': models, 'default': models[0] if models else None}, 200
    except Exception as e:
        logger.warning(f'Models-Fetch Error ({provider_id}): {e}')
        return {'error': str(e)}, 502


@providers_bp.route('/user/settings', methods=['GET'])
@token_required
def get_user_provider_settings(user):
    """User-Preference (welcher Provider/Model). Bleibt lokal in der Bewerbungstracker-DB."""
    backup = user.get_backup_config()
    if backup:
        backup_provider, backup_model, backup_auto = backup
    else:
        backup_provider, backup_model, backup_auto = None, None, False
    return {
        'provider': user.ai_provider or 'claude',
        'model': user.ai_provider_model,
        'backup_provider': backup_provider,
        'backup_model': backup_model,
        'backup_auto': backup_auto,
    }, 200


@providers_bp.route('/user/settings', methods=['PATCH'])
@token_required
def update_user_provider_settings(user):
    """Speichere User-Preference.

    Akzeptiert primär (provider, model) und optional (backup_provider, backup_model).
    Backup-Felder explizit auf None gesetzt → Backup-Override gelöscht
    (Admin-User fallen dann auf env-Default zurück).
    """
    data = request.get_json() or {}
    has_provider = 'provider' in data
    has_backup = 'backup_provider' in data or 'backup_model' in data

    # Primary
    if has_provider:
        provider = (data.get('provider') or user.ai_provider or 'claude')
        model = data.get('model')
        if provider not in VALID_PROVIDERS:
            return {'error': f'Unbekannter Provider: {provider}'}, 400
        # Bei User-Providern: prüfe ob im Service konfiguriert
        if provider in USER_PROVIDERS and ai_provider_client.is_enabled():
            try:
                client = ai_provider_client.get_client()
                cfg = client.get_config(user.id, provider)
                if not cfg.get('configured'):
                    return {'error': f'Provider {provider} ist nicht konfiguriert'}, 400
            except Exception as e:
                logger.warning(f'Config-Check für {provider} fehlgeschlagen: {e}')
        # Modell-Validierung: verhindert dass nicht existente Modelle gespeichert werden
        # (z.B. veraltete oder umbenannte Modelle wie 'qwen3.6:latest')
        err = _validate_model_for_provider(user.id, provider, model)
        if err:
            return {'error': err}, 400
        user.ai_provider = provider
        user.ai_provider_model = model

    # Adaptive-Learning Settings (optional, unabhängig von provider/backup)
    if 'job_learn_enabled' in data:
        if not isinstance(data['job_learn_enabled'], bool):
            return {'error': 'job_learn_enabled muss bool sein'}, 400
        user.job_learn_enabled = data['job_learn_enabled']

    if 'job_learn_min_samples' in data:
        v = data['job_learn_min_samples']
        if not isinstance(v, int) or isinstance(v, bool) or v < 1 or v > 100:
            return {'error': 'job_learn_min_samples muss int 1-100 sein'}, 400
        user.job_learn_min_samples = v

    if 'job_learn_weight_pct' in data:
        v = data['job_learn_weight_pct']
        if not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 100:
            return {'error': 'job_learn_weight_pct muss int 0-100 sein'}, 400
        user.job_learn_weight_pct = v

    # Backup (optional, unabhängig vom primary update)
    if has_backup:
        backup_provider = data.get('backup_provider')
        backup_model = data.get('backup_model')
        if backup_provider:
            if backup_provider not in VALID_PROVIDERS:
                return {'error': f'Unbekannter Backup-Provider: {backup_provider}'}, 400
            err = _validate_model_for_provider(user.id, backup_provider, backup_model)
            if err:
                return {'error': f'Backup: {err}'}, 400
        # backup_provider == None → Override löschen (Admin fällt auf env-Default)
        user.ai_provider_backup = backup_provider or None
        user.ai_provider_backup_model = backup_model if backup_provider else None

    try:
        db.session.commit()
        backup = user.get_backup_config()
        if backup:
            bp, bm, ba = backup
        else:
            bp, bm, ba = None, None, False
        logger.info(
            f'User {user.email} settings: provider={user.ai_provider} model={user.ai_provider_model} '
            f'backup={bp} backup_model={bm} backup_auto={ba}'
        )
        return {
            'provider': user.ai_provider,
            'model': user.ai_provider_model,
            'backup_provider': bp,
            'backup_model': bm,
            'backup_auto': ba,
            'message': 'Einstellungen gespeichert ✓'
        }, 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'Provider-Settings Error: {e}')
        return {'error': str(e)}, 500


@providers_bp.route('/<provider_id>/config', methods=['GET'])
@token_required
def get_provider_config(user, provider_id):
    """Aktuelle Provider-Config (ohne sensible Daten)."""
    if provider_id not in USER_PROVIDERS:
        return {'error': f'Provider {provider_id} unterstützt keine User-Konfiguration'}, 400

    client, err = _service_or_400()
    if err:
        return err

    try:
        cfg = client.get_config(user.id, provider_id)
        return cfg, 200
    except Exception as e:
        logger.error(f'Get Provider Config Error: {e}')
        return {'error': str(e)}, 502


@providers_bp.route('/<provider_id>/config', methods=['POST'])
@token_required
def save_provider_config(user, provider_id):
    """Provider-Config im ai-provider-service ablegen.

    API-Key fließt im Klartext zum lokalen Service (127.0.0.1) und wird
    dort serverseitig mit MASTER_KEY verschlüsselt.
    """
    if provider_id not in USER_PROVIDERS:
        return {'error': f'Provider {provider_id} wird nicht unterstützt'}, 400

    client, err = _service_or_400()
    if err:
        return err

    data = request.get_json() or {}

    # Pflichtfelder pro Provider
    required = {
        'claude': ['api_key'],
        'openai': ['api_key'],
        'mammouth': ['api_endpoint'],
        'custom': ['api_endpoint'],
        'opencode': ['api_key'],
    }.get(provider_id, [])
    missing = [f for f in required if not data.get(f)]
    if missing:
        return {'error': f'Pflichtfelder: {", ".join(missing)}'}, 400

    # Provider-Config bauen (Service erwartet inneres "config"-Objekt + Top-Level fallback/queue)
    config = {k: v for k, v in data.items() if k in (
        'api_key', 'api_endpoint', 'organization_id', 'name'
    ) and v}

    fallback = data.get('fallback_provider')
    queue_when_unavailable = data.get('queue_when_unavailable', True)
    queue_ttl_hours = int(data.get('queue_ttl_hours', 24))

    try:
        result = client.save_config(
            user_id=user.id, provider_id=provider_id,
            config=config, fallback_provider=fallback,
            queue_when_unavailable=queue_when_unavailable,
            queue_ttl_hours=queue_ttl_hours,
        )
        logger.info(f'User {user.email} saved provider {provider_id} via service')
        return {
            'message': f'Provider {provider_id} konfiguriert ✓',
            'provider_id': provider_id,
            'configured': True,
            **result,
        }, 200
    except Exception as e:
        logger.error(f'Save Provider Config Error: {e}')
        return {'error': str(e)}, 502


@providers_bp.route('/<provider_id>/config', methods=['DELETE'])
@token_required
def delete_provider_config(user, provider_id):
    """Provider-Config aus dem Service löschen."""
    if provider_id not in USER_PROVIDERS:
        return {'error': f'Provider {provider_id} hat keine löschbare User-Config'}, 400

    client, err = _service_or_400()
    if err:
        return err

    try:
        return client.delete_config(user.id, provider_id), 200
    except Exception as e:
        logger.error(f'Delete Provider Config Error: {e}')
        return {'error': str(e)}, 502


@providers_bp.route('/<provider_id>/test', methods=['POST'])
@token_required
def test_provider_connection(user, provider_id):
    """Teste Verbindung zu einem User-Provider."""
    if provider_id not in USER_PROVIDERS:
        return {'error': f'Provider {provider_id} hat keinen User-Test'}, 400

    client, err = _service_or_400()
    if err:
        return err

    try:
        return client.test_provider(provider_id, user_id=user.id), 200
    except Exception as e:
        logger.error(f'Test Provider Error ({provider_id}): {e}')
        return {'status': 'error', 'provider_id': provider_id, 'error': str(e)}, 400


# Sinnvolle Default-Models, falls User keinen gesetzt hat.
_DEFAULT_MODELS = {
    'claude': 'claude-haiku-4-5-20251001',
    'ollama': 'mistral-nemo:12b-instruct-2407-q5_K_M',
}


@providers_bp.route('/chat', methods=['POST'])
@token_required
def chat_with_user_provider(user):
    """Direkter Chat mit dem User-konfigurierten Provider (mit Fallback + Queue).

    Body:
      { "prompt": "...", "max_tokens": 3000, "model": "..." (optional) }

    Antworten:
      200: { "response": "<text>", "via": "<provider>", "fallback_used": bool, "usage": {...} }
      202: { "queued": true, "queue_id": "...", "expires_at": "..." }   ← Provider down + Queue an
      4xx/5xx: { "error": "..." }
    """
    if not ai_provider_client.is_enabled():
        return {'error': 'AI Provider Service nicht konfiguriert (AI_PROVIDER_SERVICE_URL fehlt)'}, 503

    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return {'error': 'prompt fehlt'}, 400

    max_tokens = int(data.get('max_tokens', 2000))
    provider = user.ai_provider or 'claude'
    model = data.get('model') or user.ai_provider_model or _DEFAULT_MODELS.get(provider, '')

    if not model:
        return {'error': f'Kein Model für Provider {provider} konfiguriert'}, 400

    try:
        client = ai_provider_client.get_client()
        fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='chat')
        response = client.chat(
            user_id=user.id, provider=provider, model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens,
            **fallback_kwargs,
        )
        return {
            'response': response.content[0].text if response.content else '',
            'via': response.via,
            'fallback_used': response.fallback_used,
            'provider': provider,
            'model': model,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
            },
        }, 200
    except AIProviderQueuedError as e:
        logger.info(f'Chat queued for user={user.id} provider={provider}: {e.queue_id}')
        return {
            'queued': True,
            'queue_id': e.queue_id,
            'expires_at': e.expires_at,
            'provider': provider,
            'message': f'Provider {provider} nicht erreichbar — Anfrage wird automatisch nachgeholt',
        }, 202
    except Exception as e:
        logger.error(f'Chat Error: {e}')
        return {'error': str(e), 'provider': provider}, 502
