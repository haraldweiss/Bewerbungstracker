# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""StepStone-„Du hast gute Chancen"-Empfehlungs-Mails: Marketing-Header dürfen
nicht als Job-Titel durchrutschen (Bug: 'Erhöhe deine Chancen…' wurde Titel,
der echte Jobtitel wurde Firma).
"""
from services.job_sources.email_jobs import (
    EmailJobsAdapter, PROFILES, _DB_PROFILE_HARD_BLACKLISTS,
)


def test_stepstone_hard_blacklist_matches_marketing_headers():
    bl = _DB_PROFILE_HARD_BLACKLISTS["stepstone"]
    assert bl.search("Erhöhe deine Chancen – Du passt auch gut zu diesen Jobs")
    assert bl.search("Passt hervorragend")
    assert bl.search("Neues Jobangebot basierend auf deiner letzten Suche")
    assert bl.search("Du hast gute Chancen auf ein Interview für diesen Job")
    # Echte Jobtitel dürfen NICHT gefiltert werden:
    assert not bl.search("SOC Security Analyst (m/w/d)")
    assert not bl.search("Senior Cyber Security Analyst (m/w/d)")
    assert not bl.search("Senior Systemintegrator für KI-Anwendungen")


def test_ai_digest_filters_marketing_header_titles(app, user_factory, monkeypatch):
    """Der AI-Pfad muss die hard_title_blacklist anwenden (tat er vorher nicht)."""
    with app.app_context():
        user = user_factory()
        # Profil mit StepStone-Blacklist (wie get_profile('stepstone') es liefert,
        # ohne DB-Row: hardcoded Blacklist reicht für diesen Test).
        from services.job_sources.email_jobs import PlatformProfile
        import re
        _any = re.compile(r"(?P<x>.+)")
        profile = PlatformProfile(
            name="stepstone", source_label="StepStone",
            from_filter="from:stepstone.de",
            from_whitelist=(r"stepstone\.de$",),
            url_pattern=re.compile(r"https?://[^\s]+stepstone[^\s]*"),
            subject_patterns=("job",),
            body_title_re=_any, body_company_re=_any, body_location_re=_any,
            hard_title_blacklist_re=_DB_PROFILE_HARD_BLACKLISTS["stepstone"],
        )
        adapter = EmailJobsAdapter(config={}, user=user, platform_profile=profile)

        import services.job_sources.email_jobs as ej
        monkeypatch.setattr(ej, "_ai_extract_digest", lambda *a, **k: [
            {"title": "Erhöhe deine Chancen – Du passt auch gut zu diesen Jobs",
             "company": "SOC Security Analyst (m/w/d)", "location": None,
             "url": "https://click.stepstone.de/f/a/AAA~~/x"},
            {"title": "SOC Security Analyst (m/w/d)", "company": "Amprion GmbH",
             "location": "Pulheim bei Köln",
             "url": "https://click.stepstone.de/f/a/BBB~~/y"},
        ])
        em = {"subject": "Du hast gute Chancen", "body": "x", "from": "info@jobagent.stepstone.de"}
        jobs = adapter._ai_fallback_digest(em)
        titles = [j.title for j in jobs]
        assert "SOC Security Analyst (m/w/d)" in titles
        assert not any("Erhöhe deine Chancen" in t for t in titles)
