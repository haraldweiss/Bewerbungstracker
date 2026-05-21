# SPDX-License-Identifier: AGPL-3.0-or-later
"""URL-Truncation: real Indeed cts.indeed.com URLs are ~2300 chars long.
Previous [:1024] truncation made them unusable (404 on click).
"""
import pytest
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES, _INDEED_URL_RE


# Reduced-size but realistic representative — 1500 chars, longer than 1024.
LONG_INDEED_URL = (
    "https://cts.indeed.com/v3/H4sIAAAAAAAA_"
    + "A" * 1400  # padding to simulate a real base64 segment
    + "/Y3JESLJy08srw6A9y9d0cv41Pj7g5GLdaodosT0ZAzA"
)


def test_long_indeed_url_not_truncated_at_1024(monkeypatch):
    """An Indeed-tracker URL >1024 chars must survive the adapter intact."""
    assert len(LONG_INDEED_URL) > 1024  # sanity: this test only matters if URL is long

    # Build a minimal Indeed-style mail body that contains the long URL.
    body = (
        f"Hallo Harald,\n"
        f"Neue Stelle: Test Engineer bei TestCo\n"
        f"[Job anzeigen]({LONG_INDEED_URL})\n"
    )
    em = {
        "subject": "Test Engineer bei TestCo",
        "body": body,
        "from": "Indeed <jobs@indeed.com>",
        "date": "2026-05-21T14:00:00Z",
    }

    # Stub out the tracker resolver so the test doesn't hit the network.
    import services.job_sources.email_jobs as ej
    monkeypatch.setattr(ej, "_resolve_indeed_tracker", lambda url, timeout=4.0: None)

    adapter = EmailJobsAdapter(
        config={},
        user=None,
        platform_profile=PROFILES["indeed"],
    )
    job = adapter._parse_email(em)
    assert job is not None, "adapter dropped a valid indeed mail"
    assert job.url == LONG_INDEED_URL, (
        f"URL truncated: stored len={len(job.url)}, expected len={len(LONG_INDEED_URL)}. "
        f"End-of-stored={job.url[-50:]!r}, end-of-expected={LONG_INDEED_URL[-50:]!r}"
    )


def test_url_regex_matches_long_url():
    """Sanity: _INDEED_URL_RE captures the entire long URL in one match."""
    matches = _INDEED_URL_RE.findall(LONG_INDEED_URL + " trailing space")
    assert len(matches) == 1
    assert matches[0] == LONG_INDEED_URL, (
        f"regex broke URL at len={len(matches[0])}"
    )
