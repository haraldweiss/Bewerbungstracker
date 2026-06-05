# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /train-pattern. Logik aus api/jobs_user.py extrahiert."""
from __future__ import annotations

import json as _json
import re as _re
from datetime import datetime, timedelta
from typing import Callable, Optional

from database import db
from models import JobSource, LearnedEmailPattern, User
from services.tasks.registry import register


@register('pattern_learner_train')
def handle_pattern_learner_train(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """AI-Pattern-Training für eine Email-Source.

    Payload:
        user_id (str)
        source_id (int)
        sample_size (int)
        train_size (int)
        min_hit_rate (float)

    Returns: gleiches dict wie der frühere synchrone Endpoint auf success.
    Raises:  bei Fetch/Train/Validate-Fehlern.
    """
    # Lazy import (services → api allowed; same convention as email_import handler)
    from services.job_sources import pattern_learner as pl

    user = User.query.get(payload['user_id'])
    if user is None:
        raise ValueError(f"user_id {payload['user_id']!r} nicht gefunden")

    src = JobSource.query.get(payload['source_id'])
    if src is None or src.user_id != user.id:
        raise ValueError(f"source_id {payload['source_id']!r} nicht zugänglich")

    platform = src.type.removesuffix("_email")
    sample_size = int(payload.get('sample_size') or 20)
    train_size = int(payload.get('train_size') or 3)
    min_hit_rate = float(payload.get('min_hit_rate') or 0.40)

    if progress_cb:
        progress_cb(5, 'fetching mails')

    try:
        mails = pl.fetch_sample_mails(
            user,
            platform=platform,
            folder=src.config.get("folder", "INBOX"),
            lookback_days=int(src.config.get("lookback_days", 30)),
            n=sample_size,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"IMAP-Fetch fehlgeschlagen: {exc}") from exc

    # Mindestens 2 Mails noetig (1 train + 1 test). Bei weniger Mails als
    # train_size + 1 wird train_size automatisch reduziert, damit User mit
    # kleinen Plattform-Inboxen (z.B. HeyJobs: 1 Digest/Woche) trotzdem
    # trainieren koennen. Trade-off: Pattern auf weniger Samples ist
    # statistisch schwaecher; mind. min_hit_rate-Schwelle bleibt der
    # Quality-Gate.
    if len(mails) < 2:
        raise ValueError(
            f"Zu wenig Mails ({len(mails)}) fuer Training "
            f"(mind. 2 noetig: 1 Train + 1 Test)."
        )

    train_size_effective = min(train_size, max(1, len(mails) - 1))
    train_size_reduced = train_size_effective < train_size

    train = mails[:train_size_effective]
    test = mails[train_size_effective:]

    if progress_cb:
        progress_cb(30, 'ai-training pattern')

    try:
        pattern = pl.ai_learn_pattern(
            user, train_samples=train, platform=platform,
            provider_override='ollama',
            model_override='qwen3-coder:latest',
        )
    except RuntimeError as exc:
        raise RuntimeError(f"AI-Train fehlgeschlagen: {exc}") from exc

    if progress_cb:
        progress_cb(60, 'compiling pattern')

    try:
        # Plattform-URL-Pattern (hardcoded) als Constraint einflechten —
        # verhindert dass AI-gelernte url_labels Marketing-Links matchen.
        from services.job_sources.email_jobs import get_profile
        profile = get_profile(platform)
        url_pattern_str = profile.url_pattern.pattern
        compiled = pl.compile_pattern(pattern, url_pattern_str=url_pattern_str)
    except (ValueError, _re.error) as exc:
        raise RuntimeError(f"Pattern-Compile fehlgeschlagen: {exc}") from exc

    if progress_cb:
        progress_cb(85, 'validating pattern')

    hit_rate, diagnostics = pl.validate_pattern(
        compiled, test, url_check_re=profile.url_pattern,
    )
    if hit_rate < min_hit_rate:
        raise RuntimeError(
            f"Hit-Rate unter Schwelle - Pattern nicht aktiviert. "
            f"hit_rate={hit_rate:.2f} < min_hit_rate={min_hit_rate:.2f}"
        )

    # Persist: alte Patterns deaktivieren + neue als active speichern.
    LearnedEmailPattern.query.filter_by(
        platform=platform, is_active=True  # noqa: E712
    ).update({"is_active": False})
    new_row = LearnedEmailPattern(
        platform=platform,
        pattern_json=_json.dumps(pattern),
        sample_count=len(test),
        hit_rate=hit_rate,
        trained_at=datetime.utcnow(),
        trained_by_user_id=user.id,
        is_active=True,
    )
    db.session.add(new_row)
    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "ok": True,
        "hit_rate": hit_rate,
        "sample_count": len(test),
        "pattern": pattern,
        "example_matches": [d for d in diagnostics if d["matched"]][:3],
        "train_size_used": train_size_effective,
        "train_size_reduced": train_size_reduced,
        "mails_total": len(mails),
    }
