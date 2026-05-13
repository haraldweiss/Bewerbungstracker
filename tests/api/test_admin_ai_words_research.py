# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für /api/admin/ai-words-research/* Endpoints."""
import pytest
from datetime import datetime
from models import AIWordsResearchLog
from database import db


def test_get_research_history_requires_auth(client):
    """Unauthenticated users get 401."""
    r = client.get('/api/admin/ai-words-research/history')
    assert r.status_code == 401


def test_get_research_history_requires_admin(client, auth_header, user_factory):
    """Non-admin authenticated users get 403."""
    # auth_header creates a regular (non-admin) user
    headers, _ = auth_header
    r = client.get('/api/admin/ai-words-research/history', headers=headers)
    assert r.status_code == 403
    assert 'Admin access required' in r.get_json()['error']


def test_get_research_history_admin_returns_empty_list(client, auth_header, db_session):
    """Admin user gets empty list when no logs exist."""
    headers, user = auth_header
    # Make user an admin
    user.is_admin = True
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/history', headers=headers)
    assert r.status_code == 200
    assert r.get_json()['research_history'] == []


def test_get_research_history_returns_logs_newest_first(client, auth_header, db_session):
    """Logs returned in reverse chronological order (newest first)."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    # Create test logs with different timestamps
    log1 = AIWordsResearchLog(
        found_total=50,
        new_count=5,
        new_words=['word1', 'word2'],
        sources_checked={'arbeits-abc': True},
        timestamp=datetime(2026, 5, 10, 12, 0, 0)
    )
    log2 = AIWordsResearchLog(
        found_total=48,
        new_count=2,
        new_words=['word3'],
        sources_checked={'arbeits-abc': True},
        timestamp=datetime(2026, 5, 12, 12, 0, 0)
    )
    db_session.add_all([log1, log2])
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/history', headers=headers)
    assert r.status_code == 200
    history = r.get_json()['research_history']
    assert len(history) == 2
    assert history[0]['id'] == log2.id  # Newest first
    assert history[1]['id'] == log1.id


def test_get_research_history_limits_to_10_results(client, auth_header, db_session):
    """History endpoint returns maximum 10 most recent logs."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    # Create 15 logs
    for i in range(15):
        log = AIWordsResearchLog(
            found_total=50 + i,
            new_count=i,
            new_words=[f'word{i}'],
            sources_checked={'test': True},
            timestamp=datetime(2026, 5, 1 + i, 12, 0, 0)
        )
        db_session.add(log)
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/history', headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()['research_history']) == 10


def test_get_research_history_includes_all_fields(client, auth_header, db_session):
    """Response includes all research log fields."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    log = AIWordsResearchLog(
        found_total=42,
        new_count=3,
        new_words=['foo', 'bar', 'baz'],
        sources_checked={'source1': True, 'source2': False},
        error_message=None,
        timestamp=datetime(2026, 5, 13, 10, 30, 0)
    )
    db_session.add(log)
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/history', headers=headers)
    assert r.status_code == 200
    logs = r.get_json()['research_history']
    assert len(logs) == 1
    log_data = logs[0]
    assert log_data['id'] == log.id
    assert log_data['found_total'] == 42
    assert log_data['new_count'] == 3
    assert log_data['new_words'] == ['foo', 'bar', 'baz']
    assert log_data['sources_checked'] == {'source1': True, 'source2': False}
    assert log_data['error_message'] is None


def test_get_latest_research_requires_auth(client):
    """Unauthenticated users get 401."""
    r = client.get('/api/admin/ai-words-research/latest')
    assert r.status_code == 401


def test_get_latest_research_requires_admin(client, auth_header):
    """Non-admin authenticated users get 403."""
    headers, _ = auth_header
    r = client.get('/api/admin/ai-words-research/latest', headers=headers)
    assert r.status_code == 403


def test_get_latest_research_returns_none_when_empty(client, auth_header, db_session):
    """Latest endpoint returns None when no logs exist."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/latest', headers=headers)
    assert r.status_code == 200
    assert r.get_json()['research_run'] is None


def test_get_latest_research_returns_most_recent(client, auth_header, db_session):
    """Latest endpoint returns single most recent log."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    log_old = AIWordsResearchLog(
        found_total=40,
        new_count=1,
        new_words=['old'],
        sources_checked={'test': True},
        timestamp=datetime(2026, 5, 1, 12, 0, 0)
    )
    log_new = AIWordsResearchLog(
        found_total=50,
        new_count=5,
        new_words=['new1', 'new2'],
        sources_checked={'test': True},
        timestamp=datetime(2026, 5, 13, 10, 0, 0)
    )
    db_session.add_all([log_old, log_new])
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/latest', headers=headers)
    assert r.status_code == 200
    run = r.get_json()['research_run']
    assert run['id'] == log_new.id  # Most recent
    assert run['found_total'] == 50
    assert run['new_count'] == 5


def test_get_latest_research_with_error_message(client, auth_header, db_session):
    """Latest endpoint includes error_message if research failed."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    log = AIWordsResearchLog(
        found_total=0,
        new_count=0,
        sources_checked={'test': True},
        error_message='Connection timeout after 30s'
    )
    db_session.add(log)
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/latest', headers=headers)
    assert r.status_code == 200
    run = r.get_json()['research_run']
    assert run['error_message'] == 'Connection timeout after 30s'
    assert run['found_total'] == 0
    assert run['new_count'] == 0


def test_get_latest_research_with_null_new_words(client, auth_header, db_session):
    """Latest endpoint handles null new_words gracefully."""
    headers, user = auth_header
    user.is_admin = True
    db_session.commit()

    log = AIWordsResearchLog(
        found_total=25,
        new_count=0,
        new_words=None,  # No new words
        sources_checked={'test': True}
    )
    db_session.add(log)
    db_session.commit()

    r = client.get('/api/admin/ai-words-research/latest', headers=headers)
    assert r.status_code == 200
    run = r.get_json()['research_run']
    assert run['new_words'] == []  # Returns empty list instead of null
    assert run['found_total'] == 25
