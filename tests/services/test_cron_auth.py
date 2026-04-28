import os
from flask import Flask
from services.cron_auth import require_cron_token


def make_app(monkeypatch, token=None):
    if token is not None:
        monkeypatch.setenv("JOB_CRON_TOKEN", token)
    app = Flask(__name__)
    @app.post("/cron/test")
    @require_cron_token
    def cron_endpoint():
        return {"ok": True}
    return app


def test_blocks_without_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    client = app.test_client()
    r = client.post("/cron/test")
    assert r.status_code == 403

def test_blocks_with_wrong_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "wrong"})
    assert r.status_code == 403

def test_passes_with_correct_token(monkeypatch):
    app = make_app(monkeypatch, "secret123")
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "secret123"})
    assert r.status_code == 200

def test_blocks_when_env_unset(monkeypatch):
    monkeypatch.delenv("JOB_CRON_TOKEN", raising=False)
    app = make_app(monkeypatch, None)
    r = app.test_client().post("/cron/test", headers={"X-Cron-Token": "anything"})
    assert r.status_code == 503
