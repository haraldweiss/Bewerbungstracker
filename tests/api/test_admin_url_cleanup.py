# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""Integration-Tests fuer URL-Cleanup-Admin-Endpoints (Task 5).

Endpoints:
  - GET  /api/admin/url-cleanup-candidates
  - POST /api/admin/url-cleanup/<id>/delete
  - POST /api/admin/url-cleanup/<id>/keep
  - POST /api/admin/url-cleanup/bulk-delete
"""
import pytest

from auth_service import AuthService
from database import db
from models import JobEmbedding, JobMatch, JobSource, RawJob


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def admin_header(user_factory):
    """Admin-User + JWT-Header."""
    admin = user_factory(email="admin@cleanup-test.de", is_admin=True)
    token = AuthService.create_access_token(admin.id)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }, admin


@pytest.fixture
def source(app):
    """RawJob.source_id ist NOT NULL — Tests brauchen eine JobSource."""
    src = JobSource(
        name="UrlCleanupTest",
        type="rss",
        enabled=True,
        crawl_interval_min=60,
    )
    src.config = {"url": "https://example.com/feed.xml"}
    db.session.add(src)
    db.session.commit()
    return src


# ── Tests: list_url_cleanup_candidates ────────────────────────────────────


def test_list_candidates_returns_marked_only(client, admin_header, source):
    """Nur RawJobs mit crawl_status='marked_for_deletion' kommen zurueck."""
    headers, _ = admin_header
    rj_marked = RawJob(
        source_id=source.id, external_id='m1',
        title='Marked Job', url='https://x.com/1',
        crawl_status='marked_for_deletion',
        url_check_status='404', url_check_failures=1,
    )
    rj_active = RawJob(
        source_id=source.id, external_id='a1',
        title='Active Job', url='https://x.com/2',
        crawl_status='raw',
    )
    db.session.add_all([rj_marked, rj_active])
    db.session.commit()

    resp = client.get('/api/admin/url-cleanup-candidates', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    ids = [c['id'] for c in data['candidates']]
    assert rj_marked.id in ids
    assert rj_active.id not in ids

    # Felder-Shape pruefen
    entry = next(c for c in data['candidates'] if c['id'] == rj_marked.id)
    assert entry['url'] == 'https://x.com/1'
    assert entry['url_check_status'] == '404'
    assert entry['url_check_failures'] == 1
    assert entry['source_id'] == source.id
    assert entry['source_name'] == 'UrlCleanupTest'
    assert entry['source_type'] == 'rss'


def test_list_candidates_empty(client, admin_header, source):
    """Wenn keine Kandidaten vorhanden, leere Liste statt 404."""
    headers, _ = admin_header
    resp = client.get('/api/admin/url-cleanup-candidates', headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == {'candidates': []}


# ── Tests: delete_url_cleanup_candidate ───────────────────────────────────


def test_delete_candidate_removes_raw_and_matches(
    client, admin_header, source, user_factory
):
    """Delete cascades: RawJob + JobMatch + JobEmbedding sind weg."""
    headers, _ = admin_header
    other_user = user_factory(email='matcher@test.de')

    rj = RawJob(
        source_id=source.id, external_id='del1',
        title='To Delete', url='https://x.com/del',
        crawl_status='marked_for_deletion', url_check_status='404',
    )
    db.session.add(rj)
    db.session.commit()
    rj_id = rj.id

    jm = JobMatch(
        user_id=other_user.id, raw_job_id=rj_id, status='dismissed',
    )
    emb = JobEmbedding(raw_job_id=rj_id, vector=b'\x00' * 16)
    db.session.add_all([jm, emb])
    db.session.commit()

    resp = client.post(
        f'/api/admin/url-cleanup/{rj_id}/delete',
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['deleted_raw_job_id'] == rj_id

    assert db.session.get(RawJob, rj_id) is None
    assert JobMatch.query.filter_by(raw_job_id=rj_id).count() == 0
    assert JobEmbedding.query.filter_by(raw_job_id=rj_id).count() == 0


def test_delete_rejects_non_marked(client, admin_header, source):
    """RawJob mit crawl_status='raw' darf nicht geloescht werden -> 400."""
    headers, _ = admin_header
    rj = RawJob(
        source_id=source.id, external_id='nope',
        title='Active', url='https://x.com/nope',
        crawl_status='raw',
    )
    db.session.add(rj)
    db.session.commit()
    resp = client.post(
        f'/api/admin/url-cleanup/{rj.id}/delete',
        headers=headers,
    )
    assert resp.status_code == 400
    # RawJob immer noch da
    assert db.session.get(RawJob, rj.id) is not None


def test_delete_unknown_id_returns_404(client, admin_header):
    headers, _ = admin_header
    resp = client.post(
        '/api/admin/url-cleanup/999999/delete',
        headers=headers,
    )
    assert resp.status_code == 404


# ── Tests: keep_url_cleanup_candidate ─────────────────────────────────────


def test_keep_resets_failures(client, admin_header, source):
    """Keep setzt crawl_status='raw' und url_check_failures=0."""
    headers, _ = admin_header
    rj = RawJob(
        source_id=source.id, external_id='keep1',
        title='Keep Me', url='https://x.com/keep',
        crawl_status='marked_for_deletion',
        url_check_failures=3, url_check_status='timeout',
    )
    db.session.add(rj)
    db.session.commit()
    rj_id = rj.id

    resp = client.post(
        f'/api/admin/url-cleanup/{rj_id}/keep',
        headers=headers,
    )
    assert resp.status_code == 200
    rj_after = db.session.get(RawJob, rj_id)
    assert rj_after.crawl_status == 'raw'
    assert rj_after.url_check_failures == 0
    assert rj_after.url_check_status is None


def test_keep_unknown_id_returns_404(client, admin_header):
    headers, _ = admin_header
    resp = client.post(
        '/api/admin/url-cleanup/999999/keep',
        headers=headers,
    )
    assert resp.status_code == 404


# ── Tests: bulk_delete_url_cleanup ────────────────────────────────────────


def test_bulk_delete_only_processes_marked(client, admin_header, source):
    """Bulk-Delete loescht nur marked_for_deletion-IDs, ignoriert aktive."""
    headers, _ = admin_header
    marked = RawJob(
        source_id=source.id, external_id='bk1',
        title='M', url='https://x.com/bk1',
        crawl_status='marked_for_deletion',
    )
    active = RawJob(
        source_id=source.id, external_id='bk2',
        title='A', url='https://x.com/bk2',
        crawl_status='raw',
    )
    db.session.add_all([marked, active])
    db.session.commit()
    marked_id = marked.id
    active_id = active.id

    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete',
        headers=headers,
        json={'ids': [marked_id, active_id]},
    )
    assert resp.status_code == 200
    assert resp.get_json()['deleted'] == 1
    assert db.session.get(RawJob, marked_id) is None
    assert db.session.get(RawJob, active_id) is not None


def test_bulk_delete_empty_ids(client, admin_header):
    headers, _ = admin_header
    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete',
        headers=headers,
        json={'ids': []},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True, 'deleted': 0}


def test_bulk_delete_validates_payload(client, admin_header):
    """Nicht-Listen oder Listen mit Non-Ints -> 400."""
    headers, _ = admin_header
    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete',
        headers=headers,
        json={'ids': 'oops'},
    )
    assert resp.status_code == 400

    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete',
        headers=headers,
        json={'ids': [1, 'two', 3]},
    )
    assert resp.status_code == 400


def test_bulk_delete_cascades_embeddings_and_matches(
    client, admin_header, source, user_factory
):
    """Bulk-Delete cascadet JobMatch + JobEmbedding genau wie Single-Delete."""
    headers, _ = admin_header
    u = user_factory(email='bulk-matcher@test.de')

    rjs = []
    for i in range(3):
        rj = RawJob(
            source_id=source.id, external_id=f'bulk{i}',
            title=f'B{i}', url=f'https://x.com/bulk{i}',
            crawl_status='marked_for_deletion',
        )
        db.session.add(rj)
        rjs.append(rj)
    db.session.commit()
    rj_ids = [r.id for r in rjs]

    # Eine Match + Embedding pro RawJob
    for rid in rj_ids:
        db.session.add(JobMatch(user_id=u.id, raw_job_id=rid, status='new'))
        db.session.add(JobEmbedding(raw_job_id=rid, vector=b'\x00' * 16))
    db.session.commit()

    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete',
        headers=headers,
        json={'ids': rj_ids},
    )
    assert resp.status_code == 200
    assert resp.get_json()['deleted'] == 3

    assert RawJob.query.filter(RawJob.id.in_(rj_ids)).count() == 0
    assert JobMatch.query.filter(JobMatch.raw_job_id.in_(rj_ids)).count() == 0
    assert JobEmbedding.query.filter(
        JobEmbedding.raw_job_id.in_(rj_ids)
    ).count() == 0


# ── Tests: Auth ───────────────────────────────────────────────────────────


def test_non_admin_user_gets_403(client, auth_headers, source):
    """Normaler User (kein is_admin) bekommt 403 auf alle Endpoints."""
    headers, _ = auth_headers

    resp = client.get('/api/admin/url-cleanup-candidates', headers=headers)
    assert resp.status_code == 403

    rj = RawJob(
        source_id=source.id, external_id='auth1',
        title='Z', url='https://x.com/auth',
        crawl_status='marked_for_deletion',
    )
    db.session.add(rj)
    db.session.commit()

    resp = client.post(
        f'/api/admin/url-cleanup/{rj.id}/delete', headers=headers,
    )
    assert resp.status_code == 403

    resp = client.post(
        f'/api/admin/url-cleanup/{rj.id}/keep', headers=headers,
    )
    assert resp.status_code == 403

    resp = client.post(
        '/api/admin/url-cleanup/bulk-delete', headers=headers,
        json={'ids': [rj.id]},
    )
    assert resp.status_code == 403


def test_no_token_returns_401(client):
    """Ohne Auth-Header -> 401."""
    resp = client.get('/api/admin/url-cleanup-candidates')
    assert resp.status_code == 401
