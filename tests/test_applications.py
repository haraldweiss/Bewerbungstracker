import pytest
from auth_service import AuthService


@pytest.fixture
def auth_token(client):
    """Register and login user, return token"""
    client.post(
        '/api/auth/register',
        json={'email': 'test@example.com', 'password': 'password123'}
    )

    response = client.post(
        '/api/auth/login',
        json={'email': 'test@example.com', 'password': 'password123'}
    )

    return response.get_json()['access_token']


def test_create_application(client, auth_token):
    """Test creating application"""
    response = client.post(
        '/api/applications',
        json={
            'company': 'Google',
            'position': 'Software Engineer',
            'applied_date': '2026-04-22'
        },
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data['company'] == 'Google'
    assert data['position'] == 'Software Engineer'


def test_list_applications(client, auth_token):
    """Test listing applications"""
    # Create 2 applications
    client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    client.post(
        '/api/applications',
        json={'company': 'Meta', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    response = client.get(
        '/api/applications',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['count'] == 2


def test_update_application(client, auth_token):
    """Test updating application"""
    create_response = client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    app_id = create_response.get_json()['id']

    response = client.patch(
        f'/api/applications/{app_id}',
        json={'status': 'interview'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'interview'


def test_delete_application(client, auth_token):
    """Test deleting application"""
    create_response = client.post(
        '/api/applications',
        json={'company': 'Google', 'position': 'SWE'},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    app_id = create_response.get_json()['id']

    response = client.delete(
        f'/api/applications/{app_id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200

    # Verify deleted
    get_response = client.get(
        f'/api/applications/{app_id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )
    assert get_response.status_code == 404
