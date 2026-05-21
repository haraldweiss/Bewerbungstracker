# SPDX-License-Identifier: AGPL-3.0-or-later
import re
from services.job_sources.email_jobs import _INDEED_URL_RE


# Realistic Indeed-job-alert mail body (truncated).
# Contains BOTH a sponsored ad tracker (de.indeed.com/pagead/clk) AND a real
# cts.indeed.com/v3/ job tracker. The bug: extractor was picking up pagead/clk
# because it appears first.
INDEED_BODY = """
Hallo Harald,

Lust auf neue Stellen?
https://de.indeed.com/pagead/clk?from=jobi2a_jobmatch-de-DE_email&jrtk=5-cmh1-1-1jp2vi8ebier3806-d1072f8b0d4fcaf1&mo=r&ad=-6NYlbfk

# Cybersecurity Consultant Marine (m/w/d) bei INFODAS

[Job anzeigen](https://cts.indeed.com/v3/H4sIAAAAAAAA_32UW4urWBBG_AT/abc?xyz)

INFODAS, Köln
"""


def test_indeed_url_regex_excludes_pagead_clk():
    """pagead/clk URLs are sponsored-ad trackers — adapter must skip them."""
    matches = _INDEED_URL_RE.findall(INDEED_BODY)
    # No pagead/clk in matches
    assert not any("pagead/clk" in m for m in matches), f"pagead/clk leaked: {matches}"


def test_indeed_url_regex_keeps_cts_tracker():
    """cts.indeed.com/v3/ links are the real job trackers — must be matched."""
    matches = _INDEED_URL_RE.findall(INDEED_BODY)
    assert any("cts.indeed.com/v3/" in m for m in matches), f"cts tracker missing: {matches}"


def test_indeed_url_search_returns_real_job_link_first():
    """The first .search() hit must be the real job tracker, not pagead/clk.

    This is the actual bug: in the live mail the pagead/clk URL comes
    BEFORE the cts.indeed.com URL in the body, so the previous regex
    picked up the sponsored ad.
    """
    m = _INDEED_URL_RE.search(INDEED_BODY)
    assert m is not None
    assert "pagead/clk" not in m.group(0)
    assert "cts.indeed.com/v3/" in m.group(0)
