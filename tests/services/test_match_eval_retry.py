# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from services.job_matching.claude_utils import _parse_match_response


def test_parse_invalid_json_sets_failed_flag():
    r = _parse_match_response("not json at all", 100, 20)
    assert r.failed is True
    assert r.score == 0


def test_parse_valid_score_zero_is_not_failed():
    r = _parse_match_response('{"score": 0, "reasoning": "kein Fit", "missing_skills": []}', 100, 20)
    assert r.failed is False
    assert r.score == 0
