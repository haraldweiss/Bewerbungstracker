#!/bin/bash
# Startup script for Railway/Heroku deployment
# Properly handles PORT environment variable

set -e

# Default port if not set
PORT=${PORT:-8080}

echo "🚀 Starting Bewerbungs-Tracker on port $PORT"
echo "📦 Using gunicorn with 2 workers"

# Start gunicorn with the PORT environment variable
exec gunicorn \
    --workers 2 \
    --timeout 120 \
    --bind 0.0.0.0:${PORT} \
    --access-logfile - \
    --error-logfile - \
    app:app
