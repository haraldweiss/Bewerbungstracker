# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""E2E-Test: 3 imports + 3 dismisses mit Feedback → ähnlicher Job zu imported
scoret höher, ähnlicher Job zu dismissed scoret niedriger.

Durchläuft die REALEN API-Pfade:
- POST /api/jobs/matches/{id}/import  → status='imported' + Centroid-Update
- PATCH /api/jobs/matches/{id}        → status='dismissed' + feedback_reasons
- GET  /api/jobs/learn-profile        → Stats-Verifikation

Anschließend wird `compute_score_adjustment` direkt aufgerufen um zu prüfen,
dass das gelernte Profil die erwartete Richtung (Boost vs. Penalty) liefert.
"""

import numpy as np
import pytest

from database import db
from models import RawJob, JobMatch, JobSource, JobEmbedding, User
from services.job_matching.embedder import vector_pack
from services.job_matching.learner import compute_score_adjustment


def _make_job_with_embedding(source_id: int, ext_id: str, title: str, vec: np.ndarray) -> RawJob:
    """RawJob + zugehöriges JobEmbedding mit gegebenem Vektor anlegen."""
    raw = RawJob(
        source_id=source_id,
        external_id=ext_id,
        title=title,
        company='ACME',
        url=f'https://example.com/jobs/{ext_id}',
        description=title,
        crawl_status='matched',
    )
    db.session.add(raw)
    db.session.flush()
    emb = JobEmbedding(raw_job_id=raw.id, vector=vector_pack(vec))
    db.session.add(emb)
    db.session.commit()
    return raw


def test_e2e_learning_adjusts_score(client, auth_headers):
    """3 imports (Vektor A) + 3 dismisses (Vektor B) → ähnlicher Job zu A
    scoret höher als base, ähnlicher Job zu B scoret niedriger.
    """
    headers, user = auth_headers

    source = JobSource(user_id=None, name='E2E-Source', type='rss',
                       config={'url': 'https://example.com/feed.xml'},
                       enabled=True)
    db.session.add(source)
    db.session.commit()

    # --- 3 imports: orthogonaler Vektor A = [1,0,0,...] ---
    imp_vec = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    for i in range(3):
        raw = _make_job_with_embedding(source.id, f'imp-{i}', f'Imported Job {i}', imp_vec)
        m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
        db.session.add(m)
        db.session.commit()
        # Echter Import-Pfad: erzeugt Application + setzt status='imported' +
        # triggert update_centroid_for_feedback im Endpoint.
        resp = client.post(f'/api/jobs/matches/{m.id}/import', headers=headers)
        assert resp.status_code == 201, f'imp-{i} failed: {resp.get_json()}'

    # --- 3 dismisses: orthogonaler Vektor B = [0,1,0,...] mit Feedback-Reason ---
    dis_vec = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    for i in range(3):
        raw = _make_job_with_embedding(source.id, f'dis-{i}', f'Dismissed Job {i}', dis_vec)
        m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new')
        db.session.add(m)
        db.session.commit()
        resp = client.patch(
            f'/api/jobs/matches/{m.id}',
            json={'status': 'dismissed', 'feedback_reasons': ['wrong_industry']},
            headers=headers,
        )
        assert resp.status_code == 200, f'dis-{i} failed: {resp.get_json()}'

    # --- learn-profile via API verifizieren ---
    resp = client.get('/api/jobs/learn-profile', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['samples_imported'] == 3, f'expected 3 imports, got {data}'
    assert data['samples_dismissed'] == 3, f'expected 3 dismisses, got {data}'
    assert data['active'] is True, f'profile should be active after 3+3, got {data}'
    assert any(r['reason'] == 'wrong_industry' for r in data['top_reasons']), (
        f'wrong_industry should appear in top_reasons, got {data["top_reasons"]}'
    )

    # --- Score-Adjustment richtungsprüfen ---
    fresh_user = User.query.get(user.id)
    sim_imp_job = _make_job_with_embedding(source.id, 'sim-imp', 'Similar to imported', imp_vec)
    sim_dis_job = _make_job_with_embedding(source.id, 'sim-dis', 'Similar to dismissed', dis_vec)

    base = 50.0
    adj_imp = compute_score_adjustment(fresh_user, sim_imp_job.id, base_score=base)
    adj_dis = compute_score_adjustment(fresh_user, sim_dis_job.id, base_score=base)

    assert adj_imp > base, f'expected boost above {base}, got {adj_imp}'
    assert adj_dis < base, f'expected penalty below {base}, got {adj_dis}'
    # Sanity: imported-Boost und dismissed-Penalty sollten symmetrisch um base liegen,
    # da die Vektoren orthogonal sind und sim_imp/sim_dis je zur korrekten Klasse identisch.
    assert adj_imp > adj_dis, f'imported-adjusted ({adj_imp}) must beat dismissed-adjusted ({adj_dis})'
