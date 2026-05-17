# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Indeed-Email-Source: liest Indeed-Job-Empfehlungen aus einem IMAP-Folder.

User-Credentials kommen aus `User.imap_*`. Der Adapter verbindet direkt
zum IMAP-Server (kein Mac-Proxy, da der Proxy nur Header liefert).

Parsing: Regex zuerst, AI-Fallback (ai-provider-service) wenn unvollständig.
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import re
import ssl
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Optional

from services.job_sources.base import JobSourceAdapter, FetchedJob

logger = logging.getLogger(__name__)


# Subject-Patterns für Indeed-Emails (DE + EN).
_SUBJECT_PATTERNS = [
    re.compile(
        r'(?:Neue Stelle|Stellenvorschlag|Job alert|New job|New jobs?)\s*:?\s*'
        r'(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)(?:\s*[-–|]\s*Indeed.*)?$',
        re.IGNORECASE,
    ),
    re.compile(
        r'^(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)(?:\s*[-–|]\s*Indeed.*)?$',
        re.IGNORECASE,
    ),
]

# Indeed-URL: jede subdomain (cts.indeed.com, match.indeed.com, de.indeed.com,
# www.indeed.com, ...) und jeder Pfad. Indeed nutzt vor allem cts.indeed.com/v3/
# als Click-Tracker mit base64-codierter Ziel-URL — wir behalten den Tracker-Link
# als external_id und folgen ihm nicht (kein Auto-Redirect).
_INDEED_URL_RE = re.compile(
    r'(https?://(?:[a-z0-9\-.]+\.)?indeed\.(?:de|com|co\.uk|fr|it|es)/[^\s\)<>"\'\\]+)',
    re.IGNORECASE,
)

# Body-Fallback-Patterns
_BODY_TITLE_RE = re.compile(
    r'(?:Stelle|Position|Job\s*Title|Jobtitel)\s*:?\s*([^\n\r]+)',
    re.IGNORECASE,
)
_BODY_COMPANY_RE = re.compile(
    r'(?:Firma|Unternehmen|Company|Arbeitgeber|Employer)\s*:?\s*([^\n\r]+)',
    re.IGNORECASE,
)
_BODY_LOCATION_RE = re.compile(
    r'(?:Ort|Standort|Location|Place|City)\s*:?\s*([^\n\r]+)',
    re.IGNORECASE,
)


