#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Setup / Recovery für Oracle VM (Docker, nicht Podman/Quadlet).
#
# Dieses Skript dokumentiert die exakten `docker run`-Befehle für alle 5
# Bewerbungstracker-Container auf der Oracle VM. Es dient als:
#   - Einrichtungs-Anleitung für eine frische VM
#   - Recovery-Vorlage wenn Container neu erstellt werden müssen
#   - Dokumentation der Volume-Namen (single source of truth)
#
# HISTORY
# 2026-06-12  Volume-Namen waren inkonsistent (underscore vs hyphen):
#             APP nutzte "bewerbungen_data", WORKER "bewerbungen-data",
#             EMAIL-SERVICE + IMAP-PROXY ein Host-Bind-Mount.
#             Fix: ALLE Container auf EINEN Volume-Namen vereinheitlicht.
#             Der Fehler fiel erst auf als 6 Tasks 2h lang nicht verarbeitet
#             wurden weil der WORKER die neuen DB-Einträge nicht sah.
#
# PREREQUISITES
#   - Docker installiert
#   - Image gebaut: docker build -t localhost/bewerbungen:latest .
#   - Docker-Netzwerk: docker network create bewerbungen-net
#   - Konfigurations-Ordner: /etc/bewerbungen/bewerbungen.env (siehe §1)
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  VOLUME-NAMEN MÜSSEN EXAKT GLEICH SEIN                               ║
# ║  Unterschiede wie bewerbungen_data vs bewerbungen-data führen dazu,    ║
# ║  dass APP Schreibt und WORKER/Leser verschiedene DB-Kopien sehen.      ║
# ║  → Volume-Name: bewerbungen_data  (mit underscore, KEIN hyphen)       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail
# ── Konfiguration ──────────────────────────────────────────────────────────

VOLUME_NAME="bewerbungen_data"
NETWORK_NAME="bewerbungen-net"
CONFIG_DIR="/etc/bewerbungen"
IMAGE="localhost/bewerbungen:latest"

# ── §1: Konfigurationsdatei ────────────────────────────────────────────────

setup_config() {
    echo "▶ Config: $CONFIG_DIR/bewerbungen.env"
    mkdir -p "$CONFIG_DIR"
    if [ ! -f "$CONFIG_DIR/bewerbungen.env" ]; then
        cat > "$CONFIG_DIR/bewerbungen.env" << 'ENVEOF'
FLASK_ENV=production
JWT_SECRET_KEY=replace-with-strong-random-key
JOB_CRON_TOKEN=replace-with-random-secret-32plus-chars
CLAUDE_API_KEY=
AI_PROVIDER_SERVICE_URL=http://10.88.0.1:8767
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
ENCRYPTION_KEY=replace-with-32-char-fernet-key
DATABASE_URL=sqlite:////app/data/bewerbungstracker.db
IMAP_PROXY_URL=http://bewerbungen-imap-proxy:8765
APP_INTERNAL_URL=http://bewerbungen-app:5000
AUTH_ALLOW_REGISTRATION=true
ENVEOF
        chmod 600 "$CONFIG_DIR/bewerbungen.env"
        echo "  → Template erstellt. BITTE ALLE SECRETS SETZEN!"
    else
        echo "  → Existiert bereits"
    fi
}

# ── §2: Volume + Netzwerk ─────────────────────────────────────────────────

setup_prereqs() {
    if ! docker volume inspect "$VOLUME_NAME" &>/dev/null; then
        docker volume create "$VOLUME_NAME"
        echo "▶ Volume $VOLUME_NAME erstellt"
    else
        echo "▶ Volume $VOLUME_NAME existiert bereits"
    fi

    if ! docker network inspect "$NETWORK_NAME" &>/dev/null; then
        docker network create "$NETWORK_NAME"
        echo "▶ Network $NETWORK_NAME erstellt"
    else
        echo "▶ Network $NETWORK_NAME existiert bereits"
    fi
}

# ── §3: Container-Kommandos (single source of truth) ──────────────────────

