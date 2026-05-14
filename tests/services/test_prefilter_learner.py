# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from unittest.mock import patch, MagicMock

from services.job_matching.prefilter import score_job, PrefilterContext
from services.job_matching.cv_tokenizer import CVTokens


def _ctx():
    return PrefilterContext(language_filter=['de', 'en'], region_filter=None)


def _cv():
    return CVTokens(skills={'python'}, titles={'developer'}, freetext={'agile'})


def test_score_job_without_user_returns_base():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    score = score_job(_cv(), job, _ctx())
    assert score > 0


def test_score_job_with_user_calls_learner():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    user = MagicMock()
    user.job_learn_enabled = True
    with patch('services.job_matching.prefilter.compute_score_adjustment') as mock_adj:
        mock_adj.return_value = 75.0
        score = score_job(_cv(), job, _ctx(), user=user, raw_job_id=1)
        mock_adj.assert_called_once()
        assert score == 75.0


def test_score_job_with_user_none_skips_learner():
    job = {'title': 'Python Developer', 'description': 'agile team', 'location': '', 'id': 1}
    with patch('services.job_matching.prefilter.compute_score_adjustment') as mock_adj:
        score_job(_cv(), job, _ctx(), user=None, raw_job_id=1)
        mock_adj.assert_not_called()
