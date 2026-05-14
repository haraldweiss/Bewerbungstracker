# SPDX-License-Identifier: AGPL-3.0-or-later
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from services.job_matching.embedder import (
    embed_text, vector_pack, vector_unpack, cosine_similarity, embed_raw_job
)


def test_vector_pack_unpack_roundtrip():
    original = [0.1, -0.2, 0.5, 1.0, -1.0]
    blob = vector_pack(original)
    restored = vector_unpack(blob)
    np.testing.assert_array_almost_equal(restored, original, decimal=5)


def test_cosine_similarity_identical():
    a = np.array([1.0, 2.0, 3.0])
    assert cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    a = np.array([0.0, 0.0])
    b = np.array([1.0, 1.0])
    assert cosine_similarity(a, b) == 0.0


def test_embed_text_returns_packed_bytes_on_success():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {'embedding': [0.1, 0.2, 0.3] * 256}  # 768-dim
        mock_req.post.return_value = mock_resp
        result = embed_text('hello world')
        assert result is not None
        assert isinstance(result, bytes)
        vec = vector_unpack(result)
        assert vec.shape == (768,)


def test_embed_text_returns_none_on_failure():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_req.post.side_effect = Exception('connection refused')
        result = embed_text('hello')
        assert result is None


def test_embed_text_returns_none_on_http_error():
    with patch('services.job_matching.embedder.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_req.post.return_value = mock_resp
        result = embed_text('hello')
        assert result is None
