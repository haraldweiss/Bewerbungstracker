# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Indeed-Email-Source: liest Indeed-Job-Empfehlungen aus einem IMAP-Folder.

User-Credentials kommen aus `User.imap_*`. Der Adapter verbindet direkt
zum IMAP-Server (kein Mac-Proxy, da der Proxy nur Header liefert).

Parsing: Regex zuerst, AI-Fallback (ai-provider-service) wenn unvollständig.
"""
from __future__ import annotations

import concurrent.futures as _futures
import email
import imaplib
import json
import logging
import re
import ssl
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Optional

from services.job_sources.base import JobSourceAdapter, FetchedJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformProfile:
    """Plattform-spezifische Daten für den EmailJobsAdapter.

    Nur Daten, keine Logik. Profile werden in `PROFILES`-Dict registriert
    und vom Adapter via `EmailJobsAdapter(config, user, profile=...)`
    injected.
    """
    name: str
    source_label: str
    from_filter: str
    from_whitelist: tuple[str, ...]
    url_pattern: "re.Pattern"
    subject_patterns: tuple
    body_title_re: "re.Pattern"
    body_company_re: "re.Pattern"
    body_location_re: "re.Pattern"
    digest_threshold: int = 3
    ai_hint: str = ""
    # Optionaler Body-Block-Pattern: matched zusammenhängende Card-Struktur
    # mit named groups (title, company, location, url). Greift wenn die
    # einzelnen body_*_re-Label-Pattern nichts finden. Für Plattformen wo
    # der Body keine "Label:"-Felder nutzt (LinkedIn, XING).
    body_card_re: "re.Pattern | None" = None
    # Hardcoded Title-Blacklist (zusätzlich zum AI-gelernten title_blacklist).
    # Greift IMMER, egal welches Pattern aktiv ist. Wird im Adapter
    # angewendet, nachdem body_card_re ein title-Match liefert. Schützt vor
    # offensichtlichen Marketing-Headers die LinkedIn/XING in jeder Mail
    # nutzen (Section-Header vor Job-Gruppen etc.).
    hard_title_blacklist_re: "re.Pattern | None" = None
    # Subject must contain AT LEAST one of these substrings (case-insensitive).
    # Default empty → no subject filter applied (backward-compatible).
    # Use for platforms that emit mixed mail (jobs + news + birthdays etc.)
    # from the same domain, e.g. XING.
    subject_must_contain: tuple[str, ...] = ()
    # Optional platform-specific hint added to the AI-pattern-learner prompt.
    # Tells the AI about structural quirks (e.g. XING uses title-in-link cards).
    ai_schema_hint: str = ""


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
# www.indeed.com, ...) und jeder Pfad ausser /pagead/clk (Sponsored-Ad-
# Click-Tracker — die expirieren und führen zu Suchergebnis statt Job).
# Wir behalten cts.indeed.com/v3/-Tracker als external_id und resolven sie
# später via HEAD-Request zur canonical viewjob-URL.
_INDEED_URL_RE = re.compile(
    r'(https?://(?:[a-z0-9\-.]+\.)?indeed\.(?:de|com|co\.uk|fr|it|es)/'
    r'(?!pagead/clk)'
    r'[^\s\)<>"\'\\]+)',
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


PROFILES: dict[str, PlatformProfile] = {
    "indeed": PlatformProfile(
        name="indeed",
        source_label="Indeed",
        from_filter="from:indeed",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?indeed\.(?:de|com|co\.uk|fr|it|es)$",
        ),
        url_pattern=_INDEED_URL_RE,
        subject_patterns=tuple(_SUBJECT_PATTERNS),
        body_title_re=_BODY_TITLE_RE,
        body_company_re=_BODY_COMPANY_RE,
        body_location_re=_BODY_LOCATION_RE,
        # Indeed-Mails sind meist Single-Job; auch die enthalten 3-7
        # unique Indeed-URLs (Job-Tracker, Profile-Edit, Unsubscribe,
        # Footer-Links). digest_threshold=8 verhindert false-positiv
        # AI-Fallback-Trigger der bei Indeed-Latenz Worker-Timeouts
        # verursacht. Echte Multi-Job-Digests haben deutlich >8 URLs.
        digest_threshold=8,
        ai_hint=(
            "Indeed-Jobempfehlung. Click-Tracker-URLs cts.indeed.com/v3 "
            "bleiben als external_id (kein Auto-Follow)."
        ),
    ),
    "linkedin": PlatformProfile(
        name="linkedin",
        source_label="LinkedIn",
        from_filter="from:linkedin.com",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?linkedin\.com$",
        ),
        url_pattern=re.compile(
            r"https?://(?:www\.)?linkedin\.com/(?:jobs/view|comm/jobs/view)/\d+[^\s)<>\"'\\]*",
            re.IGNORECASE,
        ),
        subject_patterns=(
            # Echte LinkedIn-Subjects: "<Title> bei <Company>" ohne Prefix.
            # Prefix optional für andere Mail-Quellen.
            re.compile(
                r"^(?:(?:New job|Neue Stelle|Job alert)\s*:?\s*)?"
                r"(?P<title>.+?)\s+(?:at|bei|@)\s+(?P<company>.+?)"
                r"(?:\s*[-–|]\s*LinkedIn.*)?$",
                re.IGNORECASE,
            ),
        ),
        # LinkedIn Body-Struktur (kein "Label:"-Schema): direkt vor dem
        # "Jobangebot ansehen:"-URL stehen 3 Zeilen Title/Company/Location,
        # ggf. mit Whitespace-Padding und CR. Lookahead matched die URL,
        # die 3 Capture-Gruppen sind die Zeilen davor.
        body_title_re=re.compile(
            r"(?:Position|Job\s*Title|Jobtitel|Stelle)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_company_re=re.compile(
            r"(?:Company|Firma|Unternehmen|Employer)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_location_re=re.compile(
            r"(?:Location|Standort|Ort|Place)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        # LinkedIn-Card: 3 Zeilen Title / Company / Location, gefolgt von
        # 0–5 Trenner-Zeilen, dann optionaler Label-Text, dann Job-URL.
        # Der Label ist typisch "Jobangebot ansehen", "View job" etc. —
        # flexibel gehalten da LinkedIn das Format aendert.
        body_card_re=re.compile(
            r"^[ \t]*(?P<title>\S[^\r\n]{2,200}\S)\s*\r?\n"
            r"[ \t]*(?P<company>\S[^\r\n]{1,150}\S)\s*\r?\n"
            r"[ \t]*(?P<location>\S[^\r\n]{1,80}\S)\s*\r?\n"
            r"(?:[^\r\n]*\r?\n){0,5}?"
            r"[^\S\r\n]*(?:[A-Za-z\u00e4\u00f6\u00fc\u00df].{0,60})?\s*:?\s*"
            r"(?P<url>https?://(?:www\.)?linkedin\.com/[^\s\r\n)<>\"']+)",
            re.IGNORECASE | re.MULTILINE,
        ),
        digest_threshold=3,
        # LinkedIn versendet auch Nicht-Job-Mails (Profilaufrufe, Geburtstage,
        # Verbindungsanfragen) von derselben Domain. Der Subject-Filter
        # reduziert False-Positives drastisch.
        subject_must_contain=(
            "bei ", " at ",
            "job", "stelle", "stellenvorschlag", "stellenangebot",
            "jobempfehlung", "jobs you may", "new job",
            "positionen als",  # "11 neue Positionen als Entwickler"
        ),
        ai_hint=(
            "LinkedIn-Jobempfehlungs-Digest. Jede Job-Card hat einen "
            "linkedin.com/jobs/view/<ID>-Link. "
            "Extrahiere {title, company, location, url} pro Job als JSON-Array."
        ),
        # Hardcoded Marketing-Header die LinkedIn vor Job-Cards einstreut.
        # Diese sind KEINE Job-Titel, sondern Sektion-Header. Greift IMMER,
        # auch wenn das AI-gelernte title_blacklist sie nicht enthält.
        hard_title_blacklist_re=re.compile(
            r"^(?:"
            r"\d+\s+neue?r?\s+(?:Position|Stelle|Job|Mitarbeiter|Firma)|"
            r"\d+\s+weiter(?:e|en)\s+(?:Position|Stelle|Job|Mitarbeiter)|"
            r"Ihre Jobbenachrichtigung|"
            r"Top-Jobs?|"
            r"\d+\s+neue?r?\s+Jobs?|"
            r"\d+\s+weitere\s+Jobs?|"
            r"Ergebnisse der|"
            r"Vorschläge für|"
            r"Empfohlene Jobs|"
            r"Recommended (?:for you|jobs)|"
            r"Lust auf|"
            r"Jobs you may be interested in|"
            r"Bewerben Sie sich als Erste|"
            r"Stellen, die dir gefallen könnten|"
            r"Stellen, die (?:dir|Ihnen) gefallen|"
            r"Aufbauend auf deinen Fähigkeiten|"
            r"Beliebt bei Bewerbern|"
            r"\u00c4hnliche Jobs?|"                          # "Ähnliche Jobs"
            r"Neue Stellenangebote|"
            r"Passende (?:Stellen|Jobs) für|"
            r"Jobs in deinem (?:Netzwerk|Bereich)|"
            r"Stellen in deinem (?:Netzwerk|Bereich)|"
            r"Das könnte dich interessieren|"
            r"Das könnte Ihnen gefallen|"
            r"Möglicherweise interessant"
            r")",
            re.IGNORECASE,
        ),
    ),
    "xing": PlatformProfile(
        name="xing",
        source_label="XING",
        from_filter="from:xing.com",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?xing\.com$",
        ),
        # XING-Mail-URLs nutzen drei Formate:
        #   /jobs/<slug>      — Web-UI-Direktlinks
        #   /app/jobs/<id>    — Legacy
        #   /m/<short-token>  — Mail-Tracker (Short-URL, Hauptformat in Job-Mails)
        url_pattern=re.compile(
            r"https?://(?:www\.)?xing\.com/(?:jobs|app/jobs|m)/[^\s)<>\"'\\]+",
            re.IGNORECASE,
        ),
        subject_patterns=(
            # Echte XING-Subjects: "<Title> bei <Company>" oft ohne Prefix.
            # Prefix optional.
            re.compile(
                r"^(?:(?:Neue\s+(?:Stelle|Jobempfehlung)|New\s+job|Stellenangebot)"
                r"\s*:?\s*)?(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)"
                r"(?:\s*[-–|]\s*XING.*)?$",
                re.IGNORECASE,
            ),
        ),
        body_title_re=re.compile(
            r"(?:Stelle|Position|Jobtitel|Job\s*Title)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_company_re=re.compile(
            r"(?:Firma|Unternehmen|Company|Arbeitgeber|Employer)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_location_re=re.compile(
            r"(?:Ort|Standort|Location|Place)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        digest_threshold=3,
        ai_hint=(
            "XING-Jobempfehlungs-Digest (deutsch). Jede Job-Card hat einen "
            "xing.com/jobs/<slug>-Link. "
            "Extrahiere {title, company, location, url} pro Job als JSON-Array."
        ),
        subject_must_contain=(
            "stelle", "stellenangebot", "stellenvorschlag",
            "neue jobs", "jobs für", "job alert", "jobempfehlung",
        ),
        ai_schema_hint=(
            "XING-Job-Mails sind PLAIN TEXT (kein Markdown). Jede Job-Card hat "
            "diese Struktur auf separaten Zeilen:\n"
            "  1. <optional Hook-Zeile> (z.B. 'Bis 35% mehr Gehalt', 'Zu den Ersten gehören')\n"
            "  2. <Title>\n"
            "  3. => <URL>\n"
            "  4. <leere Zeile>\n"
            "  5. <Company>\n"
            "  6. <Location>\n"
            "Setze:\n"
            "  body_card.fields_before_url = ['title']\n"
            "  body_card.url_labels = ['=>']\n"
            "  body_card.fields_after_url = ['company', 'location']\n"
            "  body_card.title_in_url_link = false\n"
            "  body_card.separator_lines_allowed = 3"
        ),
    ),
}


def _apply_subject_filter(
    mails: list[dict], must_contain: tuple[str, ...],
) -> list[dict]:
    """Filter mails: keep only those whose subject (case-insensitive) contains
    at least one of `must_contain`. Empty tuple → no filter."""
    if not must_contain:
        return list(mails)
    needles = tuple(s.lower() for s in must_contain)
    return [
        m for m in mails
        if any(n in (m.get("subject") or "").lower() for n in needles)
    ]


# Generic defaults für auto-generated Plattformen (DB-resolved).
_GENERIC_SUBJECT_PATTERN = re.compile(
    r"^(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)\s*$",
    re.IGNORECASE,
)


# Plattform-spezifische deterministische Title-Blacklists für DB-derived
# Profile (PROFILES-Dict hat eigene hardcoded Listen). Greift IMMER, auch
# wenn das AI-gelernte learned_email_patterns.title_blacklist die Strings
# nicht enthält — verhindert Drift bei zukünftigen Pattern-Re-Trains.
# Slug → compiled Regex.
_DB_PROFILE_HARD_BLACKLISTS: dict[str, "re.Pattern"] = {
    "heyjobs": re.compile(
        r"^(?:"
        # UI-Buttons / Navigation-Links die der Card-Regex als
        # "[Text](URL)"-Markdown matched (Trailing " (" ist häufig):
        r"Jobs found for|"                  # Mail-Header
        r"Von\s+Job[\s-]?Alarmen\s+abmelden|"  # Unsubscribe-CTA
        r"Zu\s+Deinen\s+Bewerbungen|"       # Navigation
        r"Feedback\s+anfragen|"             # UI-Button
        r"Du\s+kannst\s+jetzt\s+einmal|"    # Mailtext-Anfang
        # Bereits in DB-Pattern enthaltene Strings nochmal hier hardcoden,
        # damit sie bei Re-Train ohne diese Strings nicht verloren gehen:
        r"AGB|Datenschutzerk|Impressum|Newsletter\s+abmelden|"
        r"Direkt\s+bewerben|Job\s+anzeigen|Mehr\s+Jobs|"
        r"Jobs\s+aufs\s+Handy|Traumjob\s+finden|"
        r"Wir\s+haben\s+neue\s+Jobs|"
        # Email-Footer / Impressum / CTA die als Job-Cards durchrutschen:
        r"HeyJobs\s+(?:GmbH|AG|UG|SE|Inc\.?|Ltd\.?)|"
        r"Frage\s+jetzt\s+nach\s+Feedback|"
        r"Paul-Lincke-Ufer|"
        r"Geschäftsführer:|"
        r"HeyJobs(?:\s|$|\(|-)"
        r")(?:\s|\(|$)",
        re.IGNORECASE,
    ),
    # StepStone-Empfehlungs-Mails ("Du hast gute Chancen auf ein Interview")
    # streuen Marketing-Sektion-Header ein, die KEINE Job-Titel sind. Ohne
    # diesen Filter rutschte "Erhöhe deine Chancen – Du passt auch gut zu diesen
    # Jobs" als Titel rein (und der echte Jobtitel als Firma).
    "stepstone": re.compile(
        r"^(?:"
        r"Erhöhe\s+deine\s+Chancen|"
        r"Du\s+passt\s+auch\s+gut|"
        r"Passt\s+(?:hervorragend|gut|perfekt)|"
        r"Neue?s?\s+Jobangebot\s+basierend|"
        r"Du\s+hast\s+gute\s+Chancen|"
        r"Top-?Fähigkeiten|"
        r"Das\s+könnte\s+dich\s+interessieren|"
        r"Weitere\s+(?:Jobs|Stellen)|"
        r"Ähnliche\s+(?:Jobs|Stellen)|"
        r"Empfohlene\s+(?:Jobs|Stellen)|"
        r"Jobs?,?\s+die\s+(?:dir|zu\s+dir)"
        r")",
        re.IGNORECASE,
    ),
}


def _build_profile_from_row(row) -> PlatformProfile:
    """Konstruiert PlatformProfile aus DB-Row. Auto-Generation aus domain
    wenn url_pattern_override / from_whitelist_override nicht gesetzt sind.

    Defensive: ungültige Regex-Overrides fallen auf Auto-Generation zurück
    (mit Warn-Log), damit ein malformed override nicht den gesamten
    IMAP-Fetch crasht.
    """
    import json as _json
    domain = row.domain
    domain_esc = re.escape(domain)

    auto_url_pattern_str = (
        rf"https?://(?:[a-z0-9.-]+\.)?{domain_esc}/[^\s)<>\"'\\]+"
    )
    if row.url_pattern_override:
        try:
            url_pattern = re.compile(row.url_pattern_override, re.IGNORECASE)
        except re.error as exc:
            logger.warning(
                "PlatformProfile slug=%s: url_pattern_override ungültig (%s) "
                "— fallback auf auto-generated", row.slug, exc,
            )
            url_pattern = re.compile(auto_url_pattern_str, re.IGNORECASE)
    else:
        url_pattern = re.compile(auto_url_pattern_str, re.IGNORECASE)

    auto_from_whitelist = (rf"@(?:[a-z0-9.-]+\.)?{domain_esc}$",)
    if row.from_whitelist_override:
        # Validate by compiling — fall back if invalid
        try:
            re.compile(row.from_whitelist_override)
            from_whitelist = (row.from_whitelist_override,)
        except re.error as exc:
            logger.warning(
                "PlatformProfile slug=%s: from_whitelist_override ungültig (%s) "
                "— fallback auf auto-generated", row.slug, exc,
            )
            from_whitelist = auto_from_whitelist
    else:
        from_whitelist = auto_from_whitelist

    # Robust JSON-parse: malformed → []
    try:
        smc = _json.loads(row.subject_must_contain or "[]")
        if not isinstance(smc, list):
            smc = []
    except (ValueError, TypeError):
        smc = []
    subject_must_contain = tuple(s for s in smc if isinstance(s, str))

    return PlatformProfile(
        name=row.slug,
        source_label=row.display_name,
        from_filter=f"from:{domain}",
        from_whitelist=from_whitelist,
        url_pattern=url_pattern,
        subject_patterns=(_GENERIC_SUBJECT_PATTERN,),
        body_title_re=_BODY_TITLE_RE,
        body_company_re=_BODY_COMPANY_RE,
        body_location_re=_BODY_LOCATION_RE,
        digest_threshold=row.digest_threshold,
        ai_hint="",
        body_card_re=None,
        hard_title_blacklist_re=_DB_PROFILE_HARD_BLACKLISTS.get(row.slug),
        subject_must_contain=subject_must_contain,
        ai_schema_hint=row.ai_schema_hint or "",
    )


def get_profile(slug: str) -> PlatformProfile:
    """Resolve Plattform-Slug zu PlatformProfile.

    1. Hardcoded PROFILES-Dict (legacy, getestet — Vorrang).
    2. DB-Tabelle platform_profiles (user-defined).
    3. KeyError wenn nichts gefunden.
    """
    if slug in PROFILES:
        return PROFILES[slug]
    from models import PlatformProfileRow
    row = PlatformProfileRow.query.filter_by(slug=slug).first()
    if row is None:
        raise KeyError(f"Unknown platform: {slug}")
    return _build_profile_from_row(row)


class EmailJobsAdapter(JobSourceAdapter):
    """Liest Job-Empfehlungs-Emails (Indeed, LinkedIn, XING, …) aus einem
    IMAP-Folder des Users.

    Config:
        folder         (str)  — IMAP-Ordnername, Default 'Indeed'
        lookback_days  (int)  — Wie weit zurück fetchen, Default 30
        limit          (int)  — Max Emails pro Fetch, Default 100

    `platform_profile` (PlatformProfile) — Plattform-spezifische Regexe,
    From-Whitelist, AI-Hint. Default `PROFILES["indeed"]` für Rückwärts-
    kompatibilität mit dem alten `IndeedEmailAdapter`.

    Erfordert User-Kontext (im Adapter via Constructor-kwarg) für
    IMAP-Credentials (`user.imap_host`, `user.imap_user`,
    `user.decrypted_imap_password`).
    """

    # Hard cap auf AI-Fallback-Calls pro Adapter-Lauf — verhindert dass
    # ein großes Email-Batch (z.B. 171 Mails) den gunicorn-Worker (timeout
    # 180s) durch Ollama/Claude-Latenz killt. Regex-only läuft sub-second.
    AI_FALLBACK_BUDGET = 10

    def __init__(self, config: dict, user=None, platform_profile: PlatformProfile | None = None):
        super().__init__(config)
        self.user = user
        self.profile = platform_profile if platform_profile is not None else PROFILES["indeed"]
        self._ai_calls_used = 0
        # Wenn ein AI-Call innerhalb DIESES fetch()-Laufs fehlschlaegt
        # (Timeout, Parse-Fehler), schalten wir AI fuer den Rest des Laufs ab.
        # Verhindert dass mehrere langsame Digest-Mails nacheinander den
        # gunicorn-Worker-Timeout (180s) hochaddieren und die ganze Import-
        # Runde mit Apache-HTML-500 abschmiert.
        self._ai_disabled_for_run = False
        self._learned_compiled = None
        self._learned_lookup_done = False

    def _get_learned_pattern(self):
        """Lazy-load learned pattern from DB. Cached for adapter lifetime."""
        if self._learned_lookup_done:
            return self._learned_compiled
        self._learned_lookup_done = True
        try:
            from models import LearnedEmailPattern
            from services.job_sources.pattern_learner import compile_pattern
            import json as _json
            row = LearnedEmailPattern.query.filter_by(
                platform=self.profile.name, is_active=True,
            ).first()
            if row is None:
                return None
            # Plattform-URL-Pattern (hardcoded in PROFILES) als Constraint
            # an compile_pattern uebergeben — verhindert dass AI-gelernte
            # url_labels Marketing-Links matchen (LinkedIn /games/...).
            self._learned_compiled = compile_pattern(
                _json.loads(row.pattern_json),
                url_pattern_str=self.profile.url_pattern.pattern,
            )
        except Exception as exc:
            logger.warning(
                "Learned-pattern-lookup fehlgeschlagen für %s: %s",
                self.profile.name, exc,
            )
            self._learned_compiled = None
        return self._learned_compiled

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
        self._ai_disabled_for_run = False
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
                result = self._parse_email(normalized)
                if result is None:
                    continue
                if isinstance(result, list):
                    jobs.extend(result)
                else:
                    jobs.append(result)
            except Exception as exc:
                logger.warning("Email-Jobs-Parse fehlgeschlagen: %s", exc)
                continue
        return jobs

    def fetch(self) -> list[FetchedJob]:
        if self.user is None:
            raise RuntimeError("EmailJobsAdapter benötigt User-Kontext (kwarg user=...)")

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

        # Gesamt-Wall-Clock-Budget für den kompletten Run (IMAP-Fetch +
        # Parse + AI-Fallback). Muss deutlich unter gunicorn --timeout
        # (240s) liegen, damit der Worker nicht gekillt wird und der User
        # ein partial result + sauberen Status sieht statt 502.
        _RUN_BUDGET_S = 150
        deadline = _time.monotonic() + _RUN_BUDGET_S

        emails = self._fetch_emails(
            host, imap_user, password, folder, lookback_days, limit,
            deadline=deadline,
        )

        self._ai_calls_used = 0  # AI-Budget pro Lauf zurücksetzen
        self._ai_disabled_for_run = False
        jobs: list[FetchedJob] = []
        for em in emails:
            if _time.monotonic() >= deadline:
                logger.warning(
                    "fetch() Wall-Clock-Budget %ss erschöpft nach %d/%d Mails — "
                    "Rest übersprungen (verhindert gunicorn-Worker-Kill)",
                    _RUN_BUDGET_S, len(jobs), len(emails),
                )
                break
            try:
                result = self._parse_email(em, deadline=deadline)
                if result is None:
                    continue
                if isinstance(result, list):
                    jobs.extend(result)
                else:
                    jobs.append(result)
            except Exception as exc:
                logger.warning("Email-Jobs-Parse fehlgeschlagen: %s", exc)
                continue

        # Hit-Rate-Tracking: schreibt eine Markierung in last_error wenn
        # Trefferquote verdaechtig niedrig. UI rendert das als Warn-Badge.
        try:
            from models import JobSource
            from database import db
            src_id = getattr(self, '_source_id_for_tracking', None)
            if src_id and len(emails) >= 10:
                ratio = len(jobs) / max(len(emails), 1)
                if ratio < 0.20:
                    JobSource.query.filter_by(id=src_id).update({
                        'last_error': (
                            f'pattern_low_hit_rate: {len(jobs)}/{len(emails)} '
                            f'({int(ratio*100)}%)'
                        )
                    })
                    db.session.commit()
                else:
                    existing = JobSource.query.get(src_id)
                    if existing and (existing.last_error or '').startswith('pattern_low_hit_rate'):
                        JobSource.query.filter_by(id=src_id).update({'last_error': None})
                        db.session.commit()
        except Exception:
            logger.exception("Hit-Rate-Tracking schlug fehl (non-fatal)")

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
        deadline: float | None = None,
    ) -> list[dict]:
        # timeout=30: socket-level Wall-Clock-Timeout für ALLE folgenden IMAP-Ops
        # (login/select/search/fetch). Ohne diesen Parameter blockt SSL.read()
        # unbegrenzt wenn der IMAP-Server die Connection still droppt (NAT-Reset,
        # IDLE-Drop) — gunicorn killt dann den Worker bei 180s, Apache liefert
        # 502 mit HTML, Frontend zeigt "Server-Timeout (HTML-Antwort)".
        conn = imaplib.IMAP4_SSL(
            host, 993, ssl_context=ssl.create_default_context(), timeout=30
        )
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
            # Pro Plattform: Gmail-spezifischer X-GM-RAW-Filter zuerst, sonst
            # IMAP-Standard-FROM-Search. `from:` aus dem Profile (z.B.
            # 'from:indeed', 'from:linkedin.com', 'from:xing.com').
            gm_filter = self.profile.from_filter
            # IMAP-FROM-Search braucht nur den Domain-Teil ohne 'from:'-Prefix.
            imap_from = gm_filter.split(':', 1)[1] if ':' in gm_filter else gm_filter
            try:
                gm_query = f'"{gm_filter} newer_than:{lookback_days}d"'
                typ, msgnums = conn.search(None, 'X-GM-RAW', gm_query)
            except imaplib.IMAP4.error:
                typ, msgnums = conn.search(None, f'(SINCE {since_date} FROM "{imap_from}")')
            if typ != 'OK':
                return []

            ids = msgnums[0].split() if msgnums and msgnums[0] else []
            # Neueste zuerst, gecapped auf limit.
            ids = ids[-limit:][::-1]

            out: list[dict] = []
            for msg_id in ids:
                # Wall-Clock-Check vor jedem IMAP-FETCH: bei langsamen
                # Servern (Gmail-Drossel, große Mails) kann der Socket-
                # Timeout (30s) zwar je Op greifen, addiert sich aber
                # über N Mails leicht über die gunicorn-Worker-Schwelle.
                if deadline is not None and _time.monotonic() >= deadline:
                    logger.warning(
                        "_fetch_emails Deadline erschöpft nach %d/%d Mails — "
                        "Rest übersprungen (verhindert gunicorn-Worker-Kill)",
                        len(out), len(ids),
                    )
                    break
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
            # Subject-Filter: für Plattformen wie XING die unter derselben
            # Domain auch Birthdays/Newsletter/News rausschicken. Default
            # tuple() → no-op (Indeed/LinkedIn unverändert).
            out = _apply_subject_filter(out, self.profile.subject_must_contain)
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

    def _parse_email(self, em: dict, *, deadline: float | None = None):
        """Regex-Parse zuerst, AI-Fallback falls Pflichtfelder fehlen.

        Returns `None`, ein einzelnes `FetchedJob` ODER eine Liste von
        `FetchedJob`s (Multi-URL-Digest-Fall).
        """
        subject = em.get('subject', '') or ''
        body = em.get('body', '') or ''

        # From-Whitelist-Check: blockiert Mails von fremden Domains direkt.
        # Wichtig wenn mehrere Plattform-Adapter parallel laufen oder ein
        # User die Mail in den falschen Ordner verschoben hat. Wird nur
        # angewendet, wenn `from` überhaupt gesetzt ist — leeres From-Feld
        # darf nicht blockieren (Pre-Fetched Test-Inputs ohne Header sind
        # legitim und der IMAP-SEARCH FROM-Filter hat bereits gefiltert).
        # Email-Adresse aus "Display Name <user@host>"-Format extrahieren;
        # ohne den Schritt würde der whitelist-Pattern mit "$"-Anker am
        # ">" scheitern (häufiges Format bei Gmail-Headern).
        raw_from = (em.get('from') or '').lower()
        addr_match = re.search(r'<([^>]+)>', raw_from)
        from_addr = addr_match.group(1) if addr_match else raw_from
        if from_addr and self.profile.from_whitelist:
            if not any(re.search(pat, from_addr) for pat in self.profile.from_whitelist):
                return None

        # Body-Card-Pattern: wenn die Plattform ein structured-card-Pattern
        # liefert (z.B. LinkedIn/XING: Title/Company/Location/URL-Block),
        # parse direkt aus dem Body — multiple Cards pro Mail.
        # Learned pattern overrides hardcoded body_card_re if active for this platform.
        learned = self._get_learned_pattern()
        active_card_re = learned.body_card_re if learned else self.profile.body_card_re
        active_title_blacklist = learned.title_blacklist_re if learned else None
        active_company_sep = learned.company_blacklist_separator_re if learned else None
        if active_card_re is not None:
            cards = list(active_card_re.finditer(body))
            if cards:
                jobs_from_cards = []
                for m in cards:
                    gd = m.groupdict()
                    t = (gd.get('title') or '').strip()
                    c = (gd.get('company') or '').strip()
                    loc = (gd.get('location') or '').strip() or None
                    u = (gd.get('url') or '').strip()
                    if not t or not u:
                        continue
                    # Mindest-Titellänge: Jobtitel sind nie kürzer als 5 Zeichen.
                    # Filtert Einzel-Wörter wie "AGB", "Vollzeit", "KI" aus die
                    # durch Tracking-Links (HeyJobs, LinkedIn) als Card-Matches
                    # auftauchen.
                    if len(t) < 5:
                        continue
                    # Trenner-Linien (z.B. "---") schlüpfen sonst als Title
                    # oder Company durch und schieben echte Werte raus.
                    if re.fullmatch(r"[\-=_~\*\.\s]{3,}", t):
                        continue
                    if c and re.fullmatch(r"[\-=_~\*\.\s]{3,}", c):
                        continue
                    # LinkedIn-Marketing-Header-Zeilen ausfiltern — die rutschen
                    # sonst als Title rein wenn der Card-Header direkt vor
                    # "Jobangebot ansehen" steht (statt einer echten Job-Card).
                    # Muss mit hard_title_blacklist_re (PROFILES linkedin) synchron bleiben.
                    if re.search(
                        r"(?i)^(?:"
                        r"\d+\s+neue?r?\s+(?:Position|Stelle|Job|Mitarbeiter|Firma)|"
                        r"\d+\s+weiter(?:e|en)\s+(?:Position|Stelle|Job|Mitarbeiter)|"
                        r"Ihre Jobbenachrichtigung|"
                        r"Top-Jobs?|"
                        r"\d+\s+neue?r?\s+Jobs?|"
                        r"\d+\s+weitere\s+Jobs?|"
                        r"Ergebnisse|"
                        r"Vorschläge\s+für|"
                        r"Empfohlene|"
                        r"Recommended|"
                        r"Lust auf|"
                        r"Beliebt bei|"
                        r"Aufbauend auf|"
                        r"Passende\s+(?:Stellen|Jobs)\s+für|"
                        r"Das könnte|"
                        r"Möglicherweise interessant|"
                        r"Stellen, die (?:dir|Ihnen) gefallen|"
                        r"\u00c4hnliche|"
                        r"Bewerben Sie sich als"
                        r")",
                        t,
                    ):
                        continue
                    # Learned-pattern title-blacklist + company-separator (if any)
                    if active_title_blacklist and active_title_blacklist.search(t):
                        continue
                    if active_company_sep and c and active_company_sep.match(c):
                        continue
                    # Profile-level hard-blacklist (greift IMMER, auch
                    # wenn kein learned pattern aktiv ist). Schuetzt vor
                    # offensichtlichen Marketing-Headers wie "11 neue
                    # Positionen als ..." die LinkedIn vor Job-Gruppen
                    # einstreut.
                    if (
                        self.profile.hard_title_blacklist_re
                        and self.profile.hard_title_blacklist_re.search(t)
                    ):
                        continue
                    jobs_from_cards.append(FetchedJob(
                        external_id=u[:512],
                        title=t[:512],
                        url=u[:4096],
                        company=(c[:255] if c else None),
                        location=(loc[:255] if loc else None),
                        description=body[:2000] if body else None,
                        posted_at=_parse_date(em.get('date')),
                        raw={
                            'message_id': em.get('message_id', ''),
                            'subject': subject,
                            'from': em.get('from', ''),
                            'card_match': True,
                        },
                    ))
                if jobs_from_cards:
                    return jobs_from_cards

        # Multi-URL-Digest-Erkennung: ≥ digest_threshold plattform-spezifische
        # Job-URLs im Body → Digest-Mail (z.B. LinkedIn "Jobs you may be
        # interested in"). Sofort AI-Fallback weil Subject-Regex hier
        # nutzlos ist (Subject zeigt nicht einen Job).
        urls_in_body = set(self.profile.url_pattern.findall(body))
        if len(urls_in_body) >= self.profile.digest_threshold:
            return self._ai_fallback_digest(em, deadline=deadline)

        title, company = self._parse_subject(subject)
        location = None
        url = None

        # URL aus Body (oder Subject, falls vorhanden)
        url_match = self.profile.url_pattern.search(body) or self.profile.url_pattern.search(subject)
        if url_match:
            # `.group(1)` falls die Pattern eine capture-group hat,
            # sonst `.group(0)` (gesamter Match).
            try:
                url = url_match.group(1)
            except IndexError:
                url = url_match.group(0)

        # Body-Fallback für Title/Company
        if not title:
            m = self.profile.body_title_re.search(body)
            if m:
                title = m.group(1).strip()
        if not company:
            m = self.profile.body_company_re.search(body)
            if m:
                company = m.group(1).strip()

        # Location
        m = self.profile.body_location_re.search(body)
        if m:
            location = m.group(1).strip()

        # AI-Fallback nur wenn:
        #   1. Pflichtfelder fehlen UND
        #   2. Mail sieht wie Job-Mail aus (URL bereits da ODER Plattform-Marker
        #      im Subject/From) — sonst sind das random Newsletter und ein
        #      AI-Call wäre Verschwendung UND
        #   3. AI-Budget für diesen Lauf noch nicht ausgeschöpft (siehe
        #      AI_FALLBACK_BUDGET).
        # Kombi sorgt dafür dass 171 Random-Inbox-Mails nicht den Worker
        # killen (gunicorn timeout 180s).
        if (not title or not company or not url) and self.user is not None:
            platform_name = self.profile.name.lower()
            looks_like_platform = (
                url is not None
                or platform_name in from_addr
                or platform_name in subject.lower()
            )
            if (
                looks_like_platform
                and not self._ai_disabled_for_run
                and self._ai_calls_used < self.AI_FALLBACK_BUDGET
            ):
                self._ai_calls_used += 1
                ai_data = _ai_extract(self.user, subject, body, deadline=deadline)
                if not ai_data:
                    self._ai_disabled_for_run = True
                if ai_data:
                    title = title or ai_data.get('title')
                    company = company or ai_data.get('company')
                    location = location or ai_data.get('location')
                    url = url or ai_data.get('url')

        # Minimum: title + url
        if not title or not url:
            return None

        # Tracker-URL (cts.indeed.com/v3/...) zu canonical Indeed-URL auflösen.
        # Best-effort: bei Fehler bleibt die Tracker-URL erhalten (Browser kann
        # ihr auch folgen, aber Dedup-Match gegen andere Sources wird besser
        # mit canonical URL). Nur für Indeed relevant.
        if self.profile.name == 'indeed' and 'cts.indeed.' in url.lower():
            resolved = _resolve_indeed_tracker(url)
            if resolved:
                url = resolved

        return FetchedJob(
            external_id=url[:512],
            title=title[:512],
            url=url[:4096],
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

    def _parse_subject(self, subject: str) -> tuple[Optional[str], Optional[str]]:
        """Versucht (title, company) aus dem Email-Subject zu extrahieren
        mittels der subject_patterns des aktiven Profils."""
        if not subject:
            return None, None
        for pat in self.profile.subject_patterns:
            m = pat.search(subject.strip())
            if m:
                return m.group('title').strip(), m.group('company').strip()
        return None, None

    def _ai_fallback_digest(self, em: dict, *, deadline: float | None = None) -> list[FetchedJob]:
        """AI-Fallback für Multi-URL-Digest-Mails (z.B. LinkedIn/XING).

        Erwartet vom Modell eine JSON-Liste von Objekten mit Keys
        title/company/location/url. Gibt eine Liste FetchedJob zurück
        (kann leer sein bei Fehler/Budget-Exhaustion).
        """
        if self.user is None:
            return []
        if self._ai_disabled_for_run:
            return []
        if self._ai_calls_used >= self.AI_FALLBACK_BUDGET:
            return []
        self._ai_calls_used += 1

        subject = em.get('subject', '') or ''
        body = em.get('body', '') or ''

        items = _ai_extract_digest(self.user, subject, body, self.profile, deadline=deadline)
        if not items:
            # Failure (Timeout / Parse-Fehler / leeres Ergebnis): AI fuer
            # den Rest dieses Laufs deaktivieren. Verhindert kumulierte
            # Timeouts wenn Ollama gerade lahm ist.
            self._ai_disabled_for_run = True
            return []

        out: list[FetchedJob] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = (item.get('title') or '').strip()
            url = (item.get('url') or '').strip()
            if not title or not url:
                continue
            # Marketing-Sektion-Header (z.B. StepStone "Erhöhe deine Chancen…")
            # auch im AI-Pfad filtern — der Card-Pfad tat das schon, dieser nicht.
            if (self.profile.hard_title_blacklist_re
                    and self.profile.hard_title_blacklist_re.search(title)):
                continue
            company = item.get('company') or None
            location = item.get('location') or None
            out.append(FetchedJob(
                external_id=url[:512],
                title=title[:512],
                url=url[:4096],
                company=(company[:255] if company else None),
                location=(location[:255] if location else None),
                description=body[:2000] if body else None,
                posted_at=_parse_date(em.get('date')),
                raw={
                    'message_id': em.get('message_id', ''),
                    'subject': subject,
                    'from': em.get('from', ''),
                    'digest': True,
                },
            ))
        return out


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


def _resolve_indeed_tracker(tracker_url: str, timeout: float = 4.0) -> Optional[str]:
    """Folgt einem cts.indeed.com Click-Tracker zur canonical Indeed-Job-URL.

    HEAD-Request mit kurzem Timeout (Indeed-Tracker antworten in ms).
    Cap auf ~3 Redirects. Bei Fehler/Timeout: None → Caller behält die
    Tracker-URL (Browser-Klick funktioniert weiter).

    SSRF-Schutz: Wir starten nur bei einer Tracker-URL die schon auf
    cts.indeed.* zeigt — und akzeptieren nur Final-URLs auf indeed.*-Domains.
    """
    try:
        import requests
        r = requests.head(tracker_url, allow_redirects=True, timeout=timeout)
    except Exception:
        return None
    final = (r.url or '').lower()
    # Schutz: nur indeed.*-Final-URLs übernehmen (kein Open-Redirect-Hijack
    # durch böse Tracker-Antworten).
    if 'indeed.' not in final or 'cts.indeed.' in final:
        return None
    return r.url


def _ai_extract(user, subject: str, body: str, *, deadline: float | None = None) -> Optional[dict]:
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
    # Harter Wall-Clock-Timeout via ThreadPoolExecutor: verhindert dass
    # ein langsamer Ollama-Token-Stream den gunicorn-Worker (180s) killt.
    # requests timeout=60 allein reicht nicht — jeder eintreffende Token
    # resettet den Socket-Idle-Timeout, d.h. ein Streaming-Modell kann
    # theoretisch 180s laufen ohne timeout auszulösen.
    _HARD_TIMEOUT = 55  # sicher unter gunicorn-Worker-Timeout (240s)
    # Dynamisch reduzieren wenn nur noch wenig vom Gesamtbudget übrig:
    # ein langsamer Token-Stream darf nicht das letzte Wall-Clock-Budget
    # verbrennen. <10s rest → AI ganz überspringen.
    effective_timeout = _HARD_TIMEOUT
    if deadline is not None:
        remaining = deadline - _time.monotonic()
        if remaining < 10:
            logger.info("AI-Extract skip: nur %.1fs Budget übrig", remaining)
            return None
        effective_timeout = max(5, min(_HARD_TIMEOUT, int(remaining * 0.5)))
    client = ai_provider_client.get_client(timeout=effective_timeout)
    if not client:
        return None

    provider, model = user.get_model_for('email_parse')
    if not provider:
        return None

    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='email_parse')

    prompt = (
        "Extract structured job data from this Indeed email. "
        "Return ONLY a single valid JSON object with these keys: "
        '"title", "company", "location", "url". '
        "If a field is unknown, use null. No prose, no markdown, only JSON.\n\n"
        f"Subject: {subject[:200]}\n\n"
        f"Body:\n{body[:2000]}"
    )

    def _do_chat_single():
        return client.chat(
            user_id=user.id,
            provider=provider,
            model=model or '',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            **fallback_kwargs,
        )

    try:
        with _futures.ThreadPoolExecutor(max_workers=1) as _ex:
            _f = _ex.submit(_do_chat_single)
            try:
                response = _f.result(timeout=effective_timeout)
            except _futures.TimeoutError:
                logger.warning("AI-Extract hard-timeout (%ss)", effective_timeout)
                return None
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


def _ai_extract_digest(
    user, subject: str, body: str, profile: PlatformProfile,
    *, deadline: float | None = None,
) -> Optional[list[dict]]:
    """AI-Fallback für Digest-Mails: erwartet JSON-Array von Job-Dicts.

    Returns list[dict] mit Keys title/company/location/url, oder None bei
    Fehler. Profile-spezifischer Hint wird in den Prompt eingebettet.
    """
    try:
        from services import ai_provider_client
    except ImportError:
        return None

    if not ai_provider_client.is_enabled():
        return None
    # Harter Wall-Clock-Timeout via ThreadPoolExecutor — gleiche Begründung
    # wie in _ai_extract(): Streaming-Modelle können requests-Socket-Timeout
    # umgehen; hier setzen wir eine absolute Obergrenze.
    _HARD_TIMEOUT = 55
    # Gleiche Deadline-Logik wie in _ai_extract.
    effective_timeout = _HARD_TIMEOUT
    if deadline is not None:
        remaining = deadline - _time.monotonic()
        if remaining < 10:
            logger.info("AI-Extract-Digest skip: nur %.1fs Budget übrig", remaining)
            return None
        effective_timeout = max(5, min(_HARD_TIMEOUT, int(remaining * 0.5)))
    client = ai_provider_client.get_client(timeout=effective_timeout)
    if not client:
        return None

    provider, model = user.get_model_for('email_parse')
    if not provider:
        return None

    fallback_kwargs = ai_provider_client.build_fallback_kwargs(user, feature='email_parse')

    prompt = (
        f"Extract ALL job postings from this {profile.source_label} digest email. "
        "Return ONLY a single valid JSON ARRAY (no wrapping object), where each "
        'element is an object with keys "title", "company", "location", "url". '
        "If a field is unknown for an item, use null. "
        "No prose, no markdown — only the JSON array.\n\n"
        f"Hinweis: {profile.ai_hint}\n\n"
        f"Subject: {subject[:200]}\n\n"
        f"Body:\n{body[:4000]}"
    )

    def _do_chat_digest():
        return client.chat(
            user_id=user.id,
            provider=provider,
            model=model or '',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            **fallback_kwargs,
        )

    try:
        with _futures.ThreadPoolExecutor(max_workers=1) as _ex:
            _f = _ex.submit(_do_chat_digest)
            try:
                response = _f.result(timeout=effective_timeout)
            except _futures.TimeoutError:
                logger.warning("AI-Extract-Digest hard-timeout (%ss)", effective_timeout)
                return None
        text = response.content[0].text if response.content else ''
    except Exception as exc:
        logger.warning("AI-Extract-Digest fehlgeschlagen: %s", exc)
        return None

    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return data


# Backward-compat alias — kept until all callers migrate to EmailJobsAdapter.
# Bestehende Imports `from services.job_sources.email_jobs import IndeedEmailAdapter`
# funktionieren weiter; Default-Profil ist `PROFILES["indeed"]`.
IndeedEmailAdapter = EmailJobsAdapter
