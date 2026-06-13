# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Wandelt E-Mail-Tracking-/Redirect-Links in den Original-Stellenlink um.

Hintergrund: E-Mail-Job-Quellen (StepStone, LinkedIn, Indeed) verschicken
Click-Tracking-/Redirect-Links statt der echten Stellen-URL. `raw_job.url` ist
darum oft ein hässlicher Tracker (`click.stepstone.de/f/a/…`,
`linkedin.com/comm/jobs/view/…`, `cts.indeed.com/…`). Beim Übernehmen einer
Bewerbung wollen wir aber den ECHTEN Stellenlink im `link`-Feld.

Best-effort: bei Netz-Fehler oder fremder Final-Domain bleibt der Eingabe-Link
erhalten (nie schlechter als der Tracker — der Browser-Klick funktioniert ja).
Redirect-Following passiert NUR für bekannte Tracker-Hosts und akzeptiert nur
Final-URLs auf der erwarteten Domain (SSRF-Schutz, analog
`email_jobs._resolve_indeed_tracker`).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

# Reine Tracking-Query-Parameter, die entfernt werden dürfen (lowercase).
_TRACKING_PARAMS = {
    "trackingid", "refid", "trk", "ref", "src",
    "gh_src", "recommended", "ebchash", "lipi", "licu",
}
_TRACKING_PREFIXES = ("utm_",)

_LINKEDIN_VIEW_RE = re.compile(r"/(?:comm/)?jobs/view/(\d+)")


def _strip_tracking_params(url: str) -> str:
    """Entfernt bekannte Tracking-Query-Parameter, behält die übrigen in Reihenfolge."""
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    if not parts.query:
        return url
    kept = [
        (k, v)
        for (k, v) in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
        and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)
    )


def _follow_redirect(url: str, timeout: float, accept_host_substr: str) -> str | None:
    """HEAD-Request, Redirects folgen; nur Final-URLs auf der erwarteten Domain.

    Gibt None zurück bei Netz-Fehler oder wenn die Final-Domain nicht passt
    (oder weiterhin ein Tracker-Host ist) → Caller behält den Eingabe-Link.
    """
    try:
        import requests
        r = requests.head(url, allow_redirects=True, timeout=timeout)
    except Exception:
        return None
    final = getattr(r, "url", "") or ""
    host = urlparse(final).netloc.lower()
    if accept_host_substr not in host:
        return None
    if host.startswith("click.") or host.startswith("cts.") or host.startswith("sl."):
        return None  # noch ein Tracker → nicht übernehmen
    return final


def resolve_original_url(url, *, timeout: float = 4.0):
    """Best-effort: Tracking-/Redirect-Link → Original-Stellenlink.

    Bei Fehler / unbekanntem Muster wird der Eingabewert unverändert
    zurückgegeben (auch None/leer bleiben unverändert).
    """
    if not url or not isinstance(url, str):
        return url
    u = url.strip()
    try:
        host = urlparse(u).netloc.lower()
    except Exception:
        return url

    # LinkedIn: comm/jobs/view/<id> bzw. jobs/view/<id> → kanonisch (kein Netz).
    if "linkedin.com" in host:
        m = _LINKEDIN_VIEW_RE.search(urlparse(u).path)
        if m:
            return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
        return _strip_tracking_params(u)

    # Indeed: cts-Tracker oder /rc/clk → canonical viewjob via Redirect.
    if "cts.indeed." in host or "/rc/clk" in u or "/pagead/clk" in u:
        return _follow_redirect(u, timeout, "indeed.") or url

    # StepStone: SendGrid-Click-Tracker → echter Link via Redirect.
    if "click.stepstone." in host or "sl.stepstone." in host:
        return _follow_redirect(u, timeout, "stepstone.") or url

    # Unbekannter Host: KEIN Netz-Call (SSRF), nur Tracking-Params strippen.
    return _strip_tracking_params(u)
