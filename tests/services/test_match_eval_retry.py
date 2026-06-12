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


from services.job_matching.claude_utils import (
    _retry_backoff_hours, _result_is_content_failure,
    MATCH_MAX_EVAL_ATTEMPTS, MATCH_OLLAMA_FALLBACK_MODEL,
)
from services.job_matching.claude_matcher import MatchResult


def test_backoff_curve():
    assert _retry_backoff_hours(1) == 1
    assert _retry_backoff_hours(2) == 2
    assert _retry_backoff_hours(3) == 4
    assert _retry_backoff_hours(4) == 8
    assert _retry_backoff_hours(5) == 12   # gekappt


def test_content_failure_detection():
    assert _result_is_content_failure(_parse_match_response("xx", 1, 1)) is True
    ok = MatchResult(score=42, reasoning="ok", missing_skills=[], tokens_in=1, tokens_out=1)
    assert _result_is_content_failure(ok) is False


def test_constants_defaults():
    assert MATCH_MAX_EVAL_ATTEMPTS == 5
    assert MATCH_OLLAMA_FALLBACK_MODEL == "gemma4:12b"