class IndeedEmailAdapter(JobSourceAdapter):
    """Liest Indeed-Job-Empfehlungen aus einem IMAP-Folder des Users.

    Config:
        folder         (str)  — IMAP-Ordnername, Default 'Indeed'
        lookback_days  (int)  — Wie weit zurück fetchen, Default 30
        limit          (int)  — Max Emails pro Fetch, Default 100

    Erfordert User-Kontext (im Adapter via Constructor-kwarg) für
    IMAP-Credentials (`user.imap_host`, `user.imap_user`,
    `user.decrypted_imap_password`).
    """

    # Hard cap auf AI-Fallback-Calls pro Adapter-Lauf — verhindert dass
    # ein großes Email-Batch (z.B. 171 Mails) den gunicorn-Worker (timeout
    # 180s) durch Ollama/Claude-Latenz killt. Regex-only läuft sub-second.
    AI_FALLBACK_BUDGET = 10

    def __init__(self, config: dict, user=None):
        super().__init__(config)
        self.user = user
        self._ai_calls_used = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def parse_emails(self, emails: list[dict]) -> list[FetchedJob]:
        """Parses einen Pre-Fetched Email-Batch (z.B. von Google Apps Script).

        Erwartetes Email-Dict-Format:
            {'subject': str, 'body': str, 'from': str, 'date': str (ISO),
             'message_id': str (optional)}

        Reused dieselbe Regex+AI-Logik wie fetch() — nur der Transport
        unterscheidet sich (HTTP-Body statt IMAP-Connect).
        """
        if not isinstance(emails, list):
            raise ValueError("emails muss eine Liste sein")

        self._ai_calls_used = 0  # AI-Budget pro Lauf zurücksetzen
        jobs: list[FetchedJob] = []
        for em in emails:
            if not isinstance(em, dict):
                continue
            normalized = {
                'message_id': str(em.get('message_id') or em.get('id') or '')[:500],
                'subject': str(em.get('subject') or ''),
                'from': str(em.get('from') or ''),
                'date': str(em.get('date') or ''),
                'body': str(em.get('body') or em.get('snippet') or ''),
            }
            try:
                job = self._parse_email(normalized)
                if job:
                    jobs.append(job)
            except Exception as exc:
                logger.warning("Indeed-Email-Parse fehlgeschlagen: %s", exc)
                continue
        return jobs

    def fetch(self) -> list[FetchedJob]:
        if self.user is None:
            raise RuntimeError("IndeedEmailAdapter benötigt User-Kontext (kwarg user=...)")

        host = self.user.imap_host
        imap_user = self.user.imap_user
        password = self.user.decrypted_imap_password
        if not host or not imap_user or not password:
            raise RuntimeError(
                "User hat keine IMAP-Credentials — bitte zuerst in Settings einrichten"
            )

        folder = (self.config or {}).get('folder', 'Indeed')
        lookback_days = int((self.config or {}).get('lookback_days', 30))
        limit = int((self.config or {}).get('limit', 100))

        # IMAP-Folder-Name Whitelisting (gegen Injection).
        # Erlaubt Brackets (Gmail-Sonderfolder), blockt nur Control-Chars und
        # Quoting-Sonderzeichen die IMAP-Injection ermöglichen würden.
        if not re.match(r'^[^\x00-\x1f\x7f"\\]{1,100}$', folder):
            raise ValueError(f"Ungültiger Ordner-Name: {folder!r}")

        emails = self._fetch_emails(host, imap_user, password, folder, lookback_days, limit)

        self._ai_calls_used = 0  # AI-Budget pro Lauf zurücksetzen
        jobs: list[FetchedJob] = []
        for em in emails:
            try:
                job = self._parse_email(em)
                if job:
                    jobs.append(job)
            except Exception as exc:
                logger.warning("Indeed-Email-Parse fehlgeschlagen: %s", exc)
                continue

        return jobs

    # ── IMAP-Fetch ─────────────────────────────────────────────────────────

    def _fetch_emails(
        self,
        host: str,
        imap_user: str,
        password: str,
        folder: str,
        lookback_days: int,
        limit: int,
    ) -> list[dict]:
        conn = imaplib.IMAP4_SSL(host, 993, ssl_context=ssl.create_default_context())
        try:
            conn.login(imap_user, password)
            # readonly=True: setzt \Seen-Flag NICHT (User-Inbox bleibt unverändert).
            # Folder-Namen mit Leerzeichen oder Brackets (z.B. '[Gmail]/All Mail')
            # MÜSSEN als quoted-string übergeben werden, sonst antwortet Gmail
            # mit "EXAMINE command error: BAD Could not parse command".
            # imaplib quotet das NICHT automatisch.
            escaped = folder.replace('\\', '\\\\').replace('"', '\\"')
            typ, _ = conn.select(f'"{escaped}"', readonly=True)
            if typ != 'OK':
                raise RuntimeError(f"IMAP-Folder nicht erreichbar: {folder}")

            # IMAP-SEARCH: nur Indeed-Mails (FROM-Filter) im Lookback-Window.
            # Gmail's standard IMAP-FROM-Search ist eingeschränkt (nur Subset
            # des Index) — daher zuerst X-GM-RAW versuchen (Gmail-eigener
            # search-syntax, identisch zu GmailApp.search). Fallback auf
            # Standard-IMAP wenn Server X-GM-RAW nicht unterstützt
            # (z.B. IONOS/Outlook).
            since_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime('%d-%b-%Y')
            try:
                gm_query = f'"from:indeed newer_than:{lookback_days}d"'
                typ, msgnums = conn.search(None, 'X-GM-RAW', gm_query)
            except imaplib.IMAP4.error:
                typ, msgnums = conn.search(None, f'(SINCE {since_date} FROM "indeed")')
            if typ != 'OK':
                return []

            ids = msgnums[0].split() if msgnums and msgnums[0] else []
            # Neueste zuerst, gecapped auf limit.
            ids = ids[-limit:][::-1]

            out: list[dict] = []
            for msg_id in ids:
                typ, data = conn.fetch(msg_id, '(BODY.PEEK[])')
                if typ != 'OK' or not data or not data[0]:
                    continue
                raw_bytes = data[0][1]
                msg = email.message_from_bytes(raw_bytes)
                out.append({
                    'message_id': msg.get('Message-ID', '') or '',
                    'subject': _decode_mime(msg.get('Subject', '')),
                    'from': _decode_mime(msg.get('From', '')),
                    'date': msg.get('Date', ''),
                    'body': _extract_body(msg),
                })
            return out
        finally:
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn.logout()
            except Exception:
                pass

    # ── Parsing ────────────────────────────────────────────────────────────

    def _parse_email(self, em: dict) -> Optional[FetchedJob]:
        """Regex-Parse zuerst, AI-Fallback falls Pflichtfelder fehlen."""
        subject = em.get('subject', '') or ''
        body = em.get('body', '') or ''

        title, company = _parse_subject(subject)
        location = None
        url = None

        # URL aus Body (oder Subject, falls vorhanden)
        url_match = _INDEED_URL_RE.search(body) or _INDEED_URL_RE.search(subject)
        if url_match:
            url = url_match.group(1)

        # Body-Fallback für Title/Company
        if not title:
            m = _BODY_TITLE_RE.search(body)
            if m:
                title = m.group(1).strip()
        if not company:
            m = _BODY_COMPANY_RE.search(body)
            if m:
                company = m.group(1).strip()

        # Location
        m = _BODY_LOCATION_RE.search(body)
        if m:
            location = m.group(1).strip()

        # AI-Fallback nur wenn:
        #   1. Pflichtfelder fehlen UND
        #   2. Mail sieht wie Job-Mail aus (URL bereits da ODER Indeed-Marker
        #      im Subject/From) — sonst sind das random Newsletter und ein
        #      AI-Call wäre Verschwendung UND
        #   3. AI-Budget für diesen Lauf noch nicht ausgeschöpft (siehe
        #      AI_FALLBACK_BUDGET).
        # Kombi sorgt dafür dass 171 Random-Inbox-Mails nicht den Worker
        # killen (gunicorn timeout 180s).
        if (not title or not company or not url) and self.user is not None:
            from_field = (em.get('from') or '').lower()
            looks_like_indeed = (
                url is not None
                or 'indeed.' in from_field
                or 'indeed' in subject.lower()
            )
            if looks_like_indeed and self._ai_calls_used < self.AI_FALLBACK_BUDGET:
                self._ai_calls_used += 1
                ai_data = _ai_extract(self.user, subject, body)
                if ai_data:
                    title = title or ai_data.get('title')
                    company = company or ai_data.get('company')
                    location = location or ai_data.get('location')
                    url = url or ai_data.get('url')

        # Minimum: title + url
        if not title or not url:
            return None

        return FetchedJob(
            external_id=url[:512],
            title=title[:512],
            url=url[:1024],
            company=company[:255] if company else None,
            location=location[:255] if location else None,
            description=body[:2000] if body else None,
            posted_at=_parse_date(em.get('date')),
            raw={
                'message_id': em.get('message_id', ''),
                'subject': subject,
                'from': em.get('from', ''),
            },
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _decode_mime(s: str) -> str:
    if not s:
        return ''
    parts = decode_header(s)
    out = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            try:
                out.append(chunk.decode(charset or 'utf-8', errors='ignore'))
            except (LookupError, UnicodeDecodeError):
                out.append(chunk.decode('utf-8', errors='ignore'))
        else:
            out.append(chunk)
    return ''.join(out)


def _extract_body(msg) -> str:
    """Extract text body (prefer text/plain, fallback to stripped text/html)."""
    plain_text = ''
    html_text = ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get('Content-Disposition') or '')
            if 'attachment' in disp.lower():
                continue
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='ignore')
            except (LookupError, UnicodeDecodeError):
                continue
            if ctype == 'text/plain' and not plain_text:
                plain_text = decoded
            elif ctype == 'text/html' and not html_text:
                html_text = decoded
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                content = payload.decode(charset, errors='ignore')
                if msg.get_content_type() == 'text/html':
                    html_text = content
                else:
                    plain_text = content
        except (LookupError, UnicodeDecodeError, AttributeError):
            pass

    if plain_text:
        return plain_text
    if html_text:
        return _strip_html(html_text)
    return ''


