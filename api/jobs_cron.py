# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cron-Endpoints für Job-Discovery Pipeline (Token-geschützt)."""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from flask import Blueprint, jsonify

from database import db
from models import User, JobSource, RawJob, JobMatch, ApiCall, Application
from services import cost_tracker
from services.cron_auth import require_cron_token
from services.job_sources import get_adapter
from services.job_matching.cv_tokenizer import tokenize_cv
from services.job_matching.prefilter import score_job, PrefilterContext
from services.job_matching.claude_matcher import (
    match_job_with_claude, _build_prompt,
)
from services.job_matching.embedder import embed_raw_job
from services.provider_service import ProviderConfig
from services.job_matching.notifier import send_match_notification
from services.job_matching.claude_utils import (
    _get_anthropic_client, _build_cv_summary, _has_user_judgment,
    _ai_confirm_prefilter_dismiss, _run_claude_match_for, _is_failed_evaluation,
    _validate_match_schema, _parse_match_response, _extract_first_json_object,
    _summarize_description, _max_tokens_for, _is_reasoning_model,
    _strip_thinking_block,
    MAX_PREFILTER_PER_TICK, PREFILTER_DISMISS_THRESHOLD,
    AUTO_CLAUDE_THRESHOLD, HARD_TIME_LIMIT_SEC, AI_CONFIRM_BUDGET,
    DEFAULT_MODEL, COST_USD_PER_1M_TOKENS_IN, COST_USD_PER_1M_TOKENS_OUT,
    _SUMMARIZE_PROMPT, _REASONING_MODEL_PATTERNS,
)

logger = logging.getLogger(__name__)


jobs_cron_bp = Blueprint('jobs_cron', __name__, url_prefix='/api/jobs')

# Email-basierte Source-Typen werden NICHT vom generischen /crawl-source
# Round-Robin verarbeitet, sondern ausschließlich vom dedizierten
# /indeed-email-import-all (Cron) bzw. User-triggered /import-from-email.
# Grund: sie brauchen User-IMAP-Credentials und sind manuell/per-User.
EMAIL_SOURCE_TYPES = ("indeed_email", "linkedin_email", "xing_email")


def _email_source_types() -> tuple[str, ...]:
    """Dynamische Liste aller Email-Plattform-Types (hardcoded + DB).

    Wird in `_select_due_source` genutzt um Email-Sources vom auto-crawl
    auszuschließen (sie laufen nur per manuellem Import-Button).
    """
    from services.job_sources.email_jobs import PROFILES
    from models import PlatformProfileRow
    hardcoded = tuple(f"{slug}_email" for slug in PROFILES.keys())
    try:
        db_slugs = tuple(
            f"{r.slug}_email"
            for r in PlatformProfileRow.query.with_entities(
                PlatformProfileRow.slug
            ).all()
        )
    except Exception:
        # Tabelle existiert noch nicht (z.B. erste Migration)
        db_slugs = ()
    return hardcoded + db_slugs

# Tick-Limits
MAX_NEW_JOBS_PER_TICK = 50
MAX_NOTIFICATIONS_PER_TICK = 20
AUTO_DISABLE_FAILURE_COUNT = 5
ARCHIVE_AFTER_DAYS = 60


def _system_user_id() -> str:
    """Returns the admin user's id as the owner of cron-triggered system tasks.

    Cron-stages have no specific user (they run for all eligible users in one
    sweep), but task_queue.user_id is NOT NULL with a FK. Using the admin
    keeps tasks visible in the admin's Background-Jobs view.

    Raises if no admin exists — that would be a bootstrap-broken state.
    """
    admin = User.query.filter_by(is_admin=True).first()
    if admin is None:
        raise RuntimeError("No admin user — cannot enqueue cron-system task")
    return admin.id


def _select_due_source() -> JobSource | None:
    # Email-basierte Sources (indeed_email, linkedin_email, xing_email)
    # werden NUR vom dedizierten /indeed-email-import-all-Cron verarbeitet,
    # nicht vom generischen Round-Robin: sie brauchen User-IMAP-Credentials
    # und sind pro-User konfiguriert.
    candidates = JobSource.query.filter(
        JobSource.enabled == True,
        JobSource.type.notin_(_email_source_types()),
    ).all()
    now = datetime.utcnow()
    due = [
        s for s in candidates
        if s.last_crawled_at is None
        or (s.last_crawled_at + timedelta(minutes=s.crawl_interval_min)) <= now
    ]
    if not due:
        return None
    due.sort(key=lambda s: s.last_crawled_at or datetime.min)
    return due[0]


