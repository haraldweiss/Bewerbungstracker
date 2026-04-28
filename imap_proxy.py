#!/usr/bin/env python3
"""
Bewerbungs-Tracker – IMAP/POP3 Proxy
======================================
Sicherheit:
  - Bindet NUR an 127.0.0.1 (kein Netzwerkzugriff von außen)
  - Zusätzliche IP-Prüfung bei jedem Request
  - Credentials werden NICHT geloggt, gespeichert oder gecacht
  - SSL/TLS standardmäßig mit Zertifikats-Validierung (system CAs)
  - Nur lesender Zugriff: IMAP readonly=True, POP3 ohne DELE
  - Nur POST-Methode akzeptiert

Start:  python3 imap_proxy.py
Port:   8765 (nur localhost)
Stop:   Strg+C
"""

import json
import logging
import re
import socket
import ssl
import threading
import imaplib
import poplib
import email
import time
import hashlib
from datetime import datetime, timedelta
from email.header import decode_header as mime_decode
from typing import Optional
from email.utils import parsedate_to_datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# ── Configuration Loading ──────────────────────────────────────────────────────────

def load_config():
    """Load config from config.json, fallback to defaults if not found or invalid."""
    defaults = {
        'server': {'host': '127.0.0.1', 'port': 8765},
        'connection': {'timeout_seconds': 20, 'fallback_days': 90},
        'cache': {'ttl_seconds': 300},
        'search': {
            'keywords': [
                'Bewerbung', 'Application', 'Stelle', 'Interview',
                'Absage', 'Zusage', 'Job', 'Recruiting', 'Kandidat',
            ]
        }
    }

    config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    if not os.path.exists(config_path):
        print('[Config] config.json nicht gefunden – verwende Defaults')
        return defaults

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)

        # Deep merge: user config overrides defaults
        config = {
            'server': {**defaults['server'], **user_config.get('server', {})},
            'connection': {**defaults['connection'], **user_config.get('connection', {})},
            'cache': {**defaults['cache'], **user_config.get('cache', {})},
            'search': {**defaults['search'], **user_config.get('search', {})},
        }
        print(f'[Config] config.json geladen: Port {config["server"]["port"]}, Timeout {config["connection"]["timeout_seconds"]}s')
        return config
    except (json.JSONDecodeError, IOError) as e:
        print(f'[Config] Fehler beim Lesen von config.json: {e} – verwende Defaults')
        return defaults

CONFIG = load_config()
HOST = CONFIG['server']['host']
PORT = CONFIG['server']['port']
SEARCH_KEYWORDS = CONFIG['search']['keywords']
TIMEOUT_SECONDS = CONFIG['connection']['timeout_seconds']
FALLBACK_DAYS = CONFIG['connection']['fallback_days']
CACHE_TTL_SECONDS = CONFIG['cache']['ttl_seconds']

socket.setdefaulttimeout(TIMEOUT_SECONDS)

# Logger for non-user-facing debug messages (e.g. silent close failures)
logger = logging.getLogger('imap_proxy')


# ── Response Caching ───────────────────────────────────────────────────────────

