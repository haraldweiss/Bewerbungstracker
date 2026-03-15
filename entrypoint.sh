#!/bin/bash
# Entrypoint script for Docker - properly handles PORT environment variable

set -e

# Get PORT from environment or default to 8080
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-2}"
TIMEOUT="${TIMEOUT:-120}"

echo "🚀 Starting Bewerbungs-Tracker"
echo "📦 Port: $PORT"
echo "👷 Workers: $WORKERS"
echo "⏱️  Timeout: ${TIMEOUT}s"

# Execute gunicorn with the PORT variable properly expanded
exec gunicorn \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --bind "0.0.0.0:$PORT" \
    --access-logfile - \
    --error-logfile - \
    app:app
