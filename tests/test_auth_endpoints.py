import pytest


def test_register_endpoint(client):
    """Test /api/auth/register"""
    response = client.post(
        '/api/auth/register',
        json={
            'email': 'test@example.com',
            'password': 'password123'
        }
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'test@example.com'


def test_register_duplicate(client):
    """Test registering duplicate email"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )

    response = client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password456'}
    )

    assert response.status_code == 400


def test_login_endpoint(client, activate_user_after_register):
    """Test /api/auth/login"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    # Email-Confirmation + Admin-Approval wird via Helper umgangen, sodass
    # der eigentliche Login-Flow getestet werden kann.
    activate_user_after_register('test@example.com')

    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert data['token_type'] == 'Bearer'


def test_get_current_user(client, activate_user_after_register):
    """Test /api/auth/me with token"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )
    activate_user_after_register('test@example.com')

    login_response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )

    token = login_response.get_json()['access_token']

    response = client.get(
        '/api/auth/me',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['email'] == 'test@example.com'


def test_unauthorized_without_token(client):
    """Test endpoint without token returns 401"""
    response = client.get('/api/auth/me')
    assert response.status_code == 401
