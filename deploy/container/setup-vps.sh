#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Einmalige Setup-Schritte auf dem VPS für containerisiertes Deployment.
# Lokal aufrufen: scp deploy/container/setup-vps.sh root@vps:/root/ && ssh root@vps "bash /root/setup-vps.sh"
#
# Prerequisites:
#   - Podman installiert (dnf install podman)
#   - podman-systemd installiert (für Quadlet-Unterstützung)
#   - Build des Images: podman build -t localhost/bewerbungen:latest .

set -euo pipefail

DATA_DIR=${DATA_DIR:-/opt/bewerbungen-data}
CONFIG_DIR=${CONFIG_DIR:-/etc/bewerbungen}
QUADLET_DIR=/etc/containers/systemd

echo "▶ Data-Verzeichnis: $DATA_DIR"
mkdir -p "$DATA_DIR"/{instance,logs,backups}

echo "▶ Config-Verzeichnis: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# .env-Template falls noch nicht vorhanden
if [ ! -f "$CONFIG_DIR/bewerbungen.env" ]; then
    echo "▶ Erstelle $CONFIG_DIR/bewerbungen.env — bitte alle Secrets setzen!"
    cat > "$CONFIG_DIR/bewerbungen.env" << 'EOF'
FLASK_ENV=production
JWT_SECRET_KEY=replace-with-strong-random-key
JOB_CRON_TOKEN=replace-with-random-secret-32plus-chars
CLAUDE_API_KEY=
AI_PROVIDER_SERVICE_URL=http://host.containers.internal:8767
AI_PROVIDER_SERVICE_TOKEN=
MAIL_SERVER=smtp.ionos.de
MAIL_PORT=465
MAIL_USE_TLS=False
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
APP_URL=https://bewerbungen.wolfinisoftware.de
CORS_ORIGINS=https://bewerbungen.wolfinisoftware.de
AUTH_REQUIRED=true
DATABASE_URL=sqlite:////app/data/instance/bewerbungstracker.db
EOF
    chmod 600 "$CONFIG_DIR/bewerbungen.env"
fi

# Quadlet-Dateien installieren
echo "▶ Installiere Quadlet-Dateien nach $QUADLET_DIR"
for unit in bewerbungen-app bewerbungen-worker bewerbungen-imap-proxy bewerbungen-email-service bewerbungen-cron; do
    if [ -f "deploy/container/${unit}.container" ]; then
        cp "deploy/container/${unit}.container" "$QUADLET_DIR/${unit}.container"
    fi
done

systemctl daemon-reload

echo ""
echo "✓ Setup fertig."
echo ""
echo "Nächste Schritte:"
echo "  1) Secrets in $CONFIG_DIR/bewerbungen.env setzen"
echo "  2) Build: podman build -t localhost/bewerbungen:latest ."
echo "  3) Start: systemctl enable --now bewerbungen-app bewerbungen-worker bewerbungen-imap-proxy bewerbungen-cron"
echo "  4) Status: systemctl status bewerbungen-app"
echo "  5) Falls ai-provider-service läuft: 'host.containers.internal:8767' ist automatisch erreichbar"
echo ""
echo "Apache-Konfiguration anpassen:"
echo "  ProxyPass / http://127.0.0.1:5000/ (statt bisherigem gunicorn-Socket)"
