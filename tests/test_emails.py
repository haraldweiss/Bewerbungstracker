import pytest
from models import Email
from database import db
from datetime import datetime

# auth_token + auth_headers kommen aus tests/conftest.py


@pytest.fixture
def user_with_email(app, auth_headers):
    """Create test email for the authenticated user."""
    _, user = auth_headers
    email = Email(
        user_id=user.id,
        subject='Test email',
        from_address='sender@example.com',
        body='This is a test email',
        timestamp=datetime.utcnow()
    )
    db.session.add(email)
    db.session.commit()
    # Lade die ID jetzt, damit nach Session-Schließung kein Detached-Refresh
    # nötig ist (Tests greifen auf email.id und email.body zu).
    db.session.refresh(email)
    return user, email


def test_list_emails(client, user_with_email, auth_token):
    """Test listing emails"""
    response = client.get(
        '/api/emails',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['count'] == 1
    assert data['emails'][0]['subject'] == 'Test email'


def test_get_email(client, user_with_email, auth_token):
    """Test getting full email"""
    user, email = user_with_email

    response = client.get(
        f'/api/emails/{email.id}',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['body'] == 'This is a test email'


def test_match_email(client, app, user_with_email, auth_token):
    """Test matching email to application"""
    user, email = user_with_email

    with app.app_context():
        from models import Application

        app_obj = Application(
            user_id=user.id,
            company='Google',
            position='SWE'
        )
        db.session.add(app_obj)
        db.session.commit()
        app_id = app_obj.id

    response = client.post(
        f'/api/emails/{email.id}/match',
        json={'application_id': app_id},
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['matched_application_id'] == app_id
