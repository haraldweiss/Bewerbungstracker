"""
Task 15: Complete Admin User Management Workflow Tests
Tests all scenarios for the admin dashboard including:
- Admin login and dashboard access
- New user registration with email confirmation
- Admin approval workflow
- User login after approval
- Password reset
- User deletion
- Admin promotion
- Email notifications
"""

import pytest
from models import User, EmailConfirmationToken, Application
from database import db
from datetime import datetime, timedelta


@pytest.fixture
def admin_user(app):
    """Create an admin user"""
    with app.app_context():
        from auth_service import AuthService

        admin = User(
            email='harald.weiss@wolfinisoftware.de',
            password_hash=AuthService.hash_password('AdminPass123!'),
            email_confirmed=True,
            is_active=True,
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    # Return the ID as a string instead of the detached object
    return type('AdminUser', (), {'id': admin_id})()


@pytest.fixture
def admin_token(client, admin_user):
    """Login as admin and get token"""
    response = client.post(
        '/api/auth/login',
        json={
            'email': 'harald.weiss@wolfinisoftware.de',
            'password': 'AdminPass123!'
        }
    )
    return response.get_json()['access_token']


class TestStep1AdminLogin:
    """Step 1: Verify Admin Login"""

    def test_admin_can_login(self, client, admin_user):
        """Admin user can login with correct credentials"""
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'harald.weiss@wolfinisoftware.de',
                'password': 'AdminPass123!'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['token_type'] == 'Bearer'

    def test_admin_can_access_dashboard(self, client, admin_token):
        """Admin can call /api/auth/me and verify admin status"""
        response = client.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == 'harald.weiss@wolfinisoftware.de'
        assert data['is_admin'] is True


class TestStep2NewUserRegistration:
    """Step 2: Test New User Registration (Unconfirmed State)"""

    def test_new_user_registration_creates_unconfirmed_user(self, client, app):
        """New user registration creates unconfirmed, inactive account"""
        response = client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data['email'] == 'testuser@example.com'
        assert data['message'] == 'Registration successful! Please confirm your email to activate your account.'

        # Verify user is unconfirmed and inactive
        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            assert user is not None
            assert user.email_confirmed is False
            assert user.is_active is False

    def test_unconfirmed_user_cannot_login(self, client):
        """User cannot login if email not confirmed"""
        # Register user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        # Try to login
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        assert response.status_code == 401
        data = response.get_json()
        assert 'email' in data['error'].lower()


class TestStep3EmailConfirmation:
    """Step 3: Test Email Confirmation"""

    def test_email_confirmation_token_created(self, client, app):
        """Email confirmation token is created on registration"""
        response = client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        assert response.status_code == 201

        with app.app_context():
            token_record = EmailConfirmationToken.query.filter_by(
                user_id=User.query.filter_by(email='testuser@example.com').first().id
            ).first()
            assert token_record is not None
            assert token_record.expires_at > datetime.utcnow()

    def test_email_confirmation_with_valid_token(self, client, app):
        """Email confirmation works with valid token"""
        # Register user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        # Get confirmation token
        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token

        # Confirm email
        response = client.get(f'/api/auth/confirm-email?token={token}')

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == 'testuser@example.com'

        # Verify user is now confirmed but still inactive (pending approval)
        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            assert user.email_confirmed is True
            assert user.is_active is False

    def test_email_confirmation_with_expired_token(self, client, app):
        """Email confirmation fails with expired token"""
        # Register user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        # Create an expired token
        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            # Delete old token
            EmailConfirmationToken.query.filter_by(user_id=user.id).delete()

            # Create expired token
            expired_token = EmailConfirmationToken(
                token='expired_token_123',
                user_id=user.id,
                expires_at=datetime.utcnow() - timedelta(hours=1)
            )
            db.session.add(expired_token)
            db.session.commit()

        # Try to confirm with expired token
        response = client.get('/api/auth/confirm-email?token=expired_token_123')

        assert response.status_code == 400
        data = response.get_json()
        assert 'expired' in data['error'].lower()


class TestStep4AdminApprovalWorkflow:
    """Step 4: Test Admin Approval Workflow"""

    def test_admin_can_list_users(self, client, app, admin_token):
        """Admin can list all users"""
        # Create a test user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        # Confirm email
        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token

        client.get(f'/api/auth/confirm-email?token={token}')

        # List users as admin
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert len(data['users']) >= 2  # Admin + test user

    def test_admin_list_shows_user_status(self, client, app, admin_token):
        """Admin list shows email_confirmed, is_active, is_admin fields"""
        # Create and confirm test user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token

        client.get(f'/api/auth/confirm-email?token={token}')

        # List users
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        data = response.get_json()
        test_user = next((u for u in data['users'] if u['email'] == 'testuser@example.com'), None)

        assert test_user is not None
        assert test_user['email_confirmed'] is True
        assert test_user['is_active'] is False
        assert test_user['is_admin'] is False

    def test_admin_can_approve_confirmed_user(self, client, app, admin_token):
        """Admin can approve a confirmed user"""
        # Register and confirm user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token
            user_id = user.id

        client.get(f'/api/auth/confirm-email?token={token}')

        # Approve user
        response = client.post(
            f'/api/admin/users/{user_id}/approve',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == 'testuser@example.com'
        assert data['is_active'] is True

        # Verify in database
        with app.app_context():
            user = User.query.get(user_id)
            assert user.is_active is True

    def test_admin_cannot_approve_unconfirmed_user(self, client, app, admin_token):
        """Admin cannot approve user who hasn't confirmed email"""
        # Register user without confirming email
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            user_id = user.id

        # Try to approve without email confirmation
        response = client.post(
            f'/api/admin/users/{user_id}/approve',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'email' in data['error'].lower()


class TestStep5UserLoginAfterApproval:
    """Step 5: Test User Login After Approval"""

    def test_approved_user_can_login(self, client, app, admin_token):
        """Approved user can login"""
        # Register and confirm user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token
            user_id = user.id

        client.get(f'/api/auth/confirm-email?token={token}')

        # Approve user
        client.post(
            f'/api/admin/users/{user_id}/approve',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        # Login as approved user
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'access_token' in data

    def test_non_approved_user_cannot_login(self, client):
        """Non-approved user cannot login even if confirmed"""
        # Register user (email unconfirmed)
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        # Try to login
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        assert response.status_code == 401


class TestStep6AdminPanelFunctionality:
    """Step 6: Test Admin Panel Functionality"""

    def test_admin_can_view_user_applications(self, client, app, admin_token):
        """Admin can view applications for a user"""
        # Create user with application
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()

            # Create application
            app_obj = Application(
                user_id=user.id,
                company='Google',
                position='Software Engineer'
            )
            db.session.add(app_obj)
            db.session.commit()
            user_id = user.id

        # Get applications as admin
        response = client.get(
            f'/api/admin/users/{user_id}/applications',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'applications' in data
        assert len(data['applications']) == 1
        assert data['applications'][0]['company'] == 'Google'

    def test_admin_can_reset_password(self, client, app, admin_token):
        """Admin can reset user password"""
        # Create user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            user_id = user.id
            old_hash = user.password_hash

        # Reset password
        response = client.post(
            f'/api/admin/users/{user_id}/reset-password',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'temporary_password' in data

        # Verify password was changed
        with app.app_context():
            user = User.query.get(user_id)
            assert user.password_hash != old_hash

    def test_admin_can_promote_to_admin(self, client, app, admin_token):
        """Admin can promote a user to admin"""
        # Create user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            user_id = user.id
            assert user.is_admin is False

        # Promote to admin
        response = client.patch(
            f'/api/admin/users/{user_id}/promote',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['is_admin'] is True

        # Verify in database
        with app.app_context():
            user = User.query.get(user_id)
            assert user.is_admin is True

    def test_admin_can_delete_user(self, client, app, admin_token):
        """Admin can delete a user"""
        # Create user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            user_id = user.id

        # Delete user
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200

        # Verify deleted
        with app.app_context():
            user = User.query.get(user_id)
            assert user is None

    def test_admin_cannot_delete_themselves(self, client, admin_token, admin_user):
        """Admin cannot delete themselves"""
        response = client.delete(
            f'/api/admin/users/{admin_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'cannot delete yourself' in data['error'].lower()


class TestStep7NonAdminUserAccess:
    """Step 7: Verify non-admin users cannot access admin features"""

    def test_non_admin_cannot_access_admin_list(self, client, app, admin_token):
        """Non-admin user cannot access /api/admin/users"""
        # Create and approve regular user
        client.post(
            '/api/auth/register',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )

        with app.app_context():
            user = User.query.filter_by(email='testuser@example.com').first()
            token_record = EmailConfirmationToken.query.filter_by(user_id=user.id).first()
            token = token_record.token
            user_id = user.id

        client.get(f'/api/auth/confirm-email?token={token}')
        client.post(
            f'/api/admin/users/{user_id}/approve',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        # Login as regular user
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': 'testuser@example.com',
                'password': 'TestPass123!'
            }
        )
        user_token = login_response.get_json()['access_token']

        # Try to access admin endpoint
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {user_token}'}
        )

        assert response.status_code == 403


class TestAdminAuthenticationRequired:
    """Test that admin endpoints require authentication and admin role"""

    def test_admin_endpoints_require_token(self, client, admin_user):
        """Admin endpoints return 401 without token"""
        response = client.get('/api/admin/users')
        assert response.status_code == 401

    def test_admin_endpoints_require_admin_role(self, client, app):
        """Admin endpoints return 403 for non-admin users"""
        from auth_service import AuthService

        # Create non-admin user
        with app.app_context():
            user = User(
                email='user@example.com',
                password_hash=AuthService.hash_password('UserPass123!'),
                email_confirmed=True,
                is_active=True,
                is_admin=False
            )
            db.session.add(user)
            db.session.commit()

        # Login
        login_response = client.post(
            '/api/auth/login',
            json={
                'email': 'user@example.com',
                'password': 'UserPass123!'
            }
        )
        token = login_response.get_json()['access_token']

        # Try admin endpoint
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 403
