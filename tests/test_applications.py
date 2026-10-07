# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import pytest

# auth_token kommt aus tests/conftest.py (zentrale Fixture mit aktiviertem User)


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

@pytest.mark.parametrize('payload', [
    [], 'text', {'company': ' ', 'position': 'Engineer'},
    {'company': [], 'position': 'Engineer'},
    {'company': 'Acme', 'position': 'Engineer', 'status': 'unknown'},
    {'company': 'Acme', 'position': 'Engineer', 'applied_date': '2026-02-30'},
    {'company': 'Acme', 'position': 'Engineer', 'applied_date': 123},
    {'company': 'Acme', 'position': 'Engineer', 'notes': {'bad': 'type'}},
])
def test_create_rejects_invalid_payload_without_persisting(client, auth_token, payload):
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = client.post('/api/applications', json=payload, headers=headers)
    assert response.status_code == 400
    assert client.get('/api/applications', headers=headers).get_json()['count'] == 0

@pytest.mark.parametrize('changes', [
    {'company': ''}, {'position': None}, {'status': 'unknown'},
    {'notes': ['bad']}, {'company': 'Changed', 'applied_date': 'not-a-date'},
])
def test_invalid_patch_leaves_existing_application_intact(client, auth_token, changes):
    headers = {'Authorization': f'Bearer {auth_token}'}
    created = client.post('/api/applications',json={'company':'Acme','position':'Engineer'},headers=headers).get_json()
    response = client.patch(f"/api/applications/{created['id']}",json=changes,headers=headers)
    assert response.status_code == 400
    current = client.get(f"/api/applications/{created['id']}",headers=headers).get_json()
    assert current['company'] == 'Acme'
    assert current['position'] == 'Engineer'
    assert current['status'] == 'beworben'


def test_trimmed_duplicate_is_rejected_on_create_and_update(client, auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    client.post('/api/applications',json={'company':'Acme','position':'Engineer'},headers=headers)
    duplicate = client.post('/api/applications',json={'company':' acme ','position':' engineer '},headers=headers)
    assert duplicate.status_code == 409
    other = client.post('/api/applications',json={'company':'Other','position':'Engineer'},headers=headers).get_json()
    response = client.patch(f"/api/applications/{other['id']}",json={'company':' ACME '},headers=headers)
    assert response.status_code == 409
    assert client.get(f"/api/applications/{other['id']}",headers=headers).get_json()['company'] == 'Other'


def test_duplicate_matching_uses_consistent_database_case_rules(client, auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    payload = {'company': 'MÜLLER', 'position': 'ÄRZTIN'}
    assert client.post('/api/applications', json=payload, headers=headers).status_code == 201
    assert client.post('/api/applications', json=payload, headers=headers).status_code == 409
    other = client.post('/api/applications', json={'company': 'Other', 'position': 'ÄRZTIN'}, headers=headers).get_json()
    assert client.patch(f"/api/applications/{other['id']}",json={'company': 'MÜLLER'},headers=headers).status_code == 409


@pytest.mark.parametrize('status', ['beworben','interview','antwort','absage','ghosting','zusage','applied','offer','rejected','archived'])
def test_supported_statuses_and_optional_nulls_remain_compatible(client, auth_token, status):
    headers = {'Authorization': f'Bearer {auth_token}'}
    created = client.post('/api/applications',json={
        'company':' Acme ', 'position':' Engineer ', 'status':status,
        'notes':None, 'salary':None, 'applied_date':'2026-10-07T09:30:00',
    },headers=headers)
    assert created.status_code == 201
    data = created.get_json()
    assert data['company'] == 'Acme'
    assert data['status'] == status
    assert data['applied_date'] == '2026-10-07'
    response = client.patch(f"/api/applications/{data['id']}",json={'applied_date':'','notes':'A <B> & C'},headers=headers)
    assert response.status_code == 200
    assert response.get_json()['applied_date'] is None
    assert response.get_json()['notes'] == 'A <B> & C'


@pytest.mark.parametrize('field,value', [('company','x'*256),('position','x'*256),('source','x'*51),('applied_date',False)])
def test_field_limits_and_boolean_dates_are_rejected(client, auth_token, field, value):
    response=client.post('/api/applications',json={'company':'Acme','position':'Engineer',field:value},headers={'Authorization':f'Bearer {auth_token}'})
    assert response.status_code == 400


def test_duplicate_check_and_updates_remain_scoped_to_each_user(client, auth_headers, user_factory):
    from auth_service import AuthService
    first_headers, _ = auth_headers
    second_user = user_factory()
    second_headers = {'Authorization': f'Bearer {AuthService.create_access_token(second_user.id)}'}
    payload = {'company':'Acme','position':'Engineer'}
    first = client.post('/api/applications',json=payload,headers=first_headers)
    second = client.post('/api/applications',json=payload,headers=second_headers)
    assert first.status_code == second.status_code == 201
    response = client.patch(f"/api/applications/{first.get_json()['id']}",json={'company':'Changed'},headers=second_headers)
    assert response.status_code == 404
    assert client.get(f"/api/applications/{first.get_json()['id']}",headers=first_headers).get_json()['company'] == 'Acme'


def test_recovery_conflict_keeps_duplicate_in_trash(client, auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    payload = {'company':'Acme','position':'Engineer'}
    old = client.post('/api/applications',json=payload,headers=headers).get_json()
    client.delete(f"/api/applications/{old['id']}",headers=headers)
    client.post('/api/applications',json=payload,headers=headers)
    response = client.post(f"/api/applications/{old['id']}/recover",headers=headers)
    assert response.status_code == 409
    assert client.get('/api/applications',headers=headers).get_json()['count'] == 1
    assert client.get('/api/applications/deleted',headers=headers).get_json()['count'] == 1
