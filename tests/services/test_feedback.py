# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import pytest

from services.job_matching.feedback import (
    FEEDBACK_REASONS, validate_reasons, increment_reason_counts
)


def test_validate_reasons_filters_invalid():
    result = validate_reasons(['salary_too_low', 'invalid_key', 'wrong_location'])
    assert 'salary_too_low' in result
    assert 'wrong_location' in result
    assert 'invalid_key' not in result


def test_validate_reasons_empty():
    assert validate_reasons([]) == []
    assert validate_reasons(None) == []


def test_validate_reasons_limit_max_5():
    inputs = list(FEEDBACK_REASONS.keys())  # 8 valid
    result = validate_reasons(inputs)
    assert len(result) == 5


def test_validate_reasons_dedupes():
    result = validate_reasons(['salary_too_low', 'salary_too_low', 'wrong_location'])
    assert result.count('salary_too_low') == 1


def test_increment_reason_counts_first_time():
    class FakeProfile:
        reason_counts = None
    p = FakeProfile()
    increment_reason_counts(p, ['salary_too_low'])
    counts = json.loads(p.reason_counts)
    assert counts['salary_too_low'] == 1


def test_increment_reason_counts_accumulates():
    class FakeProfile:
        reason_counts = json.dumps({'salary_too_low': 3, 'wrong_location': 1})
    p = FakeProfile()
    increment_reason_counts(p, ['salary_too_low', 'missing_skills'])
    counts = json.loads(p.reason_counts)
    assert counts['salary_too_low'] == 4
    assert counts['wrong_location'] == 1
    assert counts['missing_skills'] == 1
