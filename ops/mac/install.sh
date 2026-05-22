#!/bin/bash
# Installiert die Mac-ops-Skripte und LaunchAgents fuer diesen Host.
# Erkennt den Host am Computer-Namen und kopiert die passenden Dateien
# aus shared/ + macbook|mini/ nach ~/bin und ~/Library/LaunchAgents.
#
# Optional --load: laedt die LaunchAgents am Ende via launchctl bootstrap.
#
# Idempotent: bestehende Dateien werden ueberschrieben, geladene LaunchAgents
# uebersprungen.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=$(scutil --get ComputerName 2>/dev/null || hostname)

case "$NAME" in
    *"MacBook"*|*"macbook"*)
        HOST_DIR="macbook"
        ;;
    *"mini"*|*"Mini"*)
        HOST_DIR="mini"
        ;;
    *)
        echo "FEHLER: Unbekannter Host '$NAME' - erwartet 'MacBook' oder 'Mini' im Computer-Namen."
        echo "Computer-Namen pruefen: scutil --get ComputerName"
        exit 1
        ;;
esac

echo "Host erkannt: $NAME -> Profile '$HOST_DIR'"

mkdir -p ~/bin ~/Library/LaunchAgents ~/Library/Logs

copy_dir () {
    local src="$1" dst="$2"
    [ -d "$src" ] || return 0
    for f in "$src"/*; do
        [ -f "$f" ] || continue
        local base
        base=$(basename "$f")
        cp "$f" "$dst/$base"
        [[ "$f" == *.sh ]] && chmod +x "$dst/$base"
        echo "  $dst/$base"
    done
}

echo ""
echo "=== Kopiere shared/ ==="
copy_dir "$HERE/shared/bin"          ~/bin
copy_dir "$HERE/shared/LaunchAgents" ~/Library/LaunchAgents

echo ""
echo "=== Kopiere ${HOST_DIR}/ ==="
copy_dir "$HERE/${HOST_DIR}/bin"          ~/bin
copy_dir "$HERE/${HOST_DIR}/LaunchAgents" ~/Library/LaunchAgents

# Auf Mini: reactivate-tunnels.sh wird nicht benoetigt (laeuft nur vom MacBook
# aus, weil es per ssh den Mini steuert). Entfernen wenn vorhanden.
if [ "$HOST_DIR" = "mini" ] && [ -f ~/bin/reactivate-tunnels.sh ]; then
    rm ~/bin/reactivate-tunnels.sh
    echo "  (entfernt: ~/bin/reactivate-tunnels.sh - nur auf MacBook noetig)"
fi

if [[ "${1:-}" == "--load" ]]; then
    echo ""
    echo "=== LaunchAgents laden ==="
    for plist in ~/Library/LaunchAgents/de.haraldweiss.*.plist \
                 ~/Library/LaunchAgents/com.ai-provider.ollama-tunnel.plist; do
        [ -f "$plist" ] || continue
        label=$(basename "$plist" .plist)
        if launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$label"; then
            echo "  $label: bereits geladen, ueberspringe"
            continue
        fi
        launchctl bootstrap "gui/$(id -u)" "$plist" 2>&1 && \
            echo "  $label: geladen" || \
            echo "  $label: FEHLER"
    done
fi

echo ""
echo "Fertig. (--load uebergeben, um die LaunchAgents direkt zu starten)"