# WICHTIG: ALLE Container nutzen DASSELBE Volume $VOLUME_NAME.
# Ein Tippfehler (z.B. bewerbungen-data mit hyphen) führt zu
# inkonsistenten DB-Kopien und stumm scheiternden Tasks.
#
# Der CRON-Container hat KEIN Volume — er arbeitet per curl auf die
# APP_INTERNAL_URL und braucht keinen direkten DB-Zugriff.
#
# DATABASE_URL: sqlite:////app/data/bewerbungstracker.db
#   (4 Slashes = absolute path /app/data/bewerbungstracker.db)

start_app() {
    # BIND_HOST=0.0.0.0: gunicorn lauscht container-intern auf allen Interfaces,
    # damit Dockers Port-DNAT (host 127.0.0.1:5000 → container eth0) ankommt.
    # Die Security-Grenze ist das host-seitige -p 127.0.0.1:5000 (nur loopback),
    # NICHT der container-interne Bind. Ohne dies bindet der Entrypoint auf
    # 127.0.0.1 (Default) → Container unerreichbar (HTTP 502). Gleiches Muster
    # wie email-service/imap-proxy.
    docker run -d \
        --name bewerbungen-app \
        --restart unless-stopped \
        -v "$VOLUME_NAME:/app/data:z" \
        -v "$CONFIG_DIR/bewerbungen.env:/app/.env:ro" \
        --network "$NETWORK_NAME" \
        -p 127.0.0.1:5000:5000 \
        -e BIND_HOST=0.0.0.0 \
        "$IMAGE" app
    echo "▶ bewerbungen-app gestartet"
}

start_worker() {
    # ⚠ ENCRYPTION_KEY muss explizit übergeben werden — der Worker hat KEIN
    # .env-File (anders als APP). Ohne diesen Key können IMAP-Passwörter
    # nicht entschlüsselt werden → Email-Import schlägt fehl mit
    # "ENCRYPTION_KEY environment variable not set".
    # Der Key kommt aus /etc/bewerbungen/bewerbungen.env.
    local key
    key=$(grep '^ENCRYPTION_KEY=' "$CONFIG_DIR/bewerbungen.env" 2>/dev/null | cut -d= -f2-)
    if [ -z "$key" ]; then
        echo "❌ ENCRYPTION_KEY in $CONFIG_DIR/bewerbungen.env nicht gefunden!"
        return 1
    fi
    docker run -d \
        --name bewerbungen-worker \
        --restart unless-stopped \
        -v "$VOLUME_NAME:/app/data:z" \
        --network "$NETWORK_NAME" \
        -e ENCRYPTION_KEY="$key" \
        "$IMAGE" worker
    echo "▶ bewerbungen-worker gestartet"
}

start_email_service() {
    docker run -d \
        --name bewerbungen-email-service \
        --restart unless-stopped \
        -v "$VOLUME_NAME:/app/data:z" \
        --network "$NETWORK_NAME" \
        -p 127.0.0.1:8766:8766 \
        -e BIND_HOST=0.0.0.0 \
        "$IMAGE" email-service
    echo "▶ bewerbungen-email-service gestartet"
}

start_imap_proxy() {
    docker run -d \
        --name bewerbungen-imap-proxy \
        --restart unless-stopped \
        -v "$VOLUME_NAME:/app/data:z" \
        --network "$NETWORK_NAME" \
        -p 127.0.0.1:8765:8765 \
        -e BIND_HOST=0.0.0.0 \
        "$IMAGE" imap-proxy
    echo "▶ bewerbungen-imap-proxy gestartet"
}

start_cron() {
    # --env-file: Der Cron-Container braucht JOB_CRON_TOKEN + APP_INTERNAL_URL
    # (für die curl-Trigger an die App) sowie die übrigen App-Env-Vars. Ohne
    # dies läuft supercronic ohne Token → alle Stages scheitern an der Auth
    # (require_cron_token → 401/403). Der laufende Container wurde exakt so
    # gestartet (Env deckungsgleich mit bewerbungen.env). KEIN Volume — Cron
    # arbeitet nur per curl auf APP_INTERNAL_URL, nicht direkt auf der DB.
    docker run -d \
        --name bewerbungen-cron \
        --restart unless-stopped \
        --network "$NETWORK_NAME" \
        --env-file "$CONFIG_DIR/bewerbungen.env" \
        "$IMAGE" cron
    echo "▶ bewerbungen-cron gestartet"
}