def _strip_html(html: str) -> str:
    """Sehr einfache HTML-Strip — ersetzt Tags durch Leerzeichen."""
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = (text
            .replace('&nbsp;', ' ')
            .replace('&amp;', '&')
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&quot;', '"')
            .replace('&#39;', "'"))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _parse_subject(subject: str) -> tuple[Optional[str], Optional[str]]:
    """Versucht (title, company) aus dem Email-Subject zu extrahieren."""
    if not subject:
        return None, None
    for pat in _SUBJECT_PATTERNS:
        m = pat.search(subject.strip())
        if m:
            return m.group('title').strip(), m.group('company').strip()
    return None, None


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (TypeError, ValueError):
        return None


def _ai_extract(user, subject: str, body: str) -> Optional[dict]:
    """AI-Fallback: nutzt ai-provider-service via user.get_model_for('email_parse').

    Returns dict mit Keys title/company/location/url (any may be None),
    oder None bei Fehler.
    """
    try:
        from services import ai_provider_client
    except ImportError:
        return None

    if not ai_provider_client.is_enabled():
        return None
    client = ai_provider_client.get_client()
    if not client:
        return None

    provider, model = user.get_model_for('email_parse')
    if not provider:
        return None

    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user)

    prompt = (
        "Extract structured job data from this Indeed email. "
        "Return ONLY a single valid JSON object with these keys: "
        '"title", "company", "location", "url". '
        "If a field is unknown, use null. No prose, no markdown, only JSON.\n\n"
        f"Subject: {subject[:200]}\n\n"
        f"Body:\n{body[:2000]}"
    )

    try:
        response = client.chat(
            user_id=user.id,
            provider=provider,
            model=model or '',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            **fallback_kwargs,
        )
        text = response.content[0].text if response.content else ''
    except Exception as exc:
        logger.warning("AI-Extract fehlgeschlagen: %s", exc)
        return None

    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    return {
        'title': (data.get('title') or None),
        'company': (data.get('company') or None),
        'location': (data.get('location') or None),
        'url': (data.get('url') or None),
    }
