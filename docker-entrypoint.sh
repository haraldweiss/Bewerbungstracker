#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Multi-role entrypoint for containerized Bewerbungstracker.
# Role is selected by the first argument (or ROLE env var):
#   app           — gunicorn Flask app (default)
#   worker        — background task worker
#   imap-proxy    — IMAP proxy on port 8765
#   email-service — Email service on port 8766
#   cron          — cron daemon with curl-based job triggers

set -euo pipefail

ROLE="${1:-${ROLE:-app}}"

# Source .env if present (for local container dev)
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

case "$ROLE" in
    app)
        exec gunicorn \
            --workers "${GUNICORN_WORKERS:-4}" \
            --worker-class sync \
            --bind "0.0.0.0:${PORT:-5000}" \
            --timeout "${GUNICORN_TIMEOUT:-60}" \
            --access-logfile - \
            --error-logfile - \
            wsgi:app
        ;;
    worker)
        exec python -u -m services.tasks.worker
        ;;
    imap-proxy)
        exec python -u /app/imap_proxy.py
        ;;
    email-service)
        exec python -u /app/email_service.py
        ;;
    cron)
        # Cron-Jobs laufen via crontab + curl auf den internen App-Endpoint.
        # JOB_CRON_TOKEN muss im Container gesetzt sein.
        exec supercronic /app/deploy/container/crontab
        ;;
    *)
        echo "Unknown role: $ROLE"
        echo "Usage: docker-entrypoint.sh {app|worker|imap-proxy|email-service|cron}"
        exit 1
        ;;
esac
