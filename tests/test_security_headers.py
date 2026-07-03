# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss


def test_csp_allows_frontend_pdf_and_cv_libraries(client):
    response = client.get("/")

    csp = response.headers["Content-Security-Policy"]

    assert "script-src" in csp
    assert "https://cdnjs.cloudflare.com" in csp
    assert "worker-src" in csp
    assert "blob:" in csp
