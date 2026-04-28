# Job-Discovery Phase B — BYOK + AI-Provider-Factory

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring-Your-Own-Key (BYOK) System: User können eigene AI-Credentials hinterlegen (Anthropic offiziell oder Custom-HTTP-Endpoints wie Ollama/vLLM/OpenRouter). Phase A's `claude-match` Stage wird auf eine Provider-Factory umgestellt, sodass Cost beim User-Account anfällt statt am Server.

**Architecture:** Neue Tabelle `user_ai_credentials` (envelope-encrypted), AI-Provider-Adapter (4 Typen: Anthropic, OpenAI-compat, Anthropic-compat, Custom-Template), Provider-Factory mit per-User Credential-Lookup und KeyCache, Refactor von `api/jobs_cron.py:claude_match` zur Factory-Nutzung.

**Tech Stack:** Python, SQLAlchemy, `cryptography` (Fernet), `requests`, `anthropic` SDK, `jsonpath-ng` (für custom_template Response-Parsing).

**Voraussetzung:** Phase A komplett (Pipeline läuft mit Server-Key).

**Spec:** [docs/superpowers/specs/2026-04-28-job-discovery-design.md](../specs/2026-04-28-job-discovery-design.md) — Sektion 3.5, 4 (Stage 3), 5 (AI-Provider-Adapter).

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `models.py` | + `UserAICredentials`-Modell |
| `services/ai_providers/__init__.py` | Provider-Registry + Factory |
| `services/ai_providers/base.py` | `AIProvider` ABC + `MatchResult`-Dataclass |
| `services/ai_providers/anthropic_provider.py` | Offizielle Anthropic-API |
| `services/ai_providers/openai_compat.py` | Ollama/vLLM/OpenRouter/Groq |
| `services/ai_providers/anthropic_compat.py` | Anthropic-API-kompatible Proxies |
| `services/ai_providers/custom_template.py` | Mustache+JSONPath-Provider |
| `services/ai_providers/key_cache.py` | TTL-Cache für entschlüsselte Keys |
| `services/credentials_crypto.py` | encrypt/decrypt API-Keys mit User-DEK |
| `api/ai_credentials.py` | Blueprint `/api/ai-credentials/*` |
| `scripts/migrate_byok.py` | DB-Migration für `user_ai_credentials` |
| `tests/services/test_ai_providers_anthropic.py` | |
| `tests/services/test_ai_providers_openai_compat.py` | |
| `tests/services/test_ai_providers_anthropic_compat.py` | |
| `tests/services/test_ai_providers_custom_template.py` | |
| `tests/services/test_ai_provider_factory.py` | |
| `tests/services/test_credentials_crypto.py` | |
| `tests/services/test_key_cache_ai.py` | |
| `tests/api/test_ai_credentials.py` | |

**Modifiziert:**
- `api/jobs_cron.py` — `claude_match()` ruft `AIProviderFactory.get_provider(user_id)` statt direkt `Anthropic(server_key)`
- `services/job_matching/claude_matcher.py` — Refactor zu Provider-agnostischem Aufruf

---

## Task 1: `UserAICredentials`-Modell

**Files:**
- Modify: `models.py`
- Test: `tests/test_models_byok.py` (neu)

- [ ] **Step 1: Failing-Test**

