# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Async-Handler für /api/jobs/cron/prefilter. Logik aus api/jobs_cron.py extrahiert."""
from __future__ import annotations

import json
import time
from difflib import SequenceMatcher
from typing import Callable, Optional

from database import db
from models import User, RawJob, JobMatch
from services.job_matching.embedder import embed_raw_job  # module-level for patchability
from services.tasks.registry import register


@register('cron_prefilter')
def handle_cron_prefilter(payload: dict, *, progress_cb: Optional[Callable] = None) -> dict:
    """Führt den Cron-prefilter-Lauf durch.

    Payload: leerer dict (cron-stages haben keine Parameter — pending matches
    werden intern aus DB ermittelt).

    Returns: gleiches dict wie der frühere synchrone Endpoint.
    Raises: bei harten Fehlern; Worker markiert task=failed.
    """
    from services.job_matching.claude_utils import (
        _ai_confirm_prefilter_dismiss, _has_user_judgment, _build_cv_summary,
        MAX_PREFILTER_PER_TICK, PREFILTER_DISMISS_THRESHOLD, HARD_TIME_LIMIT_SEC,
        AI_CONFIRM_BUDGET,
    )
    from services.job_matching.cv_tokenizer import tokenize_cv
    from services.job_matching.prefilter import score_job, PrefilterContext, detect_job_type
    from services.email_import_utils import (
        get_rejected_companies_lower, normalize_company, scan_body_reject,
    )

    started = time.time()
    pending = (JobMatch.query
               .filter(JobMatch.prefilter_score.is_(None), JobMatch.status == 'new')
               .limit(MAX_PREFILTER_PER_TICK).all())

    cv_cache: dict = {}
    cv_summary_cache: dict = {}
    user_cache: dict = {}
    ctx_cache: dict = {}
    rejected_companies_cache: dict = {}
    job_type_blacklist_cache: dict = {}
    fuzzy_dup_cache: dict = {}  # user_id -> [(normalized_title, normalized_company), ...]
    scored = 0
    dismissed = 0
    ai_confirm_used = 0
    ai_confirm_overruled = 0
    rejected_company_dismissed = 0
    wrong_job_type_dismissed = 0
    body_phrase_dismissed = 0
    keyword_dismissed = 0
    fuzzy_dup_dismissed = 0
    
    SIMILARITY_THRESHOLD = 0.85

    def _rejected_companies_for(user_id: str, window_days: int) -> set:
        if user_id not in rejected_companies_cache:
            rejected_companies_cache[user_id] = (
                get_rejected_companies_lower(user_id, window_days)
            )
        return rejected_companies_cache[user_id]

    if progress_cb:
        progress_cb(5, f'scoring {len(pending)} matches')

    for match in pending:
        if time.time() - started > HARD_TIME_LIMIT_SEC:
            break

        if match.user_id not in cv_cache:
            user = User.query.get(match.user_id)
            user_cache[match.user_id] = user
            cv_data = json.loads(user.cv_data_json) if user.cv_data_json else {}
            cv_cache[match.user_id] = tokenize_cv(cv_data)
            cv_summary_cache[match.user_id] = _build_cv_summary(user.cv_data_json)
            ctx_cache[match.user_id] = PrefilterContext(
                language_filter=user.job_language_filter,
                region_filter=user.job_region_filter,
            )
            import json as _json
            try:
                job_type_blacklist_cache[match.user_id] = set(
                    _json.loads(user.job_type_blacklist or '[]')
                )
            except (ValueError, TypeError):
                job_type_blacklist_cache[match.user_id] = set()

            try:
                job_type_blacklist_cache[f'kw_{match.user_id}'] = list(
                    _json.loads(user.job_keyword_blacklist or '[]')
                )
            except (ValueError, TypeError):
                job_type_blacklist_cache[f'kw_{match.user_id}'] = []

            try:
                job_type_blacklist_cache[f'body_{match.user_id}'] = list(
                    _json.loads(user.job_body_reject_phrases or '[]')
                )
            except (ValueError, TypeError):
                job_type_blacklist_cache[f'body_{match.user_id}'] = []

            # Preload existing titles for fuzzy duplicate detection
            existing = (
                db.session.query(RawJob.title, RawJob.company, RawJob.description)
                .join(JobMatch, JobMatch.raw_job_id == RawJob.id)
                .filter(
                    JobMatch.user_id == match.user_id,
                    JobMatch.status.in_(['imported', 'dismissed']),
                )
                .distinct()
                .all()
            )
            fuzzy_dup_cache[match.user_id] = [
                ((r.title or '').strip().lower(), (r.company or '').strip().lower())
                for r in existing if r.title
            ]

        raw = RawJob.query.get(match.raw_job_id)

        is_duplicate = False
        is_fuzzy_duplicate = False
        if raw.title and raw.company:
            dup_exists = (
                JobMatch.query
                .join(RawJob, JobMatch.raw_job_id == RawJob.id)
                .filter(
                    JobMatch.user_id == match.user_id,
                    JobMatch.id != match.id,
                    JobMatch.status.in_(['imported', 'dismissed']),
                    RawJob.title == raw.title,
                    RawJob.company == raw.company,
                )
                .first()
            )
            is_duplicate = dup_exists is not None

            if not is_duplicate:
                # Cross-portal fuzzy duplicate: same title, different portals
                title_norm = (raw.title or '').strip().lower()
                company_norm = normalize_company(raw.company or '').strip().lower()
                existing_titles = fuzzy_dup_cache.get(match.user_id, [])
                for ext_title, ext_company in existing_titles:
                    if SequenceMatcher(None, title_norm, ext_title).ratio() >= SIMILARITY_THRESHOLD:
                        # Same company (normalized) or similar title across different companies
                        if ext_company and (
                            company_norm == ext_company
                            or company_norm in ext_company
                            or ext_company in company_norm
                        ):
                            is_fuzzy_duplicate = True
                            break

        score = score_job(
            cv_cache[match.user_id],
            {"title": raw.title, "description": raw.description, "location": raw.location},
            ctx_cache[match.user_id],
        )
        match.prefilter_score = score
        try:
            embed_raw_job(raw)
        except Exception:
            pass

        is_rejected_company = False
        if raw.company:
            user_obj = user_cache.get(match.user_id)
            if user_obj:
                window = user_obj.job_reject_window_days or 180
                rejected_set = _rejected_companies_for(match.user_id, window)
                if normalize_company(raw.company) in rejected_set:
                    is_rejected_company = True

        blacklist = job_type_blacklist_cache.get(match.user_id, set())
        is_blacklisted_job_type = False
        if blacklist:
            detected = detect_job_type(raw.title)
            if detected and detected in blacklist:
                is_blacklisted_job_type = True

        is_body_rejected = False
        is_keyword_rejected = False
        if not is_rejected_company and not is_blacklisted_job_type:
            body_text = f"{raw.title or ''} {raw.description or ''}"
            user_phrases = job_type_blacklist_cache.get(f'body_{match.user_id}', [])
            if scan_body_reject(body_text, user_phrases):
                is_body_rejected = True
            else:
                kw_list = job_type_blacklist_cache.get(f'kw_{match.user_id}', [])
                if kw_list:
                    body_lower = body_text.lower()
                    for kw in kw_list:
                        if kw.strip() and kw.lower() in body_lower:
                            is_keyword_rejected = True
                            break

        user_has_judgment = _has_user_judgment(match)

        if is_rejected_company:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'company_already_rejected'
            dismissed += 1
            rejected_company_dismissed += 1
        elif is_blacklisted_job_type:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'wrong_job_type_blocked'
            dismissed += 1
            wrong_job_type_dismissed += 1
        elif is_body_rejected:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'body_phrase_rejected'
            dismissed += 1
            body_phrase_dismissed += 1
        elif is_keyword_rejected:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'keyword_blacklisted'
            dismissed += 1
            keyword_dismissed += 1
        elif is_duplicate:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'duplicate_of_other'
            dismissed += 1
        elif is_fuzzy_duplicate:
            match.status = 'dismissed'
            if not user_has_judgment:
                match.feedback_text = 'fuzzy_duplicate'
            dismissed += 1
            fuzzy_dup_dismissed += 1
        elif score < PREFILTER_DISMISS_THRESHOLD:
            ai_result = None
            if ai_confirm_used < AI_CONFIRM_BUDGET:
                user_obj = user_cache.get(match.user_id)
                cv_sum = cv_summary_cache.get(match.user_id, '')
                if user_obj and cv_sum:
                    ai_result = _ai_confirm_prefilter_dismiss(user_obj, raw, cv_sum)
                    if ai_result is not None:
                        ai_confirm_used += 1

            if ai_result is None:
                match.status = 'dismissed'
                if not user_has_judgment:
                    match.feedback_text = 'prefilter_low_score'
                dismissed += 1
            elif ai_result[0]:
                ai_confirm_overruled += 1
                if ai_result[1]:
                    match.match_reasoning = f"[AI-Overrule] {ai_result[1]}"
            else:
                match.status = 'dismissed'
                if not user_has_judgment:
                    match.feedback_text = 'prefilter_low_score_ai_confirmed'
                if ai_result[1]:
                    match.match_reasoning = f"[AI-Confirm-Dismiss] {ai_result[1]}"
                dismissed += 1
        scored += 1

    db.session.commit()

    if progress_cb:
        progress_cb(100, 'done')

    return {
        "scored": scored,
        "dismissed": dismissed,
        "rejected_company_dismissed": rejected_company_dismissed,
        "wrong_job_type_dismissed": wrong_job_type_dismissed,
        "body_phrase_dismissed": body_phrase_dismissed,
        "keyword_dismissed": keyword_dismissed,
        "fuzzy_dup_dismissed": fuzzy_dup_dismissed,
        "ai_confirm_used": ai_confirm_used,
        "ai_confirm_overruled": ai_confirm_overruled,
        "duration_sec": round(time.time() - started, 2),
    }