# ── §4: Start / Stop / Restart / Status ──────────────────────────────────

start_all() {
    start_app
    sleep 3
    start_worker
    start_email_service
    start_imap_proxy
    start_cron
}

stop_all() {
    for c in bewerbungen-app bewerbungen-worker bewerbungen-email-service bewerbungen-imap-proxy bewerbungen-cron; do
        docker stop "$c" 2>/dev/null && echo "▶ $c gestoppt" || true
    done
}

restart_all() {
    stop_all
    sleep 2
    # Volume bleibt erhalten — Daten sind sicher
    start_all
}

show_status() {
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E '^(NAMES|bewerbung)'
}

show_volume_info() {
    echo "=== Volume $VOLUME_NAME ==="
    docker volume inspect "$VOLUME_NAME" --format 'Mountpoint: {{.Mountpoint}}'
    echo "Größe: $(docker run --rm -v "$VOLUME_NAME:/data:z" alpine du -sh /data/ 2>/dev/null | cut -f1)"
}

# ── §5: Daten-Migration (von altem Volume) ────────────────────────────────

migrate_from_old_volume() {
    local OLD_VOLUME="${1:-bewerbungen-data}"
    if docker volume inspect "$OLD_VOLUME" &>/dev/null; then
        echo "▶ Migriere Daten von $OLD_VOLUME nach $VOLUME_NAME..."
        docker run --rm \
            -v "$OLD_VOLUME:/from:z" \
            -v "$VOLUME_NAME:/to:z" \
            alpine sh -c 'cp -a /from/. /to/'
        echo "  → Fertig. Altes Volume kann gelöscht werden:"
        echo "    docker volume rm $OLD_VOLUME"
    else
        echo "  → Altes Volume $OLD_VOLUME nicht gefunden"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────

case "${1:-help}" in
    setup)
        setup_config
        setup_prereqs
        start_all
        echo "✓ Setup abgeschlossen"
        ;;
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        show_status
        ;;
    volume-info)
        show_volume_info
        ;;
    migrate)
        migrate_from_old_volume "${2:-bewerbungen-data}"
        ;;
    logs)
        docker logs -f "bewerbungen-${2:-app}"
        ;;
    rebuild)
        # Nach Image-Neubau: Container neu erstellen (Volume bleibt)
        echo "▶ Alte Container entfernen (Volume $VOLUME_NAME bleibt erhalten)..."
        stop_all
        for c in bewerbungen-app bewerbungen-worker bewerbungen-email-service bewerbungen-imap-proxy bewerbungen-cron; do
            docker rm "$c" 2>/dev/null || true
        done
        echo "▶ Neue Container starten..."
        start_all
        echo "✓ Neustart mit aktuellem Image abgeschlossen"
        echo "  Image: $IMAGE"
        echo "  Volume: $VOLUME_NAME"
        ;;
    *)
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║  Bewerbungstracker Oracle VM Docker-Manager                ║"
        echo "║  $(basename "$0") <command>                                   ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        echo "  setup         Erstmalige Einrichtung (Config + Volume + Start)"
        echo "  start / stop  Alle Container starten/stoppen"
        echo "  restart       Alle Container neu starten (Volume bleibt)"
        echo "  rebuild       Container bei gleichem Image neu erstellen"
        echo "  status        Laufende Container anzeigen"
        echo "  volume-info   Volume-Details anzeigen"
        echo "  migrate [alt] Daten von altem Volume kopieren"
        echo "  logs [name]   Logs eines Containers (default: app)"
        echo ""
        echo "Volume: $VOLUME_NAME"
        echo "Netzwerk: $NETWORK_NAME"
        echo "Image: $IMAGE"
        ;;
esac
