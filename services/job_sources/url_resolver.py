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


# Browser-UA: manche Click-Tracker (StepStone SendGrid) antworten sonst nicht.
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    )
}


def _follow_redirect(url: str, timeout: float, accept_host_substr: str) -> str | None:
    """Folgt Redirects; nur Final-URLs auf der erwarteten Domain (SSRF-Schutz).

    Erst HEAD (billig, z.B. Indeed), dann GET als Fallback — StepStone-SendGrid
    timeoutet auf HEAD, antwortet aber auf GET. Gibt None zurück bei Netz-Fehler
    oder wenn die Final-Domain nicht passt (oder weiter ein Tracker-Host ist) →
    Caller behält den Eingabe-Link.
    """
    import requests
    for method in ("head", "get"):
        try:
            fn = getattr(requests, method)
            extra = {"stream": True} if method == "get" else {}
            r = fn(url, allow_redirects=True, timeout=timeout, headers=_UA, **extra)
            final = getattr(r, "url", "") or ""
            if method == "get":
                try:
                    r.close()
                except Exception:
                    pass
        except Exception:
            continue
        host = urlparse(final).netloc.lower()
        if (accept_host_substr in host
                and not host.startswith(("click.", "cts.", "sl."))):
            return final
        # Final-URL ungültig (fremde Domain / noch Tracker) → nächste Methode (GET).
    return None


def _unwrap_stepstone_magiclink(url: str) -> str:
    """StepStone-Magic-Link → öffentliche Anzeigen-URL aus dem `returnUrl`-Param.

    `www.stepstone.de/v2/magiclink/exchange?…&returnUrl=%2Fstellenangebote--…`
    trägt den echten öffentlichen Pfad. Tracking-Query (CID/lang/…) wird
    verworfen. Ohne `returnUrl` bleibt der Magic-Link erhalten (besser als nichts).
    """
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    if "stepstone." not in parts.netloc.lower() or "magiclink" not in parts.path.lower():
        return url
    ret = dict(parse_qsl(parts.query)).get("returnUrl")
    if not ret:
        return url
    path = urlsplit(ret).path or ret
    if not path.startswith("/"):
        return url
    return urlunsplit(("https", "www.stepstone.de", path, "", ""))


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

    # StepStone: Magic-Link direkt entpacken; Click-Tracker erst folgen (HEAD→GET),
    # dann den resultierenden Magic-Link auf die öffentliche Anzeigen-URL entpacken.
    if "stepstone." in host:
        if "magiclink" in urlparse(u).path.lower():
            return _unwrap_stepstone_magiclink(u)
        if "click.stepstone." in host or "sl.stepstone." in host:
            resolved = _follow_redirect(u, timeout, "stepstone.")
            return _unwrap_stepstone_magiclink(resolved) if resolved else url
        return _strip_tracking_params(u)

    # Unbekannter Host: KEIN Netz-Call (SSRF), nur Tracking-Params strippen.
    return _strip_tracking_params(u)