`tests/test_models_byok.py`:
```python
import pytest
from app import create_app
from database import db
from models import UserAICredentials


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_credentials_anthropic(app, user_factory):
    user = user_factory()
    cred = UserAICredentials(
        user_id=user.id, provider='anthropic',
        encrypted_api_key=b'\x00' * 32, key_nonce=b'\x00' * 16,
        default_model='claude-haiku-4-5-20251001',
        is_active=False,
    )
    db.session.add(cred); db.session.commit()
    assert cred.id is not None


def test_credentials_custom_endpoint(app, user_factory):
    user = user_factory()
    cred = UserAICredentials(
        user_id=user.id, provider='custom_openai_compat',
        endpoint_url='http://localhost:11434/v1/chat/completions',
        default_model='llama3',
        is_active=False,
    )
    db.session.add(cred); db.session.commit()
    assert cred.endpoint_url.startswith('http://localhost')


def test_unique_active_per_provider(app, user_factory):
    user = user_factory()
    c1 = UserAICredentials(user_id=user.id, provider='anthropic',
                           encrypted_api_key=b'1', key_nonce=b'1',
                           is_active=True)
    db.session.add(c1); db.session.commit()
    c2 = UserAICredentials(user_id=user.id, provider='anthropic',
                           encrypted_api_key=b'2', key_nonce=b'2',
                           is_active=True)
    db.session.add(c2)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: Modell in `models.py` ergänzen**

```python
class UserAICredentials(db.Model):
    """Per-User-Credentials für AI-Provider (BYOK).

    encrypted_api_key + key_nonce: User-DEK-verschlüsselter API-Key (Anthropic etc.)
    encrypted_auth_header_value + auth_nonce: optional, für custom_*-Endpoints mit
                                              Bearer-Token o.ä.
    request_template + response_path: nur für custom_template.

    Constraint: max 1 active=True pro (user_id, provider).
    """
    __tablename__ = 'user_ai_credentials'
    __table_args__ = (
        db.Index('ix_uac_user_provider_active', 'user_id', 'provider', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False)
    # provider ∈ {anthropic, custom_openai_compat, custom_anthropic_compat, custom_template}

    encrypted_api_key = db.Column(db.LargeBinary, nullable=True)
    key_nonce = db.Column(db.LargeBinary, nullable=True)

    endpoint_url = db.Column(db.String(1024), nullable=True)
    auth_header_name = db.Column(db.String(64), nullable=True)
    encrypted_auth_header_value = db.Column(db.LargeBinary, nullable=True)
    auth_nonce = db.Column(db.LargeBinary, nullable=True)

    default_model = db.Column(db.String(128), nullable=True)
    _request_template = db.Column('request_template', db.Text, nullable=True)
    response_path = db.Column(db.String(256), nullable=True)

    monthly_budget_cents = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def request_template(self) -> dict | None:
        return _json.loads(self._request_template) if self._request_template else None

    @request_template.setter
    def request_template(self, value: dict | None):
        self._request_template = _json.dumps(value) if value else None
```

- [ ] **Step 4: Partial Unique Index** (nur in Code, da SQLite/Postgres differieren — wir validieren on-write zusätzlich)

In `models.py` als Hook (Event-Listener) ergänzen:
```python
from sqlalchemy import event


@event.listens_for(UserAICredentials, 'before_insert')
@event.listens_for(UserAICredentials, 'before_update')
def _enforce_one_active_credential(mapper, connection, target):
    if not target.is_active:
        return
    table = UserAICredentials.__table__
    stmt = table.select().where(
        table.c.user_id == target.user_id,
        table.c.provider == target.provider,
        table.c.is_active == True,
    )
    if target.id:
        stmt = stmt.where(table.c.id != target.id)
    existing = connection.execute(stmt).first()
    if existing:
        raise ValueError(
            f"User {target.user_id} hat bereits aktive Credentials für {target.provider}"
        )
```

- [ ] **Step 5: Tests passen + Commit**

```bash
pytest tests/test_models_byok.py -v
git add models.py tests/test_models_byok.py
git commit -m "feat: UserAICredentials-Modell mit aktiv-Constraint"
```

---

## Task 2: DB-Migration

**Files:**
- Create: `scripts/migrate_byok.py`

- [ ] **Step 1: Skript schreiben**

```python
"""DB-Migration für BYOK (Phase B)."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db


def main():
    app = create_app()
    with app.app_context():
        print("→ Erstelle user_ai_credentials Tabelle...")
        db.create_all()
        print("✓ BYOK-Migration abgeschlossen.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Skript einmal laufen lassen**

```bash
python scripts/migrate_byok.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_byok.py
git commit -m "feat: BYOK DB-Migration"
```

---

## Task 3: Credentials-Crypto

**Files:**
- Create: `services/credentials_crypto.py`
- Test: `tests/services/test_credentials_crypto.py`

- [ ] **Step 1: Failing-Test**

```python
import pytest
from services.encryption_service import EncryptionService
from services.credentials_crypto import encrypt_secret, decrypt_secret


def test_roundtrip_with_user_dek(app, user_factory):
    user = user_factory()
    # Setze einen DEK auf den User (analog zu Phase 2 Setup)
    salt = EncryptionService.generate_salt()
    dek = EncryptionService.generate_dek()
    kek = EncryptionService.derive_kek("password123", salt)
    user.encryption_salt = salt
    user.encrypted_data_key = EncryptionService.wrap_dek(dek, kek)
    db.session.commit()

    plaintext = "sk-ant-api03-xyz-very-secret"
    blob, nonce = encrypt_secret(plaintext, dek)
    assert blob != plaintext.encode()
    assert len(nonce) > 0

    recovered = decrypt_secret(blob, nonce, dek)
    assert recovered == plaintext


def test_decrypt_wrong_dek_fails():
    dek1 = EncryptionService.generate_dek()
    dek2 = EncryptionService.generate_dek()
    blob, nonce = encrypt_secret("secret", dek1)
    with pytest.raises(Exception):
        decrypt_secret(blob, nonce, dek2)
```

- [ ] **Step 2: Test schlägt fehl** (möglicherweise auch Methoden-Stubs in EncryptionService)

- [ ] **Step 3: `services/credentials_crypto.py`**

```python
"""Encrypt/Decrypt von API-Keys + Auth-Headers mit User-DEK.

Nutzt Fernet (AES-128-CBC + HMAC). Der DEK ist das Output von
EncryptionService.unwrap_dek(user, password).
"""
from cryptography.fernet import Fernet


def encrypt_secret(plaintext: str, dek: bytes) -> tuple[bytes, bytes]:
    """Verschlüsselt einen String mit User-DEK.

    Returns:
        (ciphertext, nonce) — Fernet-Tokens enthalten den Nonce intrinsisch,
        wir geben einen leeren Marker zurück um die Schnittstelle homogen
        zur AESGCM-Variante zu halten.
    """
    f = Fernet(dek)
    token = f.encrypt(plaintext.encode('utf-8'))
    return token, b''  # Fernet-Tokens haben Nonce intrinsisch


def decrypt_secret(ciphertext: bytes, _nonce: bytes, dek: bytes) -> str:
    f = Fernet(dek)
    plaintext = f.decrypt(ciphertext)
    return plaintext.decode('utf-8')
```

> ⚠️ **Hinweis zum Test-Setup:** Falls `EncryptionService.wrap_dek` / `unwrap_dek` in Phase 1 nicht als statische Methoden existieren, müssen die Tests die bestehenden API-Methoden nutzen. Schau in `services/encryption_service.py` nach. Methoden wie `derive_kek`, `wrap_dek`, `unwrap_dek` sind in Memory-Notes erwähnt.

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/services/test_credentials_crypto.py -v
git add services/credentials_crypto.py tests/services/test_credentials_crypto.py
git commit -m "feat: Credentials-Crypto mit User-DEK (Fernet)"
```

---

## Task 4: AI-Provider Base + Anthropic-Provider

> **Hinweis zur Type-Migration:** Plan A definiert ein `MatchResult` in
> `services/job_matching/claude_matcher.py` mit 5 Feldern. Plan B's
> `services/ai_providers/base.py:MatchResult` ergänzt `cost_cents: int = 0`.
> Das ist die kanonische Variante ab Phase B. Die alte Definition wird in
> Task 11 mit dem `claude_matcher.py`-Cleanup obsolet.



**Files:**
- Create: `services/ai_providers/__init__.py` (zunächst leer)
- Create: `services/ai_providers/base.py`
- Create: `services/ai_providers/anthropic_provider.py`
- Test: `tests/services/test_ai_providers_anthropic.py`

- [ ] **Step 1: Failing-Test**

```python
from unittest.mock import patch, MagicMock
from services.ai_providers.anthropic_provider import AnthropicProvider


@patch("services.ai_providers.anthropic_provider.Anthropic")
def test_anthropic_provider_match(mock_anthropic_cls):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 90, "reasoning": "ok", "missing_skills": []}')],
        usage=MagicMock(input_tokens=200, output_tokens=40),
    )
    mock_anthropic_cls.return_value = client

    p = AnthropicProvider(api_key="sk-ant-test", model="claude-haiku-4-5-20251001")
    res = p.match_job(cv_summary="Senior React Dev",
                      job={"title": "x", "description": "y", "location": "z"})
    assert res.score == 90
    assert res.tokens_in == 200
    mock_anthropic_cls.assert_called_once_with(api_key="sk-ant-test")


@patch("services.ai_providers.anthropic_provider.Anthropic")
def test_anthropic_test_connection(mock_anthropic_cls):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="ok")],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )
    mock_anthropic_cls.return_value = client
    p = AnthropicProvider(api_key="sk-ant-test", model="claude-haiku-4-5-20251001")
    assert p.test_connection() is True
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/ai_providers/base.py`**

```python
"""Base-Class für alle AI-Provider."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MatchResult:
    score: float
    reasoning: str
    missing_skills: list
    tokens_in: int
    tokens_out: int
    cost_cents: int = 0  # 0 für Self-Hosted, sonst geschätzt


class AIProvider(ABC):
    """Vereinheitlichtes Interface für alle Provider-Typen."""

    @abstractmethod
    def match_job(self, cv_summary: str, job: dict) -> MatchResult:
        """Bewertet einen Job gegen einen CV."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Mini-Aufruf zur Validierung der Credentials."""
```

- [ ] **Step 4: `services/ai_providers/anthropic_provider.py`**

```python
"""Offizieller Anthropic-API-Provider via SDK."""
import json as _json
from anthropic import Anthropic

from services.ai_providers.base import AIProvider, MatchResult


COST_USD_PER_1M_IN = 0.80
COST_USD_PER_1M_OUT = 4.00

PROMPT = """Du bewertest, wie gut die Stellenausschreibung zu meinem CV passt.

MEIN CV:
{cv}

STELLE:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit gültigem JSON:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["..."]}}"""


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def match_job(self, cv_summary: str, job: dict) -> MatchResult:
        prompt = PROMPT.format(
            cv=cv_summary[:3000],
            title=job.get("title", ""),
            location=job.get("location", ""),
            description=(job.get("description") or "")[:5000],
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json\n").strip()

        tokens_in = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens

        try:
            data = _json.loads(text)
            score = float(data.get("score", 0))
            reasoning = str(data.get("reasoning", ""))
            missing = list(data.get("missing_skills") or [])
        except Exception:
            score, reasoning, missing = 0, "Bewertung fehlgeschlagen (ungültiges JSON).", []

        cost = round(((tokens_in * COST_USD_PER_1M_IN +
                       tokens_out * COST_USD_PER_1M_OUT) / 1_000_000) * 100)
        return MatchResult(score=score, reasoning=reasoning, missing_skills=missing,
                           tokens_in=tokens_in, tokens_out=tokens_out,
                           cost_cents=max(1, cost))

    def test_connection(self) -> bool:
        try:
            self.client.messages.create(
                model=self.model, max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 5: Tests passen + Commit**

```bash
mkdir -p services/ai_providers
touch services/ai_providers/__init__.py
pytest tests/services/test_ai_providers_anthropic.py -v
git add services/ai_providers/ tests/services/test_ai_providers_anthropic.py
git commit -m "feat: AnthropicProvider (offizielle SDK)"
```

---

## Task 5: OpenAI-Compat Provider

**Files:**
- Create: `services/ai_providers/openai_compat.py`
- Test: `tests/services/test_ai_providers_openai_compat.py`

- [ ] **Step 1: Failing-Test**

```python
import responses
import json
from services.ai_providers.openai_compat import OpenAICompatProvider


@responses.activate
def test_openai_compat_match():
    responses.add(
        responses.POST,
        "http://localhost:11434/v1/chat/completions",
        json={
            "choices": [{"message": {"content": '{"score": 75, "reasoning": "ok", "missing_skills": ["k8s"]}'}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 50},
        },
        status=200,
    )

    p = OpenAICompatProvider(
        endpoint_url="http://localhost:11434/v1/chat/completions",
        model="llama3", api_key=None,
    )
    res = p.match_job(cv_summary="x", job={"title": "y", "description": "z", "location": "Berlin"})
    assert res.score == 75
    assert res.tokens_in == 300
    assert res.cost_cents == 0  # Self-Hosted


@responses.activate
def test_openai_compat_with_bearer():
    captured = {}
    def cb(req):
        captured['auth'] = req.headers.get('Authorization')
        return (200, {}, json.dumps({
            "choices": [{"message": {"content": '{"score":50,"reasoning":"x","missing_skills":[]}'}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10},
        }))
    responses.add_callback(responses.POST, "https://openrouter.ai/v1/chat/completions",
                           callback=cb, content_type="application/json")

    p = OpenAICompatProvider(
        endpoint_url="https://openrouter.ai/v1/chat/completions",
        model="meta/llama-3.1", api_key="sk-or-test",
    )
    p.match_job(cv_summary="x", job={"title": "y"})
    assert captured['auth'] == "Bearer sk-or-test"


@responses.activate
def test_openai_compat_test_connection_pings():
    responses.add(responses.POST, "http://localhost:11434/v1/chat/completions",
                  json={"choices": [{"message": {"content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
                  status=200)
    p = OpenAICompatProvider(endpoint_url="http://localhost:11434/v1/chat/completions",
                             model="llama3", api_key=None)
    assert p.test_connection() is True
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/ai_providers/openai_compat.py`**

```python
"""OpenAI-API-kompatibler Provider (Ollama, vLLM, LocalAI, OpenRouter, Groq, Together)."""
import json as _json
import requests

from services.ai_providers.base import AIProvider, MatchResult


PROMPT = """Du bewertest, wie gut die Stellenausschreibung zu meinem CV passt.

MEIN CV:
{cv}

STELLE:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit gültigem JSON:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["..."]}}"""


class OpenAICompatProvider(AIProvider):
    """Spricht beliebige OpenAI-Chat-Completions-Kompatible Endpoints an."""

    def __init__(self, endpoint_url: str, model: str, api_key: str | None,
                 auth_header_name: str = "Authorization"):
        self.endpoint = endpoint_url
        self.model = model
        self.api_key = api_key
        self.auth_header_name = auth_header_name

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            value = self.api_key if self.api_key.startswith("Bearer ") else f"Bearer {self.api_key}"
            h[self.auth_header_name] = value
        return h

    def _post(self, messages: list, max_tokens: int = 600) -> dict:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        r = requests.post(self.endpoint, json=body, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def match_job(self, cv_summary: str, job: dict) -> MatchResult:
        prompt = PROMPT.format(
            cv=cv_summary[:3000],
            title=job.get("title", ""),
            location=job.get("location", ""),
            description=(job.get("description") or "")[:5000],
        )
        data = self._post([{"role": "user", "content": prompt}])

        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json\n").strip()

        usage = data.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))

        try:
            parsed = _json.loads(text)
            score = float(parsed.get("score", 0))
            reasoning = str(parsed.get("reasoning", ""))
            missing = list(parsed.get("missing_skills") or [])
        except Exception:
            score, reasoning, missing = 0, "Bewertung fehlgeschlagen (ungültiges JSON).", []

        # Self-Hosted: cost 0. Externe Anbieter: nutzen ggf. eigene Cost-Header (später).
        return MatchResult(score=score, reasoning=reasoning, missing_skills=missing,
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_cents=0)

    def test_connection(self) -> bool:
        try:
            self._post([{"role": "user", "content": "ping"}], max_tokens=10)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/services/test_ai_providers_openai_compat.py -v
git add services/ai_providers/openai_compat.py tests/services/test_ai_providers_openai_compat.py
git commit -m "feat: OpenAICompatProvider (Ollama/vLLM/OpenRouter)"
```

---

## Task 6: Anthropic-Compat Provider

**Files:**
- Create: `services/ai_providers/anthropic_compat.py`
- Test: `tests/services/test_ai_providers_anthropic_compat.py`

- [ ] **Step 1: Failing-Test**

```python
import responses
from services.ai_providers.anthropic_compat import AnthropicCompatProvider


@responses.activate
def test_anthropic_compat_match():
    responses.add(
        responses.POST, "https://my-proxy.example/v1/messages",
        json={
            "content": [{"type": "text", "text": '{"score":80,"reasoning":"ok","missing_skills":[]}'}],
            "usage": {"input_tokens": 100, "output_tokens": 30},
        },
        status=200,
    )
    p = AnthropicCompatProvider(
        endpoint_url="https://my-proxy.example/v1/messages",
        model="claude-haiku-4-5-20251001",
        api_key="sk-test",
    )
    res = p.match_job(cv_summary="x", job={"title": "y"})
    assert res.score == 80
    assert res.tokens_in == 100
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/ai_providers/anthropic_compat.py`**

```python
"""Anthropic-API-kompatible Proxies (z.B. AWS Bedrock-Proxy, eigene Gateways)."""
import json as _json
import requests

from services.ai_providers.base import AIProvider, MatchResult


PROMPT = """Du bewertest, wie gut die Stellenausschreibung zu meinem CV passt.

MEIN CV:
{cv}

STELLE:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit gültigem JSON:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["..."]}}"""


class AnthropicCompatProvider(AIProvider):
    def __init__(self, endpoint_url: str, model: str, api_key: str):
        self.endpoint = endpoint_url
        self.model = model
        self.api_key = api_key

    def _post(self, messages: list, max_tokens: int = 600) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        body = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        r = requests.post(self.endpoint, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def match_job(self, cv_summary: str, job: dict) -> MatchResult:
        prompt = PROMPT.format(
            cv=cv_summary[:3000],
            title=job.get("title", ""),
            location=job.get("location", ""),
            description=(job.get("description") or "")[:5000],
        )
        data = self._post([{"role": "user", "content": prompt}])
        content = (data.get("content") or [{}])[0]
        text = content.get("text", "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json\n").strip()

        usage = data.get("usage") or {}
        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))

        try:
            parsed = _json.loads(text)
            score = float(parsed.get("score", 0))
            reasoning = str(parsed.get("reasoning", ""))
            missing = list(parsed.get("missing_skills") or [])
        except Exception:
            score, reasoning, missing = 0, "Bewertung fehlgeschlagen.", []

        return MatchResult(score=score, reasoning=reasoning, missing_skills=missing,
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_cents=0)

    def test_connection(self) -> bool:
        try:
            self._post([{"role": "user", "content": "ping"}], max_tokens=10)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/services/test_ai_providers_anthropic_compat.py -v
git add services/ai_providers/anthropic_compat.py tests/services/test_ai_providers_anthropic_compat.py
git commit -m "feat: AnthropicCompatProvider für Proxies"
```

---

## Task 7: Custom-Template Provider

**Files:**
- Create: `services/ai_providers/custom_template.py`
- Test: `tests/services/test_ai_providers_custom_template.py`

- [ ] **Step 1: Dependency**

`requirements.txt` ergänzen:
```
jsonpath-ng>=1.6
```

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Failing-Test**

```python
import responses
import json
from services.ai_providers.custom_template import CustomTemplateProvider


@responses.activate
def test_custom_template_renders_request_and_extracts_response():
    responses.add(
        responses.POST, "http://localhost:11434/api/generate",
        json={"response": '{"score":65,"reasoning":"ok","missing_skills":[]}',
              "prompt_eval_count": 200, "eval_count": 50},
        status=200,
    )
    request_template = {
        "model": "llama3",
        "prompt": "{{system}}\n\n{{prompt}}",
        "stream": False,
    }
    p = CustomTemplateProvider(
        endpoint_url="http://localhost:11434/api/generate",
        request_template=request_template,
        response_path="$.response",
        api_key=None,
    )
    res = p.match_job(cv_summary="x", job={"title": "Frontend"})
    assert res.score == 65


def test_renders_handles_missing_variables():
    p = CustomTemplateProvider(
        endpoint_url="http://x", request_template={"prompt": "{{prompt}}"},
        response_path="$.x", api_key=None,
    )
    rendered = p._render({"prompt": "hello"})
    assert rendered == {"prompt": "hello"}
```

- [ ] **Step 3: Test schlägt fehl**

- [ ] **Step 4: `services/ai_providers/custom_template.py`**

```python
"""Power-User-Provider: User-definiertes Request-Template + JSONPath-Response.

Mustache-Style-Variablen: {{prompt}}, {{system}}, {{cv_summary}},
                           {{job_title}}, {{job_description}}, {{job_location}}
"""
import json as _json
import re
import requests
from jsonpath_ng import parse as jp_parse

from services.ai_providers.base import AIProvider, MatchResult


VAR_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


_PROMPT = """Du bewertest, wie gut die Stellenausschreibung zu meinem CV passt.

MEIN CV:
{cv}

STELLE:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit gültigem JSON:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["..."]}}"""


class CustomTemplateProvider(AIProvider):
    """Power-User-Provider mit User-definiertem Template."""

    def __init__(self, endpoint_url: str, request_template: dict, response_path: str,
                 api_key: str | None,
                 auth_header_name: str = "Authorization"):
        self.endpoint = endpoint_url
        self.template = request_template
        self.response_path = jp_parse(response_path)
        self.api_key = api_key
        self.auth_header_name = auth_header_name

    def _render(self, vars: dict) -> dict:
        s = _json.dumps(self.template)

        def repl(match):
            key = match.group(1)
            value = vars.get(key, "")
            # Escape JSON-Sonderzeichen für Einbettung in JSON-String
            return _json.dumps(str(value))[1:-1]

        return _json.loads(VAR_RE.sub(repl, s))

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            value = self.api_key if self.api_key.startswith("Bearer ") else f"Bearer {self.api_key}"
            h[self.auth_header_name] = value
        return h

    def match_job(self, cv_summary: str, job: dict) -> MatchResult:
        full_prompt = _PROMPT.format(
            cv=cv_summary[:3000],
            title=job.get("title", ""),
            location=job.get("location", ""),
            description=(job.get("description") or "")[:5000],
        )
        body = self._render({
            "prompt": full_prompt,
            "system": "Du bist ein Job-Match-Bewerter.",
            "cv_summary": cv_summary,
            "job_title": job.get("title", ""),
            "job_description": job.get("description", ""),
            "job_location": job.get("location", ""),
        })
        r = requests.post(self.endpoint, json=body, headers=self._headers(), timeout=30)
        r.raise_for_status()
        data = r.json()

        matches = [m.value for m in self.response_path.find(data)]
        text = matches[0] if matches else ""
        if isinstance(text, str):
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1].lstrip("json\n").strip()

        # Token-Counts: best-effort, je nach Format unterschiedlich
        tokens_in = int(data.get("prompt_eval_count") or data.get("usage", {}).get("prompt_tokens") or 0)
        tokens_out = int(data.get("eval_count") or data.get("usage", {}).get("completion_tokens") or 0)

        try:
            parsed = _json.loads(text) if isinstance(text, str) else (text or {})
            score = float(parsed.get("score", 0))
            reasoning = str(parsed.get("reasoning", ""))
            missing = list(parsed.get("missing_skills") or [])
        except Exception:
            score, reasoning, missing = 0, "Bewertung fehlgeschlagen.", []

        return MatchResult(score=score, reasoning=reasoning, missing_skills=missing,
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_cents=0)

    def test_connection(self) -> bool:
        try:
            body = self._render({"prompt": "ping", "system": "", "cv_summary": "",
                                 "job_title": "", "job_description": "", "job_location": ""})
            r = requests.post(self.endpoint, json=body, headers=self._headers(), timeout=15)
            return r.status_code < 500
        except Exception:
            return False
```

- [ ] **Step 5: Tests passen + Commit**

```bash
pytest tests/services/test_ai_providers_custom_template.py -v
git add services/ai_providers/custom_template.py tests/services/test_ai_providers_custom_template.py requirements.txt
git commit -m "feat: CustomTemplateProvider mit Mustache+JSONPath"
```

---

## Task 8: KeyCache (TTL-basiert)

**Files:**
- Create: `services/ai_providers/key_cache.py`
- Test: `tests/services/test_key_cache_ai.py`

- [ ] **Step 1: Failing-Test**

```python
import time
from services.ai_providers.key_cache import AIKeyCache


def test_cache_hit_within_ttl():
    cache = AIKeyCache(ttl_seconds=60)
    cache.put("user1:anthropic", "secret-key")
    assert cache.get("user1:anthropic") == "secret-key"


def test_cache_miss_after_expiry():
    cache = AIKeyCache(ttl_seconds=0.1)
    cache.put("user1:anthropic", "secret-key")
    time.sleep(0.15)
    assert cache.get("user1:anthropic") is None


def test_invalidate():
    cache = AIKeyCache(ttl_seconds=60)
    cache.put("k", "v")
    cache.invalidate("k")
    assert cache.get("k") is None


def test_invalidate_user():
    cache = AIKeyCache(ttl_seconds=60)
    cache.put("user1:anthropic", "v1")
    cache.put("user1:openai", "v2")
    cache.put("user2:anthropic", "v3")
    cache.invalidate_user("user1")
    assert cache.get("user1:anthropic") is None
    assert cache.get("user1:openai") is None
    assert cache.get("user2:anthropic") == "v3"
```

- [ ] **Step 2: Test schlägt fehl**

- [ ] **Step 3: `services/ai_providers/key_cache.py`**

```python
"""TTL-basierter Cache für entschlüsselte AI-Credentials.

Reduziert Crypto-Overhead bei vielen Match-Operationen pro Tick.
"""
import time
from threading import Lock


class AIKeyCache:
    def __init__(self, ttl_seconds: float = 300):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[any, float]] = {}
        self._lock = Lock()

    def put(self, key: str, value):
        with self._lock:
            self._store[key] = (value, time.time())

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def invalidate(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def invalidate_user(self, user_id: str):
        with self._lock:
            for k in list(self._store.keys()):
                if k.startswith(f"{user_id}:"):
                    del self._store[k]


# Globale Instanz (App-weit, in-memory)
ai_key_cache = AIKeyCache(ttl_seconds=300)
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/services/test_key_cache_ai.py -v
git add services/ai_providers/key_cache.py tests/services/test_key_cache_ai.py
git commit -m "feat: TTL-basierter KeyCache für entschlüsselte AI-Credentials"
```

---

## Task 9: Provider-Factory

**Files:**
- Modify: `services/ai_providers/__init__.py`
- Test: `tests/services/test_ai_provider_factory.py`

- [ ] **Step 1: Failing-Test**

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from services.ai_providers import AIProviderFactory, NoCredentialsError
from services.ai_providers.anthropic_provider import AnthropicProvider
from services.ai_providers.openai_compat import OpenAICompatProvider


def test_returns_anthropic_for_active_user_creds(app, user_factory_with_dek):
    user, dek = user_factory_with_dek()
    from models import UserAICredentials
    from services.credentials_crypto import encrypt_secret
    blob, _ = encrypt_secret("sk-ant-real", dek)
    cred = UserAICredentials(
        user_id=user.id, provider='anthropic',
        encrypted_api_key=blob, key_nonce=b'',
        default_model='claude-haiku-4-5-20251001',
        is_active=True,
    )
    db.session.add(cred); db.session.commit()

    factory = AIProviderFactory(get_user_dek=lambda uid: dek)
    provider = factory.get_provider(user.id)
    assert isinstance(provider, AnthropicProvider)


def test_raises_when_no_credentials_and_fallback_disabled(app, user_factory, monkeypatch):
    monkeypatch.setenv("ALLOW_SERVER_FALLBACK_KEY", "false")
    user = user_factory()
    factory = AIProviderFactory(get_user_dek=lambda uid: b"x" * 32)
    with pytest.raises(NoCredentialsError):
        factory.get_provider(user.id)


def test_returns_server_fallback_when_enabled(app, user_factory, monkeypatch):
    monkeypatch.setenv("ALLOW_SERVER_FALLBACK_KEY", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-server")
    user = user_factory()
    factory = AIProviderFactory(get_user_dek=lambda uid: b"x" * 32)
    provider = factory.get_provider(user.id)
    assert isinstance(provider, AnthropicProvider)
```

- [ ] **Step 2: `user_factory_with_dek`-Fixture in conftest ergänzen**

In `tests/conftest.py`:
```python
@pytest.fixture
def user_factory_with_dek(app, user_factory):
    """Erstellt einen User mit funktionierendem DEK (für Crypto-Tests)."""
    from services.encryption_service import EncryptionService

    def _create(**kwargs):
        u = user_factory(**kwargs)
        salt = EncryptionService.generate_salt()
        dek = EncryptionService.generate_dek()
        kek = EncryptionService.derive_kek("password123", salt)
        u.encryption_salt = salt
        u.encrypted_data_key = EncryptionService.wrap_dek(dek, kek)
        db.session.commit()
        return u, dek
    return _create
```

> ⚠️ Falls `wrap_dek` in deinem EncryptionService anders heißt, anpassen — Methodennamen aus `services/encryption_service.py` übernehmen.

- [ ] **Step 3: `services/ai_providers/__init__.py`**

```python
"""Provider-Registry + Factory."""
import os

from services.ai_providers.base import AIProvider, MatchResult
from services.ai_providers.anthropic_provider import AnthropicProvider
from services.ai_providers.openai_compat import OpenAICompatProvider
from services.ai_providers.anthropic_compat import AnthropicCompatProvider
from services.ai_providers.custom_template import CustomTemplateProvider
from services.ai_providers.key_cache import ai_key_cache
from services.credentials_crypto import decrypt_secret


class NoCredentialsError(Exception):
    pass


class AIProviderFactory:
    """Resolved User-Credentials → konkretes Provider-Objekt.

    Args:
        get_user_dek: Callback (user_id → DEK-bytes) für Decryption.
                      In Production via session/imap-cache analog zu
                      bestehendem Pattern.
    """
    def __init__(self, get_user_dek):
        self._get_user_dek = get_user_dek

    def get_provider(self, user_id: str) -> AIProvider:
        from models import UserAICredentials

        cred = (UserAICredentials.query
                .filter(UserAICredentials.user_id == user_id,
                        UserAICredentials.is_active == True)
                .order_by(
                    db.case(
                        (UserAICredentials.provider == 'anthropic', 0),
                        else_=1
                    )
                ).first())

        if cred:
            return self._build_from_credentials(cred, user_id)

        # Fallback: Server-Key
        if os.getenv("ALLOW_SERVER_FALLBACK_KEY", "false").lower() == "true":
            server_key = os.getenv("ANTHROPIC_API_KEY")
            if server_key:
                return AnthropicProvider(
                    api_key=server_key,
                    model=os.getenv("CLAUDE_DEFAULT_MODEL", "claude-haiku-4-5-20251001"),
                )

        raise NoCredentialsError(f"User {user_id} hat keine aktiven AI-Credentials")

    def _decrypt_with_cache(self, user_id: str, provider: str, blob: bytes, nonce: bytes,
                            cache_suffix: str) -> str:
        cache_key = f"{user_id}:{provider}:{cache_suffix}"
        cached = ai_key_cache.get(cache_key)
        if cached:
            return cached
        dek = self._get_user_dek(user_id)
        plain = decrypt_secret(blob, nonce, dek)
        ai_key_cache.put(cache_key, plain)
        return plain

    def _build_from_credentials(self, cred, user_id: str) -> AIProvider:
        api_key = None
        if cred.encrypted_api_key:
            api_key = self._decrypt_with_cache(
                user_id, cred.provider, cred.encrypted_api_key, cred.key_nonce, "key")

        auth_value = None
        if cred.encrypted_auth_header_value:
            auth_value = self._decrypt_with_cache(
                user_id, cred.provider, cred.encrypted_auth_header_value, cred.auth_nonce, "auth")

        if cred.provider == 'anthropic':
            return AnthropicProvider(api_key=api_key, model=cred.default_model)

        if cred.provider == 'custom_openai_compat':
            return OpenAICompatProvider(
                endpoint_url=cred.endpoint_url,
                model=cred.default_model,
                api_key=auth_value or api_key,
                auth_header_name=cred.auth_header_name or "Authorization",
            )

        if cred.provider == 'custom_anthropic_compat':
            return AnthropicCompatProvider(
                endpoint_url=cred.endpoint_url,
                model=cred.default_model,
                api_key=api_key or auth_value,
            )

        if cred.provider == 'custom_template':
            return CustomTemplateProvider(
                endpoint_url=cred.endpoint_url,
                request_template=cred.request_template or {},
                response_path=cred.response_path or "$",
                api_key=auth_value or api_key,
                auth_header_name=cred.auth_header_name or "Authorization",
            )

        raise ValueError(f"Unbekannter Provider: {cred.provider}")


# Re-Export für convenience
__all__ = [
    "AIProvider", "MatchResult", "AIProviderFactory", "NoCredentialsError",
    "AnthropicProvider", "OpenAICompatProvider",
    "AnthropicCompatProvider", "CustomTemplateProvider",
]
```

> Hinweis: Für `db.case` in der Sortierung: `from database import db` ergänzen.

- [ ] **Step 4: Tests passen**

```bash
pytest tests/services/test_ai_provider_factory.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/ai_providers/__init__.py tests/services/test_ai_provider_factory.py tests/conftest.py
git commit -m "feat: AIProviderFactory mit per-User Credentials und Fallback"
```

---

## Task 10: BYOK REST-API

**Files:**
- Create: `api/ai_credentials.py`
- Modify: `app.py`
- Test: `tests/api/test_ai_credentials.py`

- [ ] **Step 1: Failing-Test**

```python
import pytest
from app import create_app
from database import db
from models import UserAICredentials


@pytest.fixture
def app(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app, user_factory_with_dek):
    from services.auth_service import create_session_token
    user, dek = user_factory_with_dek()
    token = create_session_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user, dek


def test_create_anthropic_credentials_masks_key(client, auth_header):
    headers, user, _ = auth_header
    r = client.post("/api/ai-credentials", json={
        "provider": "anthropic",
        "api_key": "sk-ant-test-1234567890abcdef",
        "default_model": "claude-haiku-4-5-20251001",
    }, headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    assert "api_key" not in body  # nie zurückgeben
    assert body["provider"] == "anthropic"
    assert body["is_active"] is False  # Test-Pflicht vor Aktivierung
    assert body["key_preview"].endswith("cdef")
    assert body["key_preview"].startswith("sk-ant")


def test_create_custom_openai_endpoint(client, auth_header):
    headers, user, _ = auth_header
    r = client.post("/api/ai-credentials", json={
        "provider": "custom_openai_compat",
        "endpoint_url": "http://localhost:11434/v1/chat/completions",
        "default_model": "llama3",
    }, headers=headers)
    assert r.status_code == 201


def test_list_returns_only_own(client, auth_header):
    headers, user, _ = auth_header
    db.session.add(UserAICredentials(user_id=user.id, provider='anthropic',
                                     encrypted_api_key=b'1', key_nonce=b'1',
                                     default_model='m'))
    db.session.add(UserAICredentials(user_id="other-user", provider='anthropic',
                                     encrypted_api_key=b'2', key_nonce=b'2',
                                     default_model='m'))
    db.session.commit()
    r = client.get("/api/ai-credentials", headers=headers)
    body = r.get_json()
    assert len(body["credentials"]) == 1
    assert body["credentials"][0]["user_id"] == user.id


def test_delete_own_only(client, auth_header):
    headers, user, _ = auth_header
    other = UserAICredentials(user_id="other", provider='anthropic',
                              encrypted_api_key=b'1', key_nonce=b'1', default_model='m')
    db.session.add(other); db.session.commit()
    r = client.delete(f"/api/ai-credentials/{other.id}", headers=headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Tests schlagen fehl**

- [ ] **Step 3: `api/ai_credentials.py`**

```python
"""User-API für AI-Credentials (BYOK)."""
from flask import Blueprint, request, jsonify, g

from database import db
from models import UserAICredentials
from services.auth_service import require_auth
from services.credentials_crypto import encrypt_secret
from services.ai_providers.key_cache import ai_key_cache


ai_creds_bp = Blueprint('ai_credentials', __name__, url_prefix='/api/ai-credentials')

VALID_PROVIDERS = {'anthropic', 'custom_openai_compat',
                   'custom_anthropic_compat', 'custom_template'}


def _get_user_dek():
    """Holt den DEK des aktuell eingeloggten Users.

    Erfordert dass der DEK in der Session gehalten wird (analog IMAP-Pattern).
    Falls dein Auth-System dies anders macht: hier den Lookup anpassen.
    """
    from services.auth_service import get_current_user_dek  # ggf. existierende Helper
    return get_current_user_dek()


def _mask(secret: str) -> str:
    if not secret or len(secret) < 8:
        return "***"
    return secret[:6] + "…" + secret[-4:]


def _serialize(c: UserAICredentials, key_preview: str | None = None) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "provider": c.provider,
        "default_model": c.default_model,
        "endpoint_url": c.endpoint_url,
        "auth_header_name": c.auth_header_name,
        "monthly_budget_cents": c.monthly_budget_cents,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "key_preview": key_preview,
    }


@ai_creds_bp.get('')
@require_auth
def list_credentials():
    creds = UserAICredentials.query.filter_by(user_id=g.user_id).all()
    return jsonify({"credentials": [_serialize(c) for c in creds]}), 200


@ai_creds_bp.post('')
@require_auth
def create_credentials():
    data = request.get_json() or {}
    provider = data.get("provider")
    if provider not in VALID_PROVIDERS:
        return jsonify({"error": f"provider muss in {VALID_PROVIDERS} sein"}), 400

    # SSRF-Hinweis: Custom-Endpoints erlauben localhost (gewünscht für Self-Hosted)
    if provider != "anthropic":
        if not data.get("endpoint_url"):
            return jsonify({"error": "endpoint_url für custom_*-Provider erforderlich"}), 400

    if provider == "custom_template":
        if not data.get("request_template") or not data.get("response_path"):
            return jsonify({"error": "request_template und response_path erforderlich"}), 400

    cred = UserAICredentials(
        user_id=g.user_id, provider=provider,
        endpoint_url=data.get("endpoint_url"),
        auth_header_name=data.get("auth_header_name"),
        default_model=data.get("default_model"),
        monthly_budget_cents=data.get("monthly_budget_cents"),
        is_active=False,  # erst nach erfolgreichem /test
    )
    if data.get("request_template"):
        cred.request_template = data["request_template"]
    if data.get("response_path"):
        cred.response_path = data["response_path"]

    api_key = data.get("api_key")
    auth_value = data.get("auth_header_value")
    key_preview = None

    if api_key or auth_value:
        dek = _get_user_dek()
        if api_key:
            blob, nonce = encrypt_secret(api_key, dek)
            cred.encrypted_api_key = blob
            cred.key_nonce = nonce
            key_preview = _mask(api_key)
        if auth_value:
            blob, nonce = encrypt_secret(auth_value, dek)
            cred.encrypted_auth_header_value = blob
            cred.auth_nonce = nonce

    db.session.add(cred)
    db.session.commit()
    return jsonify(_serialize(cred, key_preview)), 201


@ai_creds_bp.patch('/<int:cred_id>')
@require_auth
def update_credentials(cred_id: int):
    cred = UserAICredentials.query.get_or_404(cred_id)
    if cred.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    if "default_model" in data:
        cred.default_model = data["default_model"]
    if "monthly_budget_cents" in data:
        cred.monthly_budget_cents = data["monthly_budget_cents"]
    if "is_active" in data:
        cred.is_active = bool(data["is_active"])

    if "api_key" in data:
        dek = _get_user_dek()
        blob, nonce = encrypt_secret(data["api_key"], dek)
        cred.encrypted_api_key = blob
        cred.key_nonce = nonce
        cred.is_active = False  # Re-Test erforderlich
        ai_key_cache.invalidate_user(g.user_id)

    db.session.commit()
    return jsonify(_serialize(cred)), 200


@ai_creds_bp.delete('/<int:cred_id>')
@require_auth
def delete_credentials(cred_id: int):
    cred = UserAICredentials.query.get_or_404(cred_id)
    if cred.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(cred)
    ai_key_cache.invalidate_user(g.user_id)
    db.session.commit()
    return ('', 204)


@ai_creds_bp.post('/<int:cred_id>/test')
@require_auth
def test_credentials(cred_id: int):
    """Mini-Aufruf zur Validierung. Setzt is_active=True bei Erfolg."""
    from services.ai_providers import AIProviderFactory

    cred = UserAICredentials.query.get_or_404(cred_id)
    if cred.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    factory = AIProviderFactory(get_user_dek=lambda uid: _get_user_dek())
    # Temporär zur Auswertung als wäre cred aktiv
    was_active = cred.is_active
    cred.is_active = True
    db.session.flush()
    try:
        provider = factory.get_provider(cred.user_id)
        ok = provider.test_connection()
    except Exception as e:
        ok = False
        err = str(e)
    else:
        err = None

    cred.is_active = ok or was_active
    db.session.commit()

    return jsonify({"ok": ok, "error": err if not ok else None,
                    "credentials": _serialize(cred)}), 200
```

- [ ] **Step 4: Blueprint in `app.py` registrieren**

```python
from api.ai_credentials import ai_creds_bp
app.register_blueprint(ai_creds_bp)
```

- [ ] **Step 5: Tests passen + Commit**

```bash
pytest tests/api/test_ai_credentials.py -v
git add api/ai_credentials.py app.py tests/api/test_ai_credentials.py
git commit -m "feat: BYOK REST-API für AI-Credentials (CRUD + Test)"
```

---

## Task 11: Refactor Stage 3 auf Provider-Factory

**Files:**
- Modify: `api/jobs_cron.py`
- Test: `tests/api/test_jobs_cron.py`

- [ ] **Step 1: Failing-Test (User mit BYOK)**

In `tests/api/test_jobs_cron.py` ergänzen:
```python
@patch("services.ai_providers.openai_compat.requests.post")
def test_claude_match_uses_user_byok_custom_endpoint(mock_post, app, client,
                                                     user_factory_with_dek):
    user, dek = user_factory_with_dek(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react"], "summary": "x"}}),
    )
    # Custom Endpoint Credentials anlegen
    from models import UserAICredentials
    cred = UserAICredentials(
        user_id=user.id, provider='custom_openai_compat',
        endpoint_url="http://localhost:11434/v1/chat/completions",
        default_model="llama3", is_active=True,
    )
    db.session.add(cred); db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1", title="React", url="x",
                 description="React, TypeScript", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                            prefilter_score=80))
    db.session.commit()

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "choices": [{"message": {"content": '{"score":75,"reasoning":"ok","missing_skills":[]}'}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 30},
        },
        raise_for_status=lambda: None,
    )

    r = client.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})
    body = r.get_json()
    assert body["matched"] == 1

    from models import ApiCall
    call = ApiCall.query.first()
    assert call.key_owner == 'custom_endpoint'
    assert call.cost == 0.0  # Self-Hosted, kein Cost
```

- [ ] **Step 2: Refactor `claude_match()` in `api/jobs_cron.py`**

Folgende Phase-A-Artefakte werden in diesem Step entfernt/ersetzt:
- `_get_anthropic_client()`-Funktion → ersatzlos entfernen
- Direkter `Anthropic(api_key=...)` Aufruf → durch `AIProviderFactory.get_provider(user_id)` ersetzt
- Konstanten `COST_USD_PER_1M_TOKENS_IN/OUT` → bleiben, werden aber nur noch als Fallback genutzt (Provider liefern eigene cost_cents)
- `services/job_matching/claude_matcher.py` → wird nicht mehr aus Stage 3 referenziert. **Datei kann gelöscht werden** wenn keine andere Stelle sie nutzt (`grep -rn "claude_matcher" .` zur Sicherheit). Der Prompt-Template-Inhalt zieht in die Provider (`anthropic_provider.py` etc.) um — was bereits in Tasks 4-7 passiert ist.

Ersetze den bisherigen Anthropic-Direct-Call durch Provider-Factory:

```python
from services.ai_providers import AIProviderFactory, NoCredentialsError


class _DekUnavailable(Exception):
    pass


def _get_user_dek_for_cron(user_id: str) -> bytes:
    """Cron-Pfad: DEK pro User aus dem In-Memory-Cache.

    Voraussetzung: User hat sich mind. 1× eingeloggt seit App-Start.
    Falls DEK nicht im Cache: explizite Exception (kein TypeError-Bug),
    der Caller überspringt den User graceful.
    """
    from services.key_cache import dek_cache  # Bestehender DEK-Cache aus Phase 2
    dek = dek_cache.get(user_id)
    if not dek:
        raise _DekUnavailable(f"DEK für user {user_id} nicht im Cache (User noch nicht eingeloggt seit Start)")
    return dek


@jobs_cron_bp.post('/claude-match')
@require_cron_token
def claude_match():
    started = time.time()

    factory = AIProviderFactory(get_user_dek=_get_user_dek_for_cron)
    matched, skipped_budget, skipped_no_creds = 0, 0, 0

    users_with_pending = (db.session.query(User)
                          .join(JobMatch, JobMatch.user_id == User.id)
                          .filter(JobMatch.match_score.is_(None),
                                  JobMatch.prefilter_score >= PREFILTER_DISMISS_THRESHOLD,
                                  JobMatch.status == 'new')
                          .distinct().all())

    for user in users_with_pending:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if _user_today_cost_cents(user.id) >= user.job_daily_budget_cents:
            skipped_budget += 1
            continue

        try:
            provider = factory.get_provider(user.id)
        except (NoCredentialsError, _DekUnavailable):
            # User hat keine Credentials oder ist nicht eingeloggt → skip graceful
            skipped_no_creds += 1
            continue

        candidates = (JobMatch.query
                      .filter(JobMatch.user_id == user.id,
                              JobMatch.match_score.is_(None),
                              JobMatch.prefilter_score >= PREFILTER_DISMISS_THRESHOLD,
                              JobMatch.status == 'new')
                      .order_by(JobMatch.prefilter_score.desc())
                      .limit(user.job_claude_budget_per_tick).all())

        cv_summary = _build_cv_summary(user.cv_data_json)
        provider_type = type(provider).__name__
        key_owner = (
            'user' if provider_type == 'AnthropicProvider'
            else 'custom_endpoint'
        )

        for match in candidates:
            if time.time() - started > HARD_TIME_LIMIT_SEC:
                break
            raw = RawJob.query.get(match.raw_job_id)
            try:
                result = provider.match_job(
                    cv_summary=cv_summary,
                    job={"title": raw.title, "description": raw.description, "location": raw.location},
                )
            except Exception:
                continue

            match.match_score = result.score
            match.match_reasoning = result.reasoning
            match.missing_skills = result.missing_skills
            raw.crawl_status = 'matched'

            db.session.add(ApiCall(
                user_id=user.id, endpoint='/api/jobs/claude-match',
                model=provider.model if hasattr(provider, 'model') else 'unknown',
                tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                cost=result.cost_cents / 100.0,
                key_owner=key_owner,
            ))
            matched += 1

        db.session.commit()

    return jsonify({
        "matched": matched,
        "skipped_budget": skipped_budget,
        "skipped_no_credentials": skipped_no_creds,
        "duration_sec": round(time.time() - started, 2),
    }), 200
```

- [ ] **Step 3: Tests passen — auch der Phase-A-Test (mit Server-Fallback) muss noch grün sein**

```bash
# Setze ALLOW_SERVER_FALLBACK_KEY=true für Phase-A-Test-Kompatibilität
ALLOW_SERVER_FALLBACK_KEY=true ANTHROPIC_API_KEY=sk-test pytest tests/api/test_jobs_cron.py -v
```

> Falls der Phase-A-Test fehlschlägt, weil er den Mock auf `_get_anthropic_client` setzt: in den Test umstellen auf Mock auf `AIProviderFactory.get_provider` ODER den User mit BYOK-Credentials ausstatten.

- [ ] **Step 4: Commit**

```bash
git add api/jobs_cron.py tests/api/test_jobs_cron.py
git commit -m "refactor: claude_match nutzt AIProviderFactory (BYOK + Server-Fallback)"
```

---

## Task 12: Cost-Tracking-Erweiterung (Statistik per `key_owner`)

**Files:**
- Modify: `routing_service.py` (oder bestehender Stats-Service)
- Test: ergänzen falls bestehende Stats-Tests da

- [ ] **Step 1: Aggregations-Query**

In `routing_service.py` (ersetzt Placeholder):
```python
@staticmethod
def get_user_stats(user_id: str, days: int = 30) -> dict:
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (db.session.query(
                ApiCall.key_owner,
                db.func.count(ApiCall.id).label('calls'),
                db.func.sum(ApiCall.tokens_in).label('tokens_in'),
                db.func.sum(ApiCall.tokens_out).label('tokens_out'),
                db.func.sum(ApiCall.cost).label('cost'),
            )
            .filter(ApiCall.user_id == user_id, ApiCall.timestamp >= cutoff)
            .group_by(ApiCall.key_owner).all())
    return {
        "by_key_owner": [
            {
                "key_owner": r.key_owner,
                "calls": r.calls or 0,
                "tokens_in": int(r.tokens_in or 0),
                "tokens_out": int(r.tokens_out or 0),
                "cost_cents": int((r.cost or 0) * 100),
            }
            for r in rows
        ],
        "total_cost_cents": int(sum((r.cost or 0) for r in rows) * 100),
    }
```

- [ ] **Step 2: Endpoint im AI-Credentials-Blueprint ergänzen**

```python
@ai_creds_bp.get('/usage')
@require_auth
def usage_stats():
    days = request.args.get("days", type=int, default=30)
    from routing_service import RoutingService
    return jsonify(RoutingService.get_user_stats(g.user_id, days)), 200
```

- [ ] **Step 3: Test ergänzen**

```python
def test_usage_stats_grouped_by_key_owner(client, auth_header):
    headers, user, _ = auth_header
    from datetime import datetime
    db.session.add_all([
        ApiCall(user_id=user.id, endpoint='/x', model='m',
                tokens_in=100, tokens_out=20, cost=0.005, key_owner='user'),
        ApiCall(user_id=user.id, endpoint='/x', model='m',
                tokens_in=200, tokens_out=40, cost=0.0, key_owner='custom_endpoint'),
    ])
    db.session.commit()

    r = client.get("/api/ai-credentials/usage", headers=headers)
    body = r.get_json()
    owners = {row["key_owner"]: row for row in body["by_key_owner"]}
    assert owners["user"]["calls"] == 1
    assert owners["custom_endpoint"]["calls"] == 1
    assert owners["custom_endpoint"]["cost_cents"] == 0
```

- [ ] **Step 4: Tests passen + Commit**

```bash
pytest tests/api/test_ai_credentials.py -v
git add api/ai_credentials.py routing_service.py tests/api/test_ai_credentials.py
git commit -m "feat: Cost-Tracking-Statistik per key_owner"
```

---

## Task 13: Doku-Update + Manuelle QA

**Files:**
- Modify: `docs/FEATURES/JOB_DISCOVERY.md`

- [ ] **Step 1: BYOK-Sektion ergänzen**

```markdown
## BYOK (Bring Your Own Key) — Phase B

Statt eines zentralen Server-Keys können User ihre eigenen AI-Provider hinterlegen.
Cost fällt dann beim User-Account an, nicht am Server.

### Provider-Typen

1. **Anthropic (offiziell)** — eigener `sk-ant-...`-Key
2. **OpenAI-kompatibel** — Ollama, LM Studio, vLLM, OpenRouter, Groq
3. **Anthropic-kompatibel** — Proxies, Gateways
4. **Custom Template** — Power-User mit eigenem JSON-Format

### Setup-Beispiele

**Ollama lokal (kostenlos):**
```bash
curl -X POST http://localhost:5000/api/ai-credentials \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "custom_openai_compat",
    "endpoint_url": "http://localhost:11434/v1/chat/completions",
    "default_model": "llama3"
  }'

# Test
curl -X POST http://localhost:5000/api/ai-credentials/<id>/test \
  -H "Authorization: Bearer $JWT"
```

**Eigener Anthropic-Key:**
```bash
curl -X POST http://localhost:5000/api/ai-credentials \
  -H "Authorization: Bearer $JWT" -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-api03-...",
    "default_model": "claude-haiku-4-5-20251001",
    "monthly_budget_cents": 1000
  }'
```

### ENV-Konfiguration

```bash
ALLOW_SERVER_FALLBACK_KEY=false   # User MÜSSEN eigenen Key hinterlegen
ALLOW_CUSTOM_ENDPOINTS=true       # Self-Hosted Endpoints erlauben
```
```

- [ ] **Step 2: Manueller Smoke-Test**

```bash
# 1. Migrations
python scripts/migrate_byok.py

# 2. Eigene Anthropic-Credentials per API hinterlegen
curl -X POST http://localhost:5000/api/ai-credentials -H "Authorization: Bearer $JWT" \
  -d '{"provider":"anthropic","api_key":"sk-ant-...","default_model":"claude-haiku-4-5-20251001"}'

# 3. Testen
curl -X POST http://localhost:5000/api/ai-credentials/<id>/test -H "Authorization: Bearer $JWT"

# 4. Pipeline triggern, prüfen dass key_owner='user' in api_calls
curl -X POST http://localhost:5000/api/jobs/claude-match -H "X-Cron-Token: $JOB_CRON_TOKEN"
sqlite3 bewerbungen.db "SELECT key_owner, count(*) FROM api_calls GROUP BY key_owner;"

# 5. Statistik abfragen
curl http://localhost:5000/api/ai-credentials/usage -H "Authorization: Bearer $JWT"
```

- [ ] **Step 3: Final-Commit**

```bash
git add docs/FEATURES/JOB_DISCOVERY.md
git commit -m "docs: BYOK-Sektion in Job-Discovery Doku"
```

---

## Task 14: Full-Test-Run

- [ ] **Step 1: Alle Tests**

```bash
pytest tests/ -v
```

- [ ] **Step 2: Coverage**

```bash
pytest tests/services/test_ai_providers_*.py tests/services/test_ai_provider_factory.py \
       tests/services/test_credentials_crypto.py tests/services/test_key_cache_ai.py \
       tests/api/test_ai_credentials.py \
       --cov=services/ai_providers --cov=services/credentials_crypto \
       --cov=api/ai_credentials --cov-report=term-missing
```
Erwartet: ≥ 80% je Modul, 100% für credentials_crypto.

---

## Phase B — Definition of Done

- ✅ `UserAICredentials`-Tabelle mit envelope-encrypted Keys
- ✅ 4 Provider-Typen (Anthropic, OpenAI-compat, Anthropic-compat, Custom-Template)
- ✅ `AIProviderFactory` mit per-User-Lookup + Server-Fallback
- ✅ `AIKeyCache` (TTL 5 Min) reduziert Crypto-Overhead
- ✅ REST-API für Credentials (CRUD + Test)
- ✅ Stage 3 (claude-match) refactored auf Factory
- ✅ Cost-Tracking unterscheidet `server`/`user`/`custom_endpoint`
- ✅ Coverage ≥80% / 100% für Crypto
- ✅ Doku aktualisiert

User können jetzt eigene AI-Credentials hinterlegen. Cost fällt bei BYOK auf den
User-Account; Server-Key dient nur noch als Demo-Fallback (per ENV abschaltbar).