def _eligible_users_for_source(source: JobSource) -> list[User]:
    """Match-fähige User: aktiv + Job-Discovery ON + CV vorhanden.

    Bei user-eigener Quelle: nur der Owner.
    Bei globaler Quelle: alle eligible User.
    """
    q = User.query.filter(
        User.is_active == True,
        User.job_discovery_enabled == True,
        User.cv_data_json.isnot(None),
    )
    if source.user_id is not None:
        q = q.filter(User.id == source.user_id)
    return q.all()


@jobs_cron_bp.post('/crawl-source')
@require_cron_token
def crawl_source():
    """Enqueued einen cron_crawl_source-Task. Returns 202 + task_id.

    Cron-Script erfährt nur dass der Job angenommen wurde; das eigentliche
    Resultat steht später unter GET /api/tasks/<id>.
    """
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_crawl_source', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


@jobs_cron_bp.post('/prefilter')
@require_cron_token
def prefilter():
    """Enqueued einen cron_prefilter-Task. Returns 202 + task_id.

    Cron-Script erfährt nur dass der Job angenommen wurde; das eigentliche
    Resultat steht später unter GET /api/tasks/<id>.
    """
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_prefilter', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


@jobs_cron_bp.post('/claude-match')
@require_cron_token
def claude_match():
    """Enqueued einen cron_claude_match-Task. Returns 202 + task_id.

    Cron-Script erfährt nur dass der Job angenommen wurde; das eigentliche
    Resultat steht später unter GET /api/tasks/<id>.
    """
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_claude_match', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


@jobs_cron_bp.post('/notify')
@require_cron_token
def notify():
    """Enqueued einen cron_notify-Task. Returns 202 + task_id."""
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_notify', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


@jobs_cron_bp.post('/cleanup')
@require_cron_token
def cleanup():
    """Enqueued einen cron_cleanup-Task. Returns 202 + task_id."""
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_cleanup', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


# ---------------------------------------------------------------------------
# URL-Health-Check (Cron)
# ---------------------------------------------------------------------------

URL_HEALTH_BATCH_SIZE = 100
URL_HEALTH_RECHECK_INTERVAL_HOURS = 24
# Nur Jobs juenger als X Tage pruefen — alte werden bereits durch
# cleanup() archiviert.
URL_HEALTH_MAX_AGE_DAYS = 30
# Per-Domain-Throttle: nach jedem HEAD-Request 2s warten BEVOR der
# naechste fuer dieselbe Domain rausgeht. Vermeidet IP-Block durch
# indeed/linkedin bei vielen Checks hintereinander.
URL_HEALTH_PER_DOMAIN_DELAY_S = 2.0


@jobs_cron_bp.post('/url-health-check')
@require_cron_token
def url_health_check():
    """Enqueued einen cron_url_health_check-Task. Returns 202 + task_id."""
    from services.tasks.queue import enqueue_task
    task_id = enqueue_task('cron_url_health_check', _system_user_id(), {})
    return jsonify({'task_id': task_id, 'status': 'queued'}), 202


# ---------------------------------------------------------------------------
# Indeed-Email Auto-Import (Cron)
# ---------------------------------------------------------------------------

@jobs_cron_bp.post('/indeed-email-import-all')
@require_cron_token
def indeed_email_import_all():
    """Enqueued pro eligible Email-Source einen cron_indeed_email_import_source-Task.

    Hintergrund: bis 2026-05-29 war dieser Endpoint synchron und iterierte
    über ALLE Email-Sources in einer einzigen Write-Transaktion. Bei mehreren
    Usern dauerte das >180s → gunicorn WORKER TIMEOUT/SIGKILL und 4 Minuten
    "database is locked" für andere Writer (z.B. User-"Verwerfen").

    Jetzt: kurzer Read (Eligibility), ein Task pro Source, jeder Task
    committet eigenständig. Lock-Fenster pro Task ist sub-Sekunden.

    Returns: 202 + {"enqueued": N, "task_ids": [...]}.
    Die per-Source-Resultate stehen unter GET /api/tasks/<id> bereit.
    """
    from services.tasks.queue import enqueue_task

    now = datetime.utcnow()
    eligible = JobSource.query.filter(
        JobSource.type.in_(_email_source_types()),
        JobSource.enabled == True,  # noqa: E712
    ).all()

    task_ids: list[str] = []
    skipped_not_due = 0
    for src in eligible:
        if src.last_crawled_at is not None:
            next_due = src.last_crawled_at + timedelta(
                minutes=src.crawl_interval_min or 60,
            )
            if next_due > now:
                skipped_not_due += 1
                continue
        tid = enqueue_task(
            'cron_indeed_email_import_source',
            _system_user_id(),
            {'source_id': src.id},
        )
        task_ids.append(tid)

    return jsonify({
        'enqueued': len(task_ids),
        'task_ids': task_ids,
        'skipped_not_due': skipped_not_due,
        'total_eligible': len(eligible),
    }), 202