class ResponseCache:
    """In-memory cache with TTL (time-to-live) for email responses."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()

    def _make_key(self, host: str, user: str, folder: str, limit: int, offset: int) -> str:
        """Generate cache key from request params (NO passwords)."""
        key_str = f"{host}:{user}:{folder}:{limit}:{offset}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, host: str, user: str, folder: str, limit: int, offset: int) -> Optional[dict]:
        """Return cached response if exists and not expired."""
        key = self._make_key(host, user, folder, limit, offset)
        with self._lock:
            if key not in self.cache:
                return None

            data, timestamp = self.cache[key]
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]  # Expired
                return None

            return data

    def set(self, host: str, user: str, folder: str, limit: int, offset: int, data: dict):
        """Store response in cache with current timestamp."""
        key = self._make_key(host, user, folder, limit, offset)
        with self._lock:
            self.cache[key] = (data, time.time())

    def clear(self):
        """Clear all cache."""
        with self._lock:
            self.cache.clear()

RESPONSE_CACHE = ResponseCache(ttl_seconds=CACHE_TTL_SECONDS)


# ── Header decode ─────────────────────────────────────────────────────────────

def decode_mime_str(value: str) -> str:
    """Decode RFC 2047 MIME-encoded header value to UTF-8 string."""
    if not value:
        return ''
    parts = mime_decode(value)
    result = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            try:
                result.append(raw.decode(charset or 'utf-8', errors='replace'))
            except (LookupError, TypeError):
                result.append(raw.decode('utf-8', errors='replace'))
        else:
            result.append(raw)
    return ''.join(result).strip()


def parse_date_str(date_str: str) -> str:
    """Convert email Date header to ISO-8601."""
    if not date_str:
        return ''
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return date_str


def headers_to_email_obj(raw: bytes, uid_ref: str) -> dict:
    """Parse raw header bytes into the email dict format the JS expects."""
    msg = email.message_from_bytes(raw)
    return {
        'id':      f'imap_{uid_ref}',
        'subject': decode_mime_str(msg.get('Subject', '')),
        'from':    decode_mime_str(msg.get('From',    '')),
        'date':    parse_date_str(msg.get('Date',     '')),
        'snippet': '',   # headers-only fetch – no body bytes transferred
    }


# ── IMAP fetch ────────────────────────────────────────────────────────────────

def _collect_uids(data: list) -> set[bytes]:
    """Extract UID bytes from an imaplib SEARCH response list."""
    uids: set[bytes] = set()
    for chunk in data:
        if isinstance(chunk, bytes) and chunk.strip():
            uids.update(chunk.split())
    return uids


def _extract_raw_headers(data: list) -> Optional[bytes]:
    """Extract raw header bytes from an imaplib FETCH response list."""
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _extract_all_headers_batch(data: list) -> dict[bytes, bytes]:
    """Extract all headers from a batch FETCH response. Returns {uid: raw_headers}."""
    headers_dict = {}
    i = 0
    while i < len(data):
        item = data[i]
        # IMAP batch response format: (b'1 (RFC822.HEADER {size}', raw_bytes), (b'2 (RFC822.HEADER {size}', raw_bytes), ...
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            # Extract UID from the response tuple
            if isinstance(item[0], bytes):
                try:
                    uid_part = item[0].decode('ascii', errors='ignore').split()[0]
                    headers_dict[uid_part.encode()] = item[1]
                except (ValueError, IndexError):
                    pass
        i += 1
    return headers_dict


def fetch_imap(host: str, port: int, user: str, password: str,
               folder: str, limit: int, offset: int, no_verify: bool) -> tuple[list[dict], str, int, int]:
    """
    Returns (emails, debug_info).
    Two-stage search:
      1. Server-side SUBJECT keyword search  (fast, targeted)
      2. Fallback: SINCE last 90 days        (catches unmatched subjects)
         followed by client-side keyword filter on subject + sender
    """
    ctx = ssl.create_default_context()
    if no_verify:
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE

    conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
    try:
        conn.login(user, password)
        conn.select(folder or 'INBOX', readonly=True)

        # ── Stage 1: server-side keyword search ──────────────────────────────
        all_uids: set[bytes] = set()
        search_errors: list[str] = []

        for kw in SEARCH_KEYWORDS:
            try:
                typ, data = conn.uid('SEARCH', 'SUBJECT', f'"{kw}"')
                if typ == 'OK' and data:
                    all_uids |= _collect_uids(data)
            except Exception as e:
                search_errors.append(f'"{kw}": {type(e).__name__}')

        kw_search_hits = len(all_uids)
        use_fallback   = (kw_search_hits == 0)

        # ── Stage 2: SINCE fallback if keyword search found nothing ──────────
        if use_fallback:
            cutoff = (datetime.now() - timedelta(days=FALLBACK_DAYS)).strftime('%d-%b-%Y')
            try:
                typ, data = conn.uid('SEARCH', 'SINCE', cutoff)
                if typ == 'OK' and data:
                    all_uids |= _collect_uids(data)
                print(f'[IMAP Proxy] Keyword-Suche: 0 Treffer → SINCE-Fallback ({len(all_uids)} UIDs, Ordner: {folder})')
            except Exception as e:
                print(f'[IMAP Proxy] SINCE-Fallback Fehler: {type(e).__name__}: {e}')

        if not all_uids:
            info = f'Keine UIDs gefunden. Ordner: {folder}.'
            if search_errors:
                info += f' Suchfehler: {"; ".join(search_errors)}'
            return [], info, 0, 0

        # Sort descending (newest first); fetch more when we'll filter client-side
        uid_list   = sorted(all_uids, key=lambda u: int(u), reverse=True)
        total_uids = len(uid_list)

        # Apply offset and limit for pagination
        uid_list_paginated = uid_list[offset:offset + limit]

        # Fetch more UIDs if we need to filter client-side (fallback search)
        if use_fallback:
            uid_list_paginated = uid_list[offset:offset + limit * 5]
            uid_list_paginated = uid_list_paginated[:500]  # Cap at 500

        kw_lower = [k.lower() for k in SEARCH_KEYWORDS]
        emails: list[dict] = []

        if uid_list_paginated:
            try:
                # ── BATCH FETCH: fetch all UIDs in one request ──────────────────
                uids_batch = b','.join(uid_list_paginated)
                typ, data = conn.uid('fetch', uids_batch, '(RFC822.HEADER)')

                if typ == 'OK' and data:
                    headers_dict = _extract_all_headers_batch(data)

                    for uid in uid_list_paginated:
                        if len(emails) >= limit:
                            break
                        try:
                            uid_str = uid.decode('ascii', errors='ignore') if isinstance(uid, bytes) else str(uid)
                            raw = headers_dict.get(uid)
                            if not raw:
                                continue

                            parsed = headers_to_email_obj(raw, uid_str)

                            # Client-side filter only needed for SINCE-fallback results
                            if use_fallback:
                                haystack = (parsed['subject'] + ' ' + parsed['from']).lower()
                                if not any(k in haystack for k in kw_lower):
                                    continue

                            emails.append(parsed)
                        except Exception as e:
                            print(f'[IMAP Proxy] Parse-Fehler UID {uid_str}: {type(e).__name__}: {e}')
            except Exception as e:
                print(f'[IMAP Proxy] Batch-Fetch Fehler: {type(e).__name__}: {e}')

        # Calculate pagination info
        has_more = (offset + limit) < total_uids
        next_offset = offset + limit if has_more else offset

        mode = 'Betreff-Suche' if not use_fallback else 'Zeitraum-Fallback (90 Tage)'
        info = (f'Modus: {mode} | Ordner: {folder} | '
                f'UIDs: {total_uids} | Emails zurückgegeben: {len(emails)} | '
                f'Offset: {offset}, Limit: {limit}')
        if search_errors:
            info += f' | Suchfehler: {"; ".join(search_errors)}'
        return emails, info, total_uids, has_more

    finally:
        try:
            conn.logout()
        except (imaplib.IMAP4.error, OSError) as exc:
            logger.debug('IMAP logout failed: %s', type(exc).__name__)


# ── POP3 fetch ────────────────────────────────────────────────────────────────

def fetch_pop3(host: str, port: int, user: str, password: str,
               limit: int, offset: int, no_verify: bool) -> tuple[list[dict], int, bool]:
    ctx = ssl.create_default_context()
    if no_verify:
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE

    conn = poplib.POP3_SSL(host, port, context=ctx)
    try:
        conn.user(user)
        conn.pass_(password)

        _, mailbox_list, _ = conn.list()
        total = len(mailbox_list)
        if total == 0:
            return [], 0, False

        # Take the last `limit + offset` messages (newest in POP3 = highest number)
        # For pagination: skip `offset` newest messages
        start = max(0, total - limit - offset)
        msg_nums = list(range(total, start, -1))   # descending: total → start+1

        # Apply offset for pagination
        msg_nums = msg_nums[offset:offset + limit]

        kw_lower = [kw.lower() for kw in SEARCH_KEYWORDS]
        emails   = []

        for num in msg_nums:
            try:
                # TOP fetches headers + 0 body lines → no full body transfer
                _, lines, _ = conn.top(num, 0)
                raw    = b'\r\n'.join(lines)
                parsed = headers_to_email_obj(raw, str(num))

                # Client-side keyword filter (POP3 has no server-side search)
                subj_lower = parsed['subject'].lower()
                from_lower = parsed['from'].lower()
                if any(kw in subj_lower or kw in from_lower for kw in kw_lower):
                    emails.append(parsed)
            except Exception:
                continue

        # Pagination info
        has_more = (offset + limit) < total
        return emails, total, has_more
    finally:
        try:
            conn.quit()   # QUIT without any DELE = no messages deleted
        except (poplib.error_proto, OSError) as exc:
            logger.debug('POP3 quit failed: %s', type(exc).__name__)


# ── HTTP handler ──────────────────────────────────────────────────────────────

class ProxyHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(204)      # status line MUST come before headers
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        # Defence-in-depth: reject non-localhost even though we bind to 127.0.0.1
        if self.client_address[0] not in ('127.0.0.1', '::1'):
            self._json({'error': 'Nur lokaler Zugriff erlaubt'}, 403)
            return

        # Allowed paths only
        if self.path not in ('/', '/ping'):
            self._json({'error': 'Pfad nicht gefunden'}, 404)
            return

        # Parse body
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            data   = json.loads(body or '{}')
        except (ValueError, json.JSONDecodeError):
            self._json({'error': 'Ungültige JSON-Eingabe'}, 400)
            return

        # Health-check ping
        if self.path == '/ping':
            self._json({'status': 'ok', 'message': 'Proxy läuft'})
            return

        # Extract & validate parameters
        host      = re.sub(r'[^a-zA-Z0-9.\-]', '', str(data.get('host',      '')).strip())
        port      = int(data.get('port', 993))
        protocol  = 'pop3' if str(data.get('protocol', 'imap')).lower() == 'pop3' else 'imap'
        folder    = str(data.get('folder',    'INBOX')).strip() or 'INBOX'
        user      = str(data.get('user',      '')).strip()
        password  = str(data.get('pass',      ''))
        limit     = max(5, min(200, int(data.get('limit', 50))))
        offset    = max(0, int(data.get('offset', 0)))
        no_verify = bool(data.get('noVerify', False))

        if not host:
            self._json({'error': 'Server-Adresse fehlt oder ungültig'}, 400); return
        if not (1 <= port <= 65535):
            self._json({'error': 'Ungültiger Port'}, 400); return
        if not user:
            self._json({'error': 'Benutzername fehlt'}, 400); return
        if not password:
            self._json({'error': 'Passwort fehlt'}, 400); return
        # IMAP folder name: only allow alphanumerics + a few safe separators.
        # Prevents injection of IMAP control characters (CR/LF, quotes, backslashes).
        if not re.match(r'^[A-Za-z0-9._\-/ ]{1,100}$', folder):
            self._json({'error': 'Ungültiger Ordner-Name'}, 400); return

        try:
            # ── Check cache (use cache key without password) ────────────────────────
            cached_response = RESPONSE_CACHE.get(host, user, folder, limit, offset)
            if cached_response:
                print(f'[IMAP Proxy] Cache HIT | Ordner: {folder} | Offset: {offset}, Limit: {limit}')
                self._json(cached_response)
                return

            # ── Fetch from mail server ──────────────────────────────────────────────
            if protocol == 'pop3':
                emails, total_count, has_more = fetch_pop3(host, port, user, password, limit, offset, no_verify)
                debug  = f'POP3 | Emails: {len(emails)} | Total: {total_count}'
            else:
                emails, debug, total_count, has_more = fetch_imap(host, port, user, password, folder, limit, offset, no_verify)

            print(f'[IMAP Proxy] {debug}')

            # ── Build response with pagination info ─────────────────────────────────
            response = {
                'status': 'ok',
                'count': len(emails),
                'total': total_count,
                'has_more': has_more,
                'next_offset': offset + limit if has_more else offset,
                'emails': emails,
                'debug': debug
            }

            # ── Cache successful response ───────────────────────────────────────────
            RESPONSE_CACHE.set(host, user, folder, limit, offset, response)

            self._json(response)

        except (imaplib.IMAP4.error, poplib.error_proto) as exc:
            msg = str(exc).replace(password, '***')   # scrub pw from error
            self._json({'error': f'Mail-Server Fehler: {msg}'}, 502)

        except ssl.SSLCertVerificationError as exc:
            self._json({'error': (
                f'SSL-Zertifikat ungültig: {exc}. '
                'Für eigene Server mit selbst-signiertem Zertifikat: '
                '"Zertifikat nicht prüfen" aktivieren.'
            )}, 502)

        except ssl.SSLError as exc:
            self._json({'error': f'SSL-Fehler: {exc}'}, 502)

        except ConnectionRefusedError:
            self._json({'error': (
                f'Verbindung zu {host}:{port} abgelehnt. '
                'Server-Adresse und Port prüfen.'
            )}, 502)

        except TimeoutError:
            self._json({'error': 'Timeout – Server antwortet nicht (20 s).'}, 504)

        except Exception as exc:
            msg = str(exc).replace(password, '***')
            self._json({'error': f'Fehler: {msg}'}, 500)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._set_cors_headers()
        self.send_header('Content-Type',   'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control',  'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Override default logger: never log request body (contains credentials).
        # Log only method + status code.
        print(f'[IMAP Proxy] {self.address_string()} {args[0]} → {args[1]}')


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), ProxyHandler)
    print('╔══════════════════════════════════════════════════╗')
    print('║   Bewerbungs-Tracker  IMAP/POP3 Proxy           ║')
    print(f'║   Läuft auf http://{HOST}:{PORT}              ║')
    print('║   Stoppen: Strg+C                               ║')
    print('╚══════════════════════════════════════════════════╝')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nProxy gestoppt.')
        server.server_close()
