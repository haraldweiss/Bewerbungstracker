"""HTTP-Client für ai-provider-service.

Dünner Wrapper um die REST-API des zentralen Provider-Service. Wird vom
Bewerbungstracker statt der alten lokalen ProviderFactory genutzt, sobald
AI_PROVIDER_SERVICE_URL in den Env-Vars gesetzt ist.

Antwort-Format ist Claude-kompatibel (Drop-in für match_job_with_claude):
  ChatResponse mit .content[0].text und .usage.input_tokens / .output_tokens
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
import requests
from config import Config

logger = logging.getLogger(__name__)


class AIProviderServiceError(Exception):
    """Base-Exception für Service-Fehler."""


class AIProviderQueuedError(AIProviderServiceError):
    """Request wurde gequeued (Provider down + queue=on, kein Fallback)."""

    def __init__(self, queue_id: str, expires_at: str = ''):
        super().__init__(f"Request queued: {queue_id}")
        self.queue_id = queue_id
        self.expires_at = expires_at


@dataclass
class ChatContent:
    text: str


@dataclass
class ChatUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class ChatResponse:
    """Anthropic-kompatible Response (für match_job_with_claude)."""
    content: List[ChatContent]
    usage: ChatUsage
    via: str
    fallback_used: bool = False
    # Der TATSÄCHLICH genutzte Modellname (= Wunschmodell bei primary,
    # = fallback_model bei fallback_used=True). Wird vom ai-provider-service
    # seit 2026-05-19 mitgeliefert; default = Wunschmodell (backward-compat).
    model: str = ""


class AIProviderClient:
    """HTTP-Client für ai-provider-service."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, timeout: int = 180):
        self.base_url = (base_url or Config.AI_PROVIDER_SERVICE_URL).rstrip('/')
        self.token = token or Config.AI_PROVIDER_SERVICE_TOKEN
        self.timeout = timeout
        if not self.base_url:
            raise ValueError("AI_PROVIDER_SERVICE_URL nicht gesetzt")
        if not self.token:
            raise ValueError("AI_PROVIDER_SERVICE_TOKEN nicht gesetzt")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r = requests.get(f'{self.base_url}{path}', headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: Optional[dict] = None) -> dict:
        r = requests.post(f'{self.base_url}{path}', json=body or {}, headers=self._headers(), timeout=self.timeout)
        if not r.ok:
            try:
                err = r.json().get('error', r.text)
            except Exception:
                err = r.text
            raise AIProviderServiceError(f'{r.status_code}: {err}')
        return r.json()

    def _delete(self, path: str) -> dict:
        r = requests.delete(f'{self.base_url}{path}', headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ── Provider-Listen ──────────────────────────────────────────────────────

    def list_providers(self, user_id: Optional[str] = None) -> List[Dict]:
        params = {'user_id': user_id} if user_id else None
        return self._get('/providers', params=params).get('providers', [])

    def get_models(self, provider_id: str, user_id: Optional[str] = None) -> List[str]:
        params = {'user_id': user_id} if user_id else None
        return self._get(f'/providers/{provider_id}/models', params=params).get('models', [])

    def get_provider_health(self, provider_id: str) -> dict:
        return self._get(f'/providers/{provider_id}/health')

    def test_provider(self, provider_id: str, user_id: str) -> dict:
        return self._post(f'/providers/{provider_id}/test', {'user_id': user_id})

    # ── Configs ──────────────────────────────────────────────────────────────

    def list_configs(self, user_id: str) -> List[Dict]:
        return self._get(f'/configs/{user_id}').get('configs', [])

    def get_config(self, user_id: str, provider_id: str) -> dict:
        return self._get(f'/configs/{user_id}/{provider_id}')

    def save_config(
        self,
        user_id: str,
        provider_id: str,
        config: dict,
        fallback_provider: Optional[str] = None,
        queue_when_unavailable: bool = True,
        queue_ttl_hours: int = 24,
    ) -> dict:
        body = {
            'config': config,
            'queue_when_unavailable': queue_when_unavailable,
            'queue_ttl_hours': queue_ttl_hours,
        }
        if fallback_provider is not None:
            body['fallback_provider'] = fallback_provider
        return self._post(f'/configs/{user_id}/{provider_id}', body)

    def delete_config(self, user_id: str, provider_id: str) -> dict:
        return self._delete(f'/configs/{user_id}/{provider_id}')

    # ── Chat ─────────────────────────────────────────────────────────────────

    def chat(
        self,
        user_id: str,
        provider: str,
        model: str,
        messages: List[Dict],
        max_tokens: int = 600,
        fallback_provider: Optional[str] = None,
        fallback_model: Optional[str] = None,
        fallback_config: Optional[dict] = None,
    ) -> ChatResponse:
        """Sendet Chat-Request. Bei Queueing wirft AIProviderQueuedError.

        Optional: fallback_provider+fallback_model schalten Per-Call-Fallback
        ein. fallback_config (z.B. {'api_key': '...'}) wird einmalig an den
        Service mitgegeben — nützlich für Admin-User mit zentralem env-Key,
        wo nichts in der Service-DB persistiert werden soll.

        Phase 2B: Wenn der Caller einen Claude-Backup einplant und das
        User-Tagesbudget bereits ausgeschoepft ist, werden die fallback_*-
        kwargs vor dem Service-Call gestrippt (Cap durchsetzen).
        """
        if _should_strip_claude_fallback(user_id, fallback_provider, fallback_model):
            import logging
            logging.getLogger(__name__).warning(
                "Daily budget cap hit for user %s — stripping claude fallback",
                user_id,
            )
            fallback_provider = None
            fallback_model = None
            fallback_config = None

        body = {
            'user_id': user_id, 'provider': provider, 'model': model,
            'messages': messages, 'max_tokens': max_tokens,
        }
        if fallback_provider:
            body['fallback_provider'] = fallback_provider
        if fallback_model:
            body['fallback_model'] = fallback_model
        if fallback_config:
            body['fallback_config'] = fallback_config
        result = self._post('/chat', body)
        if result.get('queued'):
            raise AIProviderQueuedError(
                queue_id=result.get('queue_id', ''),
                expires_at=result.get('expires_at', ''),
            )
        # Sync-Response
        r = result.get('result') or {}
        contents = r.get('content') or []
        usage = r.get('usage') or {}
        return ChatResponse(
            content=[ChatContent(text=c.get('text', '')) for c in contents],
            usage=ChatUsage(
                input_tokens=int(usage.get('input_tokens', 0)),
                output_tokens=int(usage.get('output_tokens', 0)),
            ),
            via=result.get('via', provider),
            fallback_used=bool(result.get('fallback_used')),
            # Service liefert 'model' seit 2026-05-19; default = Wunschmodell
            # (backward-compat fuer alte Service-Versionen).
            model=result.get('model') or model,
        )

    # ── Queue ────────────────────────────────────────────────────────────────

    def get_queue_item(self, queue_id: str) -> dict:
        return self._get(f'/queue/{queue_id}')

    def list_queue(self, user_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        params = {}
        if user_id:
            params['user_id'] = user_id
        if status:
            params['status'] = status
        return self._get('/queue', params=params or None).get('items', [])


def get_client(timeout: Optional[int] = None) -> Optional[AIProviderClient]:
    """Singleton-Helper. Returns None wenn der Service nicht konfiguriert ist
    (für Local-Dev ohne Service).

    ``timeout``: optionaler HTTP-Timeout pro Call. Default = 180s. Caller, die
    schneller fail-fast brauchen (z.B. Best-Effort-AI-Calls innerhalb eines
    Request-Handlers mit eigener Frist), sollten einen niedrigeren Wert
    setzen, damit die requests.Timeout-Exception greift bevor der gunicorn-
    Worker-Timeout den Worker abschiesst."""
    if not Config.AI_PROVIDER_SERVICE_URL or not Config.AI_PROVIDER_SERVICE_TOKEN:
        return None
    if timeout is not None:
        return AIProviderClient(timeout=timeout)
    return AIProviderClient()


def is_enabled() -> bool:
    """True wenn der Service-Modus aktiv ist (Env-Vars gesetzt)."""
    return bool(Config.AI_PROVIDER_SERVICE_URL and Config.AI_PROVIDER_SERVICE_TOKEN)


# Whitelist: nur diese Features duerfen heute Backup-Fallback nutzen.
# Erweitert in Phase 2B nach Einfuehrung des zentralen Cost-Tracker.
ALLOW_BACKUP_FEATURES = {'match'}


def _lookup_user_budget_cents(user_id: str) -> int:
    """Liest user.job_daily_budget_cents oder default 500. Isoliert, damit
    Tests mocken koennen ohne DB."""
    try:
        from models import User
        user = User.query.get(user_id)
        if user is None:
            return 500
        return int(user.job_daily_budget_cents or 500)
    except Exception:
        return 500


def _should_strip_claude_fallback(user_id: str, fallback_provider: str | None,
                                   fallback_model: str | None) -> bool:
    """Prueft ob Budget-Cap greift und Backup gestrippt werden soll."""
    if not user_id:
        return False
    is_claude = (
        (fallback_provider or '').lower() == 'claude'
        or 'claude' in (fallback_model or '').lower()
    )
    if not is_claude:
        return False
    try:
        from services import cost_tracker
        spent = cost_tracker.user_today_cost_cents(user_id)
        budget = _lookup_user_budget_cents(user_id)
        return spent >= budget
    except Exception:
        # Bei DB-Fehler permissiv durchlassen + Warnung
        import logging
        logging.getLogger(__name__).warning(
            "cost_tracker check failed for user %s — allowing call", user_id,
        )
        return False


def build_fallback_kwargs(user, feature: str | None = None) -> dict:
    """Baut die fallback_provider/fallback_model/fallback_config kwargs für chat().

    - Returns {} wenn der User kein Backup hat
    - Returns {} wenn feature nicht in ALLOW_BACKUP_FEATURES (Safe-by-Default,
      verhindert dass ungetracker Pfade Sonnet/Haiku ungebremst nutzen)
    - Returns nur provider+model wenn explizit konfiguriert (Service nutzt
      die vom User gespeicherte Config)
    - Returns provider+model+config wenn Admin-Auto-Fallback (zentraler
      CLAUDE_API_KEY wird per-call mitgegeben, NICHT im Service persistiert)
    """
    if feature not in ALLOW_BACKUP_FEATURES:
        return {}
    import os
    backup = user.get_backup_config() if user else None
    if not backup:
        return {}
    provider, model, is_auto = backup
    kwargs = {'fallback_provider': provider}
    if model:
        kwargs['fallback_model'] = model
    if is_auto:
        # Admin-Default: zentraler API-Key aus env mitgeben
        api_key = os.getenv('CLAUDE_API_KEY')
        if api_key:
            kwargs['fallback_config'] = {'api_key': api_key}
    return kwargs
