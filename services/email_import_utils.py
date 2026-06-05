# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Shared email-import utilities extracted from api/jobs_user.py.

Erlaubt Import aus services/tasks/handlers/ ohne zirkuläre Imports.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import requests

from database import db
from models import JobSource, RawJob, JobMatch, Application


_INDEED_AUTO_DISABLE_THRESHOLD = 5

_APPS_SCRIPT_URL_RE = re.compile(
    r'^https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/[a-z]+(?:\?[^\s]*)?$'
)

_APPS_SCRIPT_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_APPS_SCRIPT_CACHE_TTL = 3600.0


def fetch_apps_script_emails(url: str, user_id: str | None = None,
                              use_cache: bool = True) -> tuple[list[dict], bool]:
    """Server-side GET eines Apps-Script-Web-Endpoints (umgeht Browser-CORS).

    Returns: (emails_list, cache_hit)
    """
    if not _APPS_SCRIPT_URL_RE.match(url or ''):
        raise ValueError(
            "Apps-Script-URL muss auf https://script.google.com/macros/s/.../exec passen"
        )

    cache_key = (user_id or '', url)
    now = time.time()

    if use_cache:
        entry = _APPS_SCRIPT_CACHE.get(cache_key)
        if entry and (now - entry[0]) < _APPS_SCRIPT_CACHE_TTL:
            return entry[1], True

    try:
        r = requests.get(url, timeout=60, allow_redirects=True)
    except requests.RequestException as exc:
        raise RuntimeError(f"Apps-Script nicht erreichbar: {exc}") from exc

    if r.status_code != 200:
        raise RuntimeError(f"Apps-Script HTTP {r.status_code}")

    ctype = (r.headers.get('Content-Type') or '').lower()
    text = r.text
    if 'json' not in ctype and not text.lstrip().startswith('{'):
        snippet = text[:120].replace('\n', ' ')
        raise RuntimeError(
            f"Apps-Script gibt HTML statt JSON zurück — Deploy-Access falsch? "
            f"(Beginn: {snippet!r})"
        )

    try:
        data = r.json()
    except ValueError as exc:
        raise RuntimeError(f"Apps-Script JSON-Parse-Fehler: {exc}") from exc

    if data.get('status') and data['status'] != 'ok':
        raise RuntimeError(f"Apps-Script-Error: {data.get('error') or data['status']}")

    emails = data.get('emails') if isinstance(data.get('emails'), list) else []
    _APPS_SCRIPT_CACHE[cache_key] = (now, emails)
    return emails, False


# Trailing legal-form / corporate-suffix tokens, normalisiert beim Vergleichen
# entfernt. Nur am ENDE matchen (anchored $), damit "International Business
# Machines" o.Ä. nicht am Anfang verstümmelt werden. Liste bewusst konservativ:
# deutsche Rechtsformen + die häufigsten internationalen Pendants.
_COMPANY_SUFFIX_RE = re.compile(
    r'(?:\s*[,&\-]?\s*)(?:'
    r'gmbh\s*&?\s*co\.?\s*kg|'
    r'gmbh\s*&?\s*co\.?\s*ohg|'
    r'gmbh|ag|kg|mbh|ohg|se|gbr|ggmbh|kgaa|ug|'
    r'e\.?\s*v\.?|e\.?\s*g\.?|'
    r'ltd\.?|llc|inc\.?|corp\.?|plc|'
    r'group|holding|international'
    r')\.?\s*$',
    re.IGNORECASE,
)


def normalize_company(name: str | None) -> str:
    """Lowercase + trailing legal-suffix-Strip für Company-Match.

    Beispiele:
      "Signal Iduna Group AG" → "signal iduna"
      "Acme GmbH & Co. KG"    → "acme"
      "BWI GmbH"              → "bwi"
      "Hire Feed"             → "hire feed"
      "Continental (Germany)" → "continental"

    Idempotent: f(f(x)) == f(x).
    """
    if not name:
        return ''
    s = re.sub(r'\s+', ' ', name).strip()
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s)
    prev = None
    while s != prev:
        prev = s
        s = _COMPANY_SUFFIX_RE.sub('', s).rstrip(' ,.&-')
    return s.lower()


def get_rejected_companies_lower(user_id: str, window_days: int) -> set[str]:
    """Liefert normalisierte company-Namen mit Status 'absage' im Reject-Fenster.

    Normalisierung via `normalize_company()` (Rechtsformen-Strip + lowercase).
    Callers MÜSSEN ihren Vergleichswert mit derselben Funktion normalisieren.
    """
    cutoff_dt = datetime.utcnow() - timedelta(days=window_days)
    cutoff_date = cutoff_dt.date()
    q = (
        db.session.query(Application.company)
        .filter(
            Application.user_id == user_id,
            Application.deleted == False,  # noqa: E712
            Application.status.in_(['absage', 'rejected']),
            Application.company.isnot(None),
            db.or_(
                Application.applied_date >= cutoff_date,
                db.and_(Application.applied_date.is_(None),
                        Application.created_at >= cutoff_dt),
            ),
        )
        .distinct()
    )
    out: set[str] = set()
    for (raw_name,) in q.all():
        norm = normalize_company(raw_name)
        if norm:
            out.add(norm)
    return out


def create_raw_job_and_match(
    src: JobSource,
    user_id: str,
    job_data: dict,
    match_status: str,
    feedback_text: str | None = None,
) -> tuple[RawJob | None, JobMatch | None]:
    """Erstellt RawJob + JobMatch in einer Transaktion. Caller commit()et.

    Idempotent: existiert bereits ein RawJob mit gleichem (source_id, external_id)
    UND ein JobMatch fuer denselben User, gibt die Funktion (None, None) zurueck.
    """
    url = (job_data.get('url') or '').strip()
    external_id = (job_data.get('external_id') or url or '')[:512]

    existing_raw = RawJob.query.filter_by(
        source_id=src.id, external_id=external_id
    ).first()
    if existing_raw is not None:
        existing_match = JobMatch.query.filter_by(
            raw_job_id=existing_raw.id, user_id=user_id
        ).first()
        if existing_match is not None:
            return None, None
        match = JobMatch(
            raw_job_id=existing_raw.id,
            user_id=user_id,
            status=match_status,
            feedback_text=feedback_text,
        )
        db.session.add(match)
        return existing_raw, match

    raw = RawJob(
        source_id=src.id,
        external_id=external_id,
        title=(job_data.get('title') or '')[:512],
        company=(job_data.get('company') or '')[:255] or None,
        location=(job_data.get('location') or '')[:255] or None,
        url=url[:4096],
        description=(job_data.get('description') or '')[:2000] or None,
        crawl_status='raw',
    )
    raw.raw_payload = job_data.get('raw') or {}
    db.session.add(raw)
    db.session.flush()

    match = JobMatch(
        raw_job_id=raw.id,
        user_id=user_id,
        status=match_status,
        feedback_text=feedback_text,
    )
    db.session.add(match)
    return raw, match
