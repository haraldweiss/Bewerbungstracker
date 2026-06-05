# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/indeed-email-import-all (per-Source).

Logik aus api/jobs_cron.py::indeed_email_import_all extrahiert: jeder Source
läuft als eigener Task mit eigenem Commit. Verhindert die 4-Minuten-
Write-Lock-Phase, die im sync-Endpoint "database is locked"-500er bei
parallelen User-Writes (Verwerfen etc.) produziert hat.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

from database import db
from models import User, JobSource
from services.tasks.registry import register


_AUTO_DISABLE_THRESHOLD = 5


@register('cron_indeed_email_import_source')
def handle_cron_indeed_email_import_source(
    payload: dict, *, progress_cb: Optional[Callable] = None,
) -> dict:
    """Importiert Emails für GENAU EINE JobSource.

    Payload: {"source_id": int}

    Returns: per-source Run-Dict (gleiches Format wie früher `runs[i]` im
    sync-Endpoint), z.B.:
      {"source_id": 7, "status": "ok", "mode": "imap",
       "total_emails": 12, "duplicates": 2, "imported": 8, "blocked_auto": 2}

    Raises NICHT bei Fetch-Errors — gibt status=error zurück damit der Task
    als 'completed' (statt 'failed') geloggt wird; consecutive_failures +
    auto_disable werden im DB-Record festgehalten.
    """
    from services.job_sources import get_adapter
    from services.job_sources import dedup as _dedup
    from services.email_import_utils import (
        get_rejected_companies_lower,
        create_raw_job_and_match,
        fetch_apps_script_emails,
        normalize_company,
    )

    src = JobSource.query.get(payload['source_id'])
    if src is None:
        return {"source_id": payload['source_id'], "status": "skipped_no_source"}
    if not src.enabled:
        return {"source_id": src.id, "status": "skipped_disabled"}

    user = User.query.get(src.user_id) if src.user_id else None
    if user is None:
        return {"source_id": src.id, "status": "skipped_no_owner"}

    settings = {}
    if user.settings_json:
        try:
            settings = json.loads(user.settings_json) or {}
        except (TypeError, ValueError):
            settings = {}
    script_url = (settings.get('indeedScriptUrl') or '').strip()
    has_imap = bool(user.imap_password_encrypted)

    if progress_cb:
        progress_cb(5, 'fetching')

    try:
        adapter = get_adapter(src.type, src.config, user=user)
        if script_url:
            emails, _cache_hit = fetch_apps_script_emails(
                script_url, user_id=user.id, use_cache=False,  # Cron: immer frisch
            )
            fetched = adapter.parse_emails(emails)
            mode = 'apps_script_proxy'
        elif has_imap:
            fetched = adapter.fetch()
            mode = 'imap'
        else:
            return {"source_id": src.id, "status": "skipped_no_credentials"}
    except Exception as e:
        src.last_error = f"{type(e).__name__}: {str(e)[:500]}"
        src.consecutive_failures = (src.consecutive_failures or 0) + 1
        if src.consecutive_failures >= _AUTO_DISABLE_THRESHOLD:
            src.enabled = False
        db.session.commit()
        return {
            "source_id": src.id,
            "status": "error",
            "error": src.last_error,
            "auto_disabled": not src.enabled,
        }

    src.consecutive_failures = 0
    src.last_error = None

    if progress_cb:
        progress_cb(60, f'parsed {len(fetched)} jobs')

    existing_urls = _dedup.get_existing_job_urls()
    fresh = _dedup.deduplicate(fetched, existing_urls)
    duplicates_count = len(fetched) - len(fresh)

    window_days = int(user.job_reject_window_days or 180)
    rejected_companies = (
        get_rejected_companies_lower(user.id, window_days)
        if user.job_reject_filter_enabled else set()
    )

    imported_count = 0
    blocked_auto_count = 0
    for fjob in fresh:
        company_norm = normalize_company(fjob.company)
        is_blocked = bool(company_norm) and company_norm in rejected_companies
        payload_job = {
            'title': fjob.title, 'company': fjob.company,
            'location': fjob.location, 'url': fjob.url,
            'external_id': fjob.external_id, 'description': fjob.description,
            'raw': fjob.raw or {},
        }
        if is_blocked:
            create_raw_job_and_match(
                src, user.id, payload_job,
                match_status='dismissed',
                feedback_text='auto_blocked_by_rejection',
            )
            blocked_auto_count += 1
        else:
            create_raw_job_and_match(src, user.id, payload_job, match_status='new')
            imported_count += 1

    src.last_crawled_at = datetime.utcnow()
    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "source_id": src.id,
        "status": "ok",
        "mode": mode,
        "total_emails": len(fetched),
        "duplicates": duplicates_count,
        "imported": imported_count,
        "blocked_auto": blocked_auto_count,
    }
