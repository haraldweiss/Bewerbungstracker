#!/usr/bin/env python3
"""WSGI entry point – wird von gunicorn als `wsgi:app` geladen."""

import os
import sys
from app import create_app

# Gunicorn importiert dieses `app`-Symbol direkt.
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting Bewerbungs-Tracker on port {port}")
    if os.environ.get('FLASK_ENV') == 'development':
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        sys.exit(0)
