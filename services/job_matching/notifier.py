"""Push-Notifications für Match-Treffer.

Phase A: Stub mit logging — wird durch echten Push-Service ersetzt.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _send_push(user_id: str, title: str, body: str, url: str | None = None):
    """Hooks for tests + production push.

    Wird durch echten Push-Service ersetzt. Aktuell loggt nur.
    """
    logger.info("PUSH user=%s title=%r body=%r url=%s", user_id, title, body, url)


def send_match_notification(user_id: str, title: str, company: str | None,
                             score: float, url: str):
    body = f"Match {score:.0f}: {title}" + (f" @ {company}" if company else "")
    _send_push(user_id=user_id, title="Neuer Job-Vorschlag", body=body, url=url)
