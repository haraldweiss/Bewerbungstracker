# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""Tests fuer Admin Status-Overview Healthchecks."""

from types import SimpleNamespace

import pytest

from auth_service import AuthService


@pytest.fixture
def admin_headers(user_factory):
    admin = user_factory(email="admin-status@test.de", is_admin=True)
    token = AuthService.create_access_token(admin.id)
    return {"Authorization": f"Bearer {token}"}


def test_status_overview_uses_configured_ai_provider_health_url(
    app, client, admin_headers, monkeypatch
):
    app.config["AI_PROVIDER_SERVICE_URL"] = "http://10.88.0.1:8767/"
    called_urls = []

    def fake_urlopen(req, timeout):
        called_urls.append(req.full_url)
        return SimpleNamespace(status=200)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    resp = client.get("/api/admin/status-overview", headers=admin_headers)

    assert resp.status_code == 200
    assert "http://bewerbungen-imap-proxy:8765/" in called_urls
    assert "http://10.88.0.1:8767/health" in called_urls
    assert "http://ai-provider:8767/health" not in called_urls
    assert resp.get_json()["health"]["ai_provider"]["status"] == "ok"
