"""Cron-Token Decorator: schützt Cron-Endpoints via X-Cron-Token Header."""
import os
import hmac
from functools import wraps
from flask import request, jsonify


def require_cron_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("JOB_CRON_TOKEN")
        if not expected:
            return jsonify({"error": "Cron-Token nicht konfiguriert"}), 503

        provided = request.headers.get("X-Cron-Token", "")
        if not hmac.compare_digest(expected, provided):
            return jsonify({"error": "Forbidden"}), 403

        return fn(*args, **kwargs)
    return wrapper
