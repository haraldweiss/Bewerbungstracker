#!/usr/bin/env python3
"""
WSGI entry point for Railway/Heroku deployment
This file allows proper PORT environment variable handling
"""

import os
import sys
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))

    print(f"🚀 Starting Bewerbungs-Tracker on port {port}")
    print(f"📦 Using Gunicorn with 2 workers")

    # Use app.run for development or require gunicorn for production
    if os.environ.get('FLASK_ENV') == 'development':
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Gunicorn will be called by Procfile/Docker
        sys.exit(0)
