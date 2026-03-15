#!/usr/bin/env python3
"""
Startup script for Railway/Heroku deployment.
Reads PORT environment variable and starts gunicorn with proper port binding.
This approach avoids bash variable expansion issues in Docker.
"""

import os
import subprocess
import sys

def main():
    # Get PORT from environment, default to 8080
    port = os.environ.get('PORT', '8080')

    print(f"🚀 Starting Bewerbungs-Tracker")
    print(f"📦 Port: {port}")
    print(f"👷 Workers: 2")
    print(f"⏱️  Timeout: 120s")

    # Build gunicorn command with the actual port number
    cmd = [
        'gunicorn',
        '--workers', '2',
        '--timeout', '120',
        '--bind', f'0.0.0.0:{port}',
        '--access-logfile', '-',
        '--error-logfile', '-',
        'app:app'
    ]

    # Use exec to replace this process with gunicorn
    os.execvp('gunicorn', cmd)

if __name__ == '__main__':
    main()
