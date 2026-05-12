#!/bin/bash

# Setup .env für Mac Mini (LOCAL DEVELOPMENT)

echo "=========================================="
echo "Bewerbungstracker - .env Setup (Mac Mini)"
echo "=========================================="
echo ""

# JWT_SECRET_KEY generieren
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
echo "✓ JWT_SECRET_KEY generiert"
echo ""

# User Input
echo "Bitte folgende Werte eingeben:"
echo ""

read -p "MAIL_USERNAME (z.B. deine@ionos-email.de): " MAIL_USERNAME
read -sp "MAIL_PASSWORD (wird nicht angezeigt): " MAIL_PASSWORD
echo ""

read -p "CLAUDE_API_KEY (optional, Enter zum Überspringen): " CLAUDE_API_KEY
echo ""

# .env auf Mac Mini erstellen
ssh haraldweiss@Mac-mini-von-Harald-2.local "cat > /Library/WebServer/Documents/Bewerbungstracker/.env << 'ENVEOF'
# Bewerbungstracker – Environment Variables
# LOCAL DEVELOPMENT PROFILE

FLASK_ENV=development
FLASK_APP=app.py
PORT=8080

DATABASE_URL=sqlite:///bewerbungstracker.db

JWT_SECRET_KEY=$JWT_SECRET
AUTH_REQUIRED=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
APP_URL=http://localhost:8080

MAIL_SERVER=smtp.ionos.de
MAIL_PORT=465
MAIL_USE_TLS=False
MAIL_USERNAME=$MAIL_USERNAME
MAIL_PASSWORD=$MAIL_PASSWORD
MAIL_DEFAULT_SENDER=$MAIL_USERNAME

IMAP_PROXY_URL=http://127.0.0.1:8765

CLAUDE_API_KEY=$CLAUDE_API_KEY

RAPIDAPI_KEY=
XING_RSS_URL=
LINKEDIN_RSS_URL=
STEPSTONE_RSS_URL=
ENVEOF
"

echo ""
echo "✓ .env erfolgreich auf Mac Mini erstellt!"
echo ""
echo "JWT_SECRET_KEY:"
echo "  $JWT_SECRET"
echo ""
echo "Mail-Config:"
echo "  Username: $MAIL_USERNAME"
echo "  Password: (gespeichert)"
echo ""
