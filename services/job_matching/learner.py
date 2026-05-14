# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Adaptive Lern-Mechanismus für Job-Match-Scoring.

Pflegt pro User Centroids aus imported/dismissed Jobs.
Adjustiert Prefilter-Score basierend auf Cosine-Similarity.

Cold-Start: Erst ab min_samples in beiden Klassen aktiv.
"""

from __future__ import annotations
import json
import logging
import numpy as np

from services.job_matching.embedder import (
    vector_pack, vector_unpack, cosine_similarity
)
from services.job_matching.feedback import (
    FEEDBACK_REASONS, increment_reason_counts
)

logger = logging.getLogger(__name__)


def _load_profile(user_id: str):
    """Lazy-load UserLearnProfile oder None."""
    from models import UserLearnProfile
    return UserLearnProfile.query.filter_by(user_id=user_id).first()


def _load_embedding(raw_job_id: int):
    """Returns np.array oder None falls kein Embedding existiert."""
    from models import JobEmbedding
    emb = JobEmbedding.query.filter_by(raw_job_id=raw_job_id).first()
    if emb is None:
        return None
    return vector_unpack(emb.vector)


def _incremental_mean(old_centroid_blob, old_count: int, new_vec: np.ndarray) -> np.ndarray:
    """Online-Mean: c_new = (c_old × n + v) / (n+1)."""
    if old_centroid_blob is None or old_count == 0:
        return new_vec.astype(np.float32)
    if isinstance(old_centroid_blob, (bytes, bytearray)):
        old = vector_unpack(old_centroid_blob)
    else:
        old = old_centroid_blob
    return ((old * old_count + new_vec) / (old_count + 1)).astype(np.float32)


def update_centroid_for_feedback(user, match) -> None:
    """Update Centroid nach Status-Change auf dismissed/imported."""
    from database import db
    from models import UserLearnProfile

    if match.status not in ('dismissed', 'imported'):
        return

    vec = _load_embedding(match.raw_job_id)
    if vec is None:
        logger.info('No embedding for raw_job_id=%s — skipping centroid update', match.raw_job_id)
        return

    profile = _load_profile(user.id)
    if profile is None:
        profile = UserLearnProfile(user_id=user.id)
        db.session.add(profile)

    if match.status == 'imported':
        new_centroid = _incremental_mean(profile.imported_centroid, profile.samples_imported, vec)
        profile.imported_centroid = vector_pack(new_centroid)
        profile.samples_imported += 1
    else:
        new_centroid = _incremental_mean(profile.dismissed_centroid, profile.samples_dismissed, vec)
        profile.dismissed_centroid = vector_pack(new_centroid)
        profile.samples_dismissed += 1

    if match.feedback_reasons:
        try:
            reasons = json.loads(match.feedback_reasons)
            if isinstance(reasons, list):
                increment_reason_counts(profile, reasons)
        except (ValueError, TypeError):
            pass

    db.session.commit()


def compute_score_adjustment(user, raw_job_id: int, base_score: float) -> float:
    """Adjustiert base_score basierend auf User-Centroids."""
    if not user.job_learn_enabled:
        return base_score

    profile = _load_profile(user.id)
    if profile is None:
        return base_score

    min_samples = user.job_learn_min_samples or 3
    if profile.samples_imported < min_samples or profile.samples_dismissed < min_samples:
        return base_score

    if profile.imported_centroid is None or profile.dismissed_centroid is None:
        return base_score

    job_vec = _load_embedding(raw_job_id)
    if job_vec is None:
        return base_score

    imp_centroid = vector_unpack(profile.imported_centroid)
    dis_centroid = vector_unpack(profile.dismissed_centroid)

    sim_imp = cosine_similarity(job_vec, imp_centroid)
    sim_dis = cosine_similarity(job_vec, dis_centroid)

    alpha = (user.job_learn_weight_pct or 30) / 100.0
    adjusted = base_score * (1 + alpha * (sim_imp - sim_dis))
    return max(0.0, min(100.0, adjusted))


def get_learn_profile_stats(user) -> dict:
    """Stats für GET /api/jobs/learn-profile."""
    profile = _load_profile(user.id)
    if profile is None:
        return {
            'enabled': bool(user.job_learn_enabled),
            'samples_imported': 0,
            'samples_dismissed': 0,
            'active': False,
            'min_samples': user.job_learn_min_samples or 3,
            'weight_pct': user.job_learn_weight_pct or 30,
            'top_reasons': [],
        }

    min_samples = user.job_learn_min_samples or 3
    active = (
        bool(user.job_learn_enabled)
        and profile.samples_imported >= min_samples
        and profile.samples_dismissed >= min_samples
    )

    counts = {}
    if profile.reason_counts:
        try:
            counts = json.loads(profile.reason_counts)
        except (ValueError, TypeError):
            counts = {}

    top = sorted(counts.items(), key=lambda x: -x[1])[:5]
    top_reasons = [
        {'reason': k, 'label': FEEDBACK_REASONS.get(k, k), 'count': v}
        for k, v in top
    ]

    return {
        'enabled': bool(user.job_learn_enabled),
        'samples_imported': profile.samples_imported,
        'samples_dismissed': profile.samples_dismissed,
        'active': active,
        'min_samples': min_samples,
        'weight_pct': user.job_learn_weight_pct or 30,
        'top_reasons': top_reasons,
    }
