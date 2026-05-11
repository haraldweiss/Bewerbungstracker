# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Shared fixtures for tests/api/ — available to all test modules in this package."""
import pytest


@pytest.fixture
def auth_header(app, user_factory):
    """JWT-Header für authentifizierte Requests.

    Returns: ({'Authorization': 'Bearer ...'}, user)
    """
    from auth_service import AuthService
    user = user_factory()
    token = AuthService.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user
