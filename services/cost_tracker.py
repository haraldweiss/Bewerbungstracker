# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Zentralisiertes Cost-Tracking fuer alle AI-Calls.

Ersetzt die fruehere lokale Logik in api/jobs_cron.py — single source of
truth fuer Tageskosten + Modell-aware Cost-Estimation. Ermoeglicht das
globale Daily-Budget-Cap im ai_provider_client.chat()-Wrapper.
"""

from datetime import datetime
from database import db
from models import ApiCall


# Anthropic-Pricing (USD pro 1M Tokens). Aktualisierung wenn sich Modell-Preise aendern.
_PRICING = {
    'claude-haiku-4-5-20251001':  (1.00,  5.00),
    'claude-haiku-4-5':            (1.00,  5.00),  # alias
    'claude-sonnet-4-6':           (3.00, 15.00),
    'claude-opus-4-7':            (15.00, 75.00),
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Berechnet USD-Kosten basierend auf Modell-Pricing.

    Ollama- und andere lokale Modelle: 0.0 (= kein API-Bill).
    Unbekannte Claude-Modelle: 0.0 (conservative — lieber 0 als wilde Schaetzung).
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        return 0.0
    in_per_m, out_per_m = pricing
    return (tokens_in / 1_000_000) * in_per_m + (tokens_out / 1_000_000) * out_per_m


def record_call(user_id: str, endpoint: str, model: str,
                tokens_in: int, tokens_out: int, cost_usd: float,
                key_owner: str = 'server') -> None:
    """Schreibt einen ApiCall-Eintrag. Caller muss db.session.commit() selbst aufrufen."""
    db.session.add(ApiCall(
        user_id=user_id, endpoint=endpoint,
        model=model, tokens_in=tokens_in, tokens_out=tokens_out,
        cost=cost_usd, key_owner=key_owner,
    ))
    db.session.flush()


def user_today_cost_cents(user_id: str) -> int:
    """Summiert ApiCall.cost fuer den User seit Mitternacht UTC. Returns cents."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (db.session.query(db.func.sum(ApiCall.cost))
             .filter(ApiCall.user_id == user_id, ApiCall.timestamp >= today_start)
             .scalar()) or 0.0
    return int(round(total * 100))
