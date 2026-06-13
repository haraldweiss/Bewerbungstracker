# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für services/job_sources/url_resolver.resolve_original_url.

Wandelt E-Mail-Tracking-/Redirect-Links (StepStone SendGrid, LinkedIn comm,
Indeed cts/clk) in den Original-Stellenlink um. Best-effort: bei Netz-Fehler
oder fremder Final-Domain bleibt der Eingabe-Link erhalten (nie schlechter).
"""
import requests

from services.job_sources.url_resolver import resolve_original_url


class _Resp:
    def __init__(self, url):
        self.url = url

    def close(self):
        pass


# ── LinkedIn (reine String-Kanonisierung, kein Netz) ─────────────────────────

def test_linkedin_comm_to_canonical():
    out = resolve_original_url(
        "https://www.linkedin.com/comm/jobs/view/4416898744/?trackingId=abc%2Fdef&refId=x"
    )
    assert out == "https://www.linkedin.com/jobs/view/4416898744/"


def test_linkedin_plain_view_strips_tracking():
    out = resolve_original_url(
        "https://www.linkedin.com/jobs/view/123456/?trackingId=zzz"
    )
    assert out == "https://www.linkedin.com/jobs/view/123456/"


# ── StepStone SendGrid-Click-Tracker (Redirect folgen) ───────────────────────

def test_stepstone_click_follows_redirect(monkeypatch):
    real = "https://www.stepstone.de/stellenangebote--Senior-Dev-Berlin--12345-inline.html"
    monkeypatch.setattr(requests, "head", lambda u, **k: _Resp(real))
    out = resolve_original_url("https://click.stepstone.de/f/a/OPAQUE~~/AAA~/xxxxx")
    assert out == real


def test_stepstone_resolves_via_get_when_head_times_out(monkeypatch):
    # StepStone-SendGrid timeoutet auf HEAD, antwortet aber auf GET.
    def head_timeout(*a, **k):
        raise requests.ReadTimeout("HEAD timed out")
    real = "https://www.stepstone.de/v2/magiclink/exchange?magicLink=eyJabc"
    monkeypatch.setattr(requests, "head", head_timeout)
    monkeypatch.setattr(requests, "get", lambda u, **k: _Resp(real))
    out = resolve_original_url("https://click.stepstone.de/f/a/OPAQUE~~/AAA~/xxxxx")
    assert out == real


def test_stepstone_redirect_to_foreign_domain_falls_back(monkeypatch):
    # SSRF-Schutz: Final-URL nicht stepstone (weder HEAD noch GET) → Tracker behalten.
    monkeypatch.setattr(requests, "head", lambda u, **k: _Resp("https://evil.example.com/"))
    monkeypatch.setattr(requests, "get", lambda u, **k: _Resp("https://evil.example.com/"))
    tracker = "https://click.stepstone.de/f/a/OPAQUE~~/AAA~/xxxxx"
    assert resolve_original_url(tracker) == tracker


def test_network_error_falls_back_to_input(monkeypatch):
    def boom(*a, **k):
        raise requests.RequestException("nope")
    monkeypatch.setattr(requests, "head", boom)
    monkeypatch.setattr(requests, "get", boom)
    tracker = "https://click.stepstone.de/f/a/OPAQUE~~/AAA~/xxxxx"
    assert resolve_original_url(tracker) == tracker


# ── Indeed cts-Tracker (Redirect folgen, Domain-Check) ───────────────────────

def test_indeed_cts_follows_redirect(monkeypatch):
    real = "https://de.indeed.com/viewjob?jk=abc123"
    monkeypatch.setattr(requests, "head", lambda u, **k: _Resp(real))
    out = resolve_original_url("https://cts.indeed.com/v3/abc")
    assert out == real


# ── Generisch / unbekannte Hosts (kein Netz, nur Tracking-Params strippen) ───

def test_generic_url_strips_utm_keeps_essential_params():
    out = resolve_original_url(
        "https://jobs.example.com/view?jk=42&utm_source=email&utm_campaign=x"
    )
    assert out == "https://jobs.example.com/view?jk=42"


def test_plain_url_unchanged():
    u = "https://www.stepstone.de/stellenangebote--Foo--999-inline.html"
    assert resolve_original_url(u) == u


def test_none_and_empty_passthrough():
    assert resolve_original_url(None) is None
    assert resolve_original_url("") == ""
