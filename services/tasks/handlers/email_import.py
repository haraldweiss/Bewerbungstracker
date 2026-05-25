# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /import-from-email. Logik aus api/jobs_user.py extrahiert."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from database import db
from models import User, JobSource
from services.job_sources import get_adapter
from services.job_sources import dedup as _dedup
from services.tasks.registry import register


@register('email_import')
def handle_email_import(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt einen Email-Import durch.

    Payload-Format:
        user_id (str): UUID des Users.
        source_id (int): JobSource.id.
        emails (list[dict], optional): Apps-Script-Mode.
        script_url (str, optional): Apps-Script-Proxy-Mode.
        force_refresh (bool, optional): default False.

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    """
    user = User.query.get(payload['user_id'])
    src = JobSource.query.get(payload['source_id'])
    if user is None:
        raise ValueError(f"user_id {payload['user_id']!r} nicht gefunden")
    if src is None or src.user_id != user.id:
        raise ValueError(f"source_id {payload['source_id']!r} nicht zugänglich")

    provided_emails = payload.get('emails')
    script_url = payload.get('script_url')
    force_refresh = bool(payload.get('force_refresh'))

    if progress_cb:
        progress_cb(5, 'fetching')

    cache_hit = False
    adapter = get_adapter(src.type, src.config, user=user)
    adapter._source_id_for_tracking = src.id
    if isinstance(provided_emails, list):
        fetched = adapter.parse_emails(provided_emails)
        fetch_mode = 'apps_script'
    elif isinstance(script_url, str) and script_url:
        from api.jobs_user import _fetch_apps_script_emails
        emails, cache_hit = _fetch_apps_script_emails(
            script_url, user_id=user.id, use_cache=not force_refresh,
        )
        fetched = adapter.parse_emails(emails)
        fetch_mode = 'apps_script_proxy'
    else:
        fetched = adapter.fetch()
        fetch_mode = 'imap'

    if progress_cb:
        progress_cb(60, f'parsed {len(fetched)} jobs')

    src.consecutive_failures = 0
    src.last_error = None

    existing_urls = _dedup.get_existing_job_urls()
    fresh = _dedup.deduplicate(fetched, existing_urls)
    duplicates_count = len(fetched) - len(fresh)

    window_days = int(user.job_reject_window_days or 180)
    reject_enabled = bool(user.job_reject_filter_enabled)
    from api.jobs_user import _get_rejected_companies_lower
    rejected_companies = (
        _get_rejected_companies_lower(user.id, window_days) if reject_enabled else set()
    )

    new_for_dialog: list[dict] = []
    blocked_for_dialog: list[dict] = []
    for fjob in fresh:
        company_lower = (fjob.company or '').strip().lower()
        is_blocked = bool(company_lower) and company_lower in rejected_companies
        job_data = {
            'title': fjob.title,
            'company': fjob.company,
            'location': fjob.location,
            'url': fjob.url,
            'external_id': fjob.external_id,
            'description': fjob.description,
            'raw': fjob.raw or {},
        }
        if is_blocked:
            blocked_for_dialog.append(job_data)
        else:
            new_for_dialog.append(job_data)

    if progress_cb:
        progress_cb(85, 'persisting')

    from api.jobs_user import _create_raw_job_and_match
    imported_count = 0
    for job_data in new_for_dialog:
        raw, match = _create_raw_job_and_match(
            src, user.id, job_data, match_status='new',
        )
        if raw is not None and match is not None:
            imported_count += 1
        else:
            duplicates_count += 1

    src.last_crawled_at = datetime.utcnow()
    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        'imported': imported_count,
        'blocked': blocked_for_dialog,
        'duplicates': duplicates_count,
        'total_emails': len(fetched),
        'rejection_window_days': window_days,
        'reject_filter_enabled': reject_enabled,
        'fetch_mode': fetch_mode,
        'cache_hit': cache_hit,
    }
