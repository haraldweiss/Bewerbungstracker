# SPDX-License-Identifier: AGPL-3.0-or-later
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from services.job_matching.embedder import vector_pack
from services.job_matching.learner import (
    _incremental_mean, compute_score_adjustment, get_learn_profile_stats
)


def test_incremental_mean_first_sample():
    new_centroid = _incremental_mean(None, 0, np.array([1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(new_centroid, [1.0, 2.0, 3.0])


def test_incremental_mean_add_sample():
    old = np.array([1.0, 2.0, 3.0])
    new = _incremental_mean(old, 2, np.array([3.0, 4.0, 5.0]))
    np.testing.assert_array_almost_equal(new, [5/3, 8/3, 11/3])


def test_compute_score_adjustment_disabled_user():
    user = MagicMock()
    user.job_learn_enabled = False
    result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
    assert result == 50.0


def test_compute_score_adjustment_cold_start():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30
    user.id = 'u1'
    with patch('services.job_matching.learner._load_profile') as mock_lp:
        profile = MagicMock()
        profile.samples_imported = 2
        profile.samples_dismissed = 5
        mock_lp.return_value = profile
        result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
        assert result == 50.0


def test_compute_score_adjustment_no_embedding():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30
    user.id = 'u1'
    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack([1.0] * 768)
        profile.dismissed_centroid = vector_pack([0.0] * 768)
        mock_lp.return_value = profile
        mock_le.return_value = None
        result = compute_score_adjustment(user, raw_job_id=99, base_score=50.0)
        assert result == 50.0


def test_compute_score_adjustment_applies_boost():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 50
    user.id = 'u1'

    imported_vec = np.ones(768, dtype=np.float32)
    dismissed_vec = -np.ones(768, dtype=np.float32)
    job_vec = np.ones(768, dtype=np.float32)

    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack(imported_vec)
        profile.dismissed_centroid = vector_pack(dismissed_vec)
        mock_lp.return_value = profile
        mock_le.return_value = job_vec

        result = compute_score_adjustment(user, raw_job_id=1, base_score=50.0)
        # sim_imp=1, sim_dis=-1 -> 50 x (1 + 0.5 x (1 - (-1))) = 100, clamped to 100
        assert result == pytest.approx(100.0)


def test_compute_score_adjustment_clamps_to_100():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 1
    user.job_learn_weight_pct = 100
    user.id = 'u1'
    imported_vec = np.ones(768, dtype=np.float32)
    dismissed_vec = -np.ones(768, dtype=np.float32)
    job_vec = np.ones(768, dtype=np.float32)
    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 5
        profile.samples_dismissed = 5
        profile.imported_centroid = vector_pack(imported_vec)
        profile.dismissed_centroid = vector_pack(dismissed_vec)
        mock_lp.return_value = profile
        mock_le.return_value = job_vec
        result = compute_score_adjustment(user, raw_job_id=1, base_score=80.0)
        assert result <= 100.0
        assert result >= 0.0


def test_compute_score_adjustment_dismissed_imbalance_is_bounded():
    user = MagicMock()
    user.job_learn_enabled = True
    user.job_learn_min_samples = 3
    user.job_learn_weight_pct = 30
    user.id = 'u1'

    imported_vec = np.ones(768, dtype=np.float32)
    dismissed_vec = np.ones(768, dtype=np.float32)
    job_vec = np.ones(768, dtype=np.float32)

    with patch('services.job_matching.learner._load_profile') as mock_lp, \
         patch('services.job_matching.learner._load_embedding') as mock_le:
        profile = MagicMock()
        profile.samples_imported = 10
        profile.samples_dismissed = 1000
        profile.imported_centroid = vector_pack(imported_vec)
        profile.dismissed_centroid = vector_pack(dismissed_vec)
        mock_lp.return_value = profile
        mock_le.return_value = job_vec

        adjusted = compute_score_adjustment(user, raw_job_id=123, base_score=50.0)

    assert adjusted > 50.0
    assert adjusted <= 65.0
