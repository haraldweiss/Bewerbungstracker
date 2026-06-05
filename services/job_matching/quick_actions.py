from __future__ import annotations

import json
from datetime import date

from database import db
from models import User, RawJob, JobMatch, Application


VALID_ACTIONS = frozenset({
    'company_rejected', 'already_applied', 'job_unavailable', 'wrong_job_type',
})
VALID_JOB_TYPES = frozenset({'werkstudent', 'freelance', 'temp_agency'})

FEEDBACK_TEXT_BY_ACTION = {
    'company_rejected': 'quick_action_company_rejected',
    'already_applied': 'quick_action_already_applied',
    'job_unavailable': 'job_no_longer_available',
    'wrong_job_type': 'wrong_job_type_blocked',
}

_PROTECTED_STATUSES = frozenset({'absage', 'rejected', 'ghosting', 'zusage', 'offer'})


class QuickActionError(ValueError):
    """Validierungsfehler — wird vom Caller als 400 abgebildet."""


def apply_quick_action(*, user: User, match: JobMatch, raw: RawJob,
                       action: str, job_type: str | None = None) -> None:
    if action not in VALID_ACTIONS:
        raise QuickActionError(f"unbekannte quick_action: {action!r}")

    if action in ('company_rejected', 'already_applied'):
        company = (raw.company or '').strip()
        title = (raw.title or '').strip()
        if not company or not title:
            raise QuickActionError(
                "Firma/Titel im RawJob fehlt — quick_action nicht moeglich"
            )
        existing = _find_application(user.id, company, title)
        if action == 'company_rejected':
            _apply_company_rejected(user, raw, match, existing)
        else:
            _apply_already_applied(user, raw, match, existing)

    elif action == 'job_unavailable':
        pass

    elif action == 'wrong_job_type':
        if not job_type or job_type not in VALID_JOB_TYPES:
            raise QuickActionError(
                f"job_type muss in {sorted(VALID_JOB_TYPES)} sein"
            )
        _apply_wrong_job_type(user, job_type)


def _find_application(user_id: str, company: str, title: str) -> Application | None:
    return (
        Application.query
        .filter(
            Application.user_id == user_id,
            Application.deleted == False,
            db.func.lower(Application.company) == company.lower(),
            db.func.lower(Application.position) == title.lower(),
        )
        .first()
    )


def _apply_company_rejected(user: User, raw: RawJob, match: JobMatch,
                            existing: Application | None) -> None:
    if existing is None:
        db.session.add(Application(
            user_id=user.id,
            company=raw.company,
            position=raw.title,
            status='absage',
            applied_date=None,
            notes=f'Quick-Action company_rejected aus JobMatch #{match.id}',
        ))
    elif existing.status not in _PROTECTED_STATUSES:
        existing.status = 'absage'


def _apply_already_applied(user: User, raw: RawJob, match: JobMatch,
                           existing: Application | None) -> None:
    if existing is not None:
        return
    db.session.add(Application(
        user_id=user.id,
        company=raw.company,
        position=raw.title,
        status='beworben',
        applied_date=date.today(),
        notes=f'Quick-Action already_applied aus JobMatch #{match.id}',
    ))


def _apply_wrong_job_type(user: User, job_type: str) -> None:
    try:
        current = set(json.loads(user.job_type_blacklist or '[]'))
    except (ValueError, TypeError):
        current = set()
    if job_type in current:
        return
    current.add(job_type)
    user.job_type_blacklist = json.dumps(sorted(current))
