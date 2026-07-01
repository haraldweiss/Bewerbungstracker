# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""GET /api/applications/<id>/calendar-event.ics

Liefert eine .ics-Datei mit dem Interview-Termin der Bewerbung.
Quelle: neueste verknüpfte Email mit Interview-Keyword, sonst Application.notes.
"""

import re
from datetime import datetime, time
from flask import Blueprint, jsonify, Response
from api.auth import token_required
from database import db
from models import Application
from services.calendar_parser import parse_interview_event
from services.calendar_ics import build_ics

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/applications")

_KEYWORDS = re.compile(r"(interview|vorstellung|gespr[äa]ch|kennenlernen|einladung)", re.IGNORECASE)


@calendar_bp.route("/<app_id>/calendar-event.ics", methods=["GET"])
@token_required
def export_calendar(user, app_id: str):
    app_obj = Application.query.filter_by(id=app_id, user_id=user.id, deleted=False).first()
    if not app_obj:
        return jsonify({"error": "Bewerbung nicht gefunden"}), 404

    selected = _select_text(app_obj)
    parsed = parse_interview_event(selected.text, now=selected.reference_time)
    if parsed.start is None:
        return jsonify({"error": "Kein Termin im Notes/Email-Text gefunden"}), 400

    ics_bytes = build_ics(
        application_id=app_obj.id,
        company=app_obj.company,
        position=app_obj.position,
        parsed=parsed,
    )
    safe_company = re.sub(r"[^A-Za-z0-9_-]+", "-", app_obj.company)[:50] or "Bewerbung"
    filename = f"Interview-{safe_company}.ics"
    return Response(
        ics_bytes,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )

@calendar_bp.route("/upcoming", methods=["GET"])
@token_required
def upcoming_events(user):
    """Scant alle Bewerbungen nach Interview-Terminen und liefert
    eine nach Datum sortierte Liste.

    Durchsucht:
    - Bewerbungen mit status='interview' (notes + ggf. Emails)
    - Bewerbungen deren Emails Interview-Keywords enthalten

    Returns:
      200 + [{
        "application_id", "company", "position", "status",
        "start", "end", "meeting_url", "has_ics": bool,
      }, ...]
    """
    from models import Email

    results = []

    # Kandidaten: applications mit interview-status ODER emails mit keywords
    app_ids_with_keyword = set()
    emails = Email.query.filter(
        Email.user_id == user.id,
        Email.body.isnot(None),
    ).all()
    for e in emails:
        text = (e.subject or '') + ' ' + (e.body or '')
        if _KEYWORDS.search(text) and e.matched_application_id:
            app_ids_with_keyword.add(e.matched_application_id)

    apps = Application.query.filter(
        Application.user_id == user.id,
        Application.deleted == False,  # noqa: E712
        db.or_(
            Application.status.in_(['interview', 'offen', 'in_bearbeitung']),
            Application.id.in_(list(app_ids_with_keyword) or ['']),
        ),
    ).order_by(Application.created_at.desc()).limit(100).all()

    for app_obj in apps:
        selected = _select_text(app_obj)
        if not selected.text:
            continue
        parsed = parse_interview_event(selected.text, now=selected.reference_time)
        if parsed and parsed.start:
            results.append({
                'application_id': app_obj.id,
                'company': app_obj.company,
                'position': app_obj.position,
                'status': app_obj.status.value if hasattr(app_obj.status, 'value') else app_obj.status,
                'start': parsed.start.isoformat() if parsed.start else None,
                'end': parsed.end.isoformat() if parsed.end else None,
                'meeting_url': parsed.meeting_url or None,
                'meeting_passcode': parsed.passcode or None,
                'has_ics': True,
            })

    results.sort(key=lambda r: r['start'] or '')
    return jsonify(results), 200


class _SelectedCalendarText:
    def __init__(self, text: str, reference_time):
        self.text = text
        self.reference_time = reference_time


def _select_text(app_obj: Application) -> _SelectedCalendarText:
    """Bevorzugt Body der neuesten Email mit Interview-Keyword, sonst notes."""
    candidates = sorted(
        (e for e in (app_obj.emails or []) if (e.body or e.subject) and _KEYWORDS.search((e.subject or "") + " " + (e.body or ""))),
        key=lambda e: e.timestamp or e.created_at,
        reverse=True,
    )
    if candidates and candidates[0].body:
        return _SelectedCalendarText(candidates[0].body, candidates[0].timestamp or candidates[0].created_at)
    reference_time = _application_reference_time(app_obj)
    return _SelectedCalendarText(app_obj.notes or "", reference_time)


def _application_reference_time(app_obj: Application):
    if app_obj.applied_date:
        if isinstance(app_obj.applied_date, datetime):
            return app_obj.applied_date
        return datetime.combine(app_obj.applied_date, time.min)
    return app_obj.created_at
