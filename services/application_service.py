# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Validation and identity checks for application records."""
from datetime import date, datetime

from database import db
from models import Application, ApplicationStatus

TEXT_LIMITS = {
    'company': 255, 'position': 255, 'salary': 100, 'location': 200,
    'contact_email': 255, 'source': 50, 'link': None, 'notes': None,
}


def validate_application_data(
    data: object, *, partial: bool = False,
) -> dict[str, str | date | None]:
    """Validate the complete payload before any database mutation."""
    if not isinstance(data, dict):
        raise ValueError('Application data must be a JSON object')
    result: dict[str, str | date | None] = {}
    for field, limit in TEXT_LIMITS.items():
        if field not in data:
            if not partial and field in ('company', 'position'):
                raise ValueError(f'{field} is required')
            continue
        value = data[field]
        if field in ('company', 'position'):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{field} must be a non-empty string')
            value = value.strip()
        elif value is not None and not isinstance(value, str):
            raise ValueError(f'{field} must be a string or null')
        if value is not None and limit is not None and len(value) > limit:
            raise ValueError(f'{field} must be at most {limit} characters')
        result[field] = value
    if 'status' in data:
        value = data['status']
        if not isinstance(value, str) or value not in {s.value for s in ApplicationStatus}:
            raise ValueError('Invalid application status')
        result['status'] = value
    if 'applied_date' in data:
        value = data['applied_date']
        if value is None or value == '':
            result['applied_date'] = None
        else:
            if not isinstance(value, str):
                raise ValueError('applied_date must be an ISO date string or null')
            try:
                result['applied_date'] = datetime.fromisoformat(value).date()
            except ValueError:
                raise ValueError('Invalid applied_date; use YYYY-MM-DD') from None
    return result


def find_duplicate_application(
    user_id: str, company: str, position: str, *, exclude_id: str | None = None,
) -> Application | None:
    """Match active records, including legacy surrounding whitespace."""
    query = Application.query.filter(
        Application.user_id == user_id,
        Application.deleted.is_(False),
        db.func.lower(db.func.trim(Application.company)) == db.func.lower(company),
        db.func.lower(db.func.trim(Application.position)) == db.func.lower(position),
    )
    if exclude_id is not None:
        query = query.filter(Application.id != exclude_id)
    return query.first()
