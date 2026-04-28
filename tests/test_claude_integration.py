"""
Tests for Claude API Integration
"""

import pytest
from models import Email, ApiCall
from database import db
from datetime import datetime


# auth_token + auth_headers kommen aus tests/conftest.py


@pytest.fixture
def user_email(app, auth_headers):
    """Create test email for the authenticated user."""
    _, user = auth_headers
    email = Email(
        user_id=user.id,
        subject='Interview Request from Google',
        from_address='recruiter@google.com',
        body='We would like to invite you for an interview...',
        timestamp=datetime.utcnow()
    )
    db.session.add(email)
    db.session.commit()
    db.session.refresh(email)
    return email


def test_analyze_email(client, user_email, auth_token):
    """Test email analysis endpoint"""
    response = client.post(
        '/api/claude/analyze-email',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert 'analysis' in data
    assert 'model_used' in data
    assert 'cost' in data
    assert data['email_id'] == user_email.id
    assert data['model_used'] == 'claude-haiku-3-5'


def test_analyze_email_missing_email_id(client, auth_token):
    """Test email analysis without email_id"""
    response = client.post(
        '/api/claude/analyze-email',
        json={},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_analyze_email_not_found(client, auth_token):
    """Test email analysis with non-existent email"""
    response = client.post(
        '/api/claude/analyze-email',
        json={'email_id': 'nonexistent-id'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data


def test_match_application(client, user_email, auth_token):
    """Test application matching endpoint"""
    response = client.post(
        '/api/claude/match-application',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert 'matched_application_id' in data
    assert 'confidence' in data
    assert 'model_used' in data
    assert 'cost' in data
    assert data['email_id'] == user_email.id


def test_match_application_missing_email_id(client, auth_token):
    """Test matching without email_id"""
    response = client.post(
        '/api/claude/match-application',
        json={},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 400


def test_match_application_not_found(client, auth_token):
    """Test matching with non-existent email"""
    response = client.post(
        '/api/claude/match-application',
        json={'email_id': 'nonexistent-id'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 404


def test_monthly_usage_empty(client, auth_token):
    """Test usage stats endpoint with no API calls"""
    response = client.get(
        '/api/claude/usage/monthly',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert 'total_cost_usd' in data
    assert 'api_calls' in data
    assert 'cost_by_model' in data
    assert data['total_cost_usd'] == 0.0
    assert data['api_calls'] == 0
    assert data['cost_by_model'] == {}


def test_monthly_usage_after_api_calls(client, user_email, auth_token):
    """Test usage stats after making API calls"""
    # Make analyze call
    client.post(
        '/api/claude/analyze-email',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    # Make matching call
    client.post(
        '/api/claude/match-application',
        json={'email_id': user_email.id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    # Check usage
    response = client.get(
        '/api/claude/usage/monthly',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['api_calls'] == 2
    assert data['total_cost_usd'] > 0
    assert 'claude-haiku-3-5' in data['cost_by_model']


def test_claude_endpoints_require_auth(client):
    """Test that Claude endpoints require authentication"""
    dummy_id = 'dummy-id'

    # analyze-email without auth
    response = client.post(
        '/api/claude/analyze-email',
        json={'email_id': dummy_id}
    )
    assert response.status_code == 401

    # match-application without auth
    response = client.post(
        '/api/claude/match-application',
        json={'email_id': dummy_id}
    )
    assert response.status_code == 401

    # usage/monthly without auth
    response = client.get('/api/claude/usage/monthly')
    assert response.status_code == 401


def test_api_call_logging(client, user_email, auth_headers, app):
    """Test that API calls are logged to database"""
    headers, user = auth_headers

    # Clear any existing calls (z.B. von früheren Tests im Cluster)
    ApiCall.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    # Make an API call
    client.post(
        '/api/claude/analyze-email',
        json={'email_id': user_email.id},
        headers=headers,
    )

    # Verify logged
    api_calls = ApiCall.query.filter_by(
        user_id=user.id,
        endpoint='/api/claude/analyze-email'
    ).all()

    assert len(api_calls) == 1
    call = api_calls[0]
    assert call.model == 'claude-haiku-3-5'
    assert call.tokens_in == 150
    assert call.tokens_out == 500
    assert call.cost > 0
