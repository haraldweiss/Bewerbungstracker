#!/bin/bash
# Reaktiviert die Ollama-Reverse-Tunnel + Monitore auf MacBook und Mac mini
# nach einem VPS-Ausfall. Idempotent: bereits geladene LaunchAgents werden
# uebersprungen.
#
# Usage: ~/bin/reactivate-tunnels.sh

set -u

VPS_HOST="bewerbungen.wolfinisoftware.de"
MINI_HOST="haraldweiss@mac-mini-von-harald-2.local"

bootstrap_one () {
    local plist="$1"
    local label
    label=$(basename "$plist" .plist)
    if launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$label"; then
        echo "  - $label: bereits geladen, ueberspringe"
        return 0
    fi
    if launchctl bootstrap "gui/$(id -u)" "$plist" 2>&1; then
        echo "  - $label: geladen"
    else
        echo "  - $label: FEHLER beim Laden"
    fi
}

echo "=== VPS-Erreichbarkeit ==="
HTTP=$(curl -sS -o /dev/null -m 8 -w "%{http_code}" "https://${VPS_HOST}/" 2>/dev/null || echo "000")
echo "  HTTPS ${VPS_HOST}: ${HTTP}"
if [ "$HTTP" = "000" ]; then
    echo "  WARN: VPS noch nicht erreichbar - autossh wird beim ersten Start warten."
fi

echo ""
echo "=== MacBook: LaunchAgents laden ==="
bootstrap_one ~/Library/LaunchAgents/com.ai-provider.ollama-tunnel.plist
bootstrap_one ~/Library/LaunchAgents/de.haraldweiss.ollama-tunnel-monitor.plist

echo ""
echo "=== Mac mini: LaunchAgents laden ==="
ssh -o ConnectTimeout=5 "$MINI_HOST" 'bash -s' <<'REMOTE'
bootstrap_one () {
    local plist="$1"
    local label
    label=$(basename "$plist" .plist)
    if launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$label"; then
        echo "  - $label: bereits geladen, ueberspringe"
        return 0
    fi
    if launchctl bootstrap "gui/$(id -u)" "$plist" 2>&1; then
        echo "  - $label: geladen"
    else
        echo "  - $label: FEHLER beim Laden"
    fi
}
bootstrap_one ~/Library/LaunchAgents/com.ai-provider.ollama-tunnel.plist
bootstrap_one ~/Library/LaunchAgents/de.haraldweiss.ollama-tunnel-monitor.plist
REMOTE

sleep 3

echo ""
echo "=== Verifikation MacBook ==="
launchctl list | grep -E 'tunnel|autossh' | awk '{print "  " $0}' || echo "  (keine Eintraege)"
pgrep -lf autossh | awk '{print "  pid=" $1 " " $2}' || echo "  (kein autossh-Prozess)"

echo ""
echo "=== Verifikation Mac mini ==="
ssh -o ConnectTimeout=5 "$MINI_HOST" '
launchctl list | grep -E "tunnel|autossh" | awk "{print \"  \" \$0}" || echo "  (keine Eintraege)"
pgrep -lf autossh | awk "{print \"  pid=\" \$1 \" \" \$2}" || echo "  (kein autossh-Prozess)"
'

echo ""
echo "=== Smoke-Test: Ollama auf VPS via Tunnel ==="
if ssh -o ConnectTimeout=5 ionos-vps "
    printf '  MacBook (:11434): '
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:11434/api/tags || echo 'fail'
    printf '  Mini    (:11435): '
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:11435/api/tags || echo 'fail'
" 2>/dev/null; then
    :
else
    echo "  VPS-SSH noch nicht moeglich - Smoke-Test uebersprungen"
fi

echo ""
echo "Fertig. 200 = Tunnel funktioniert."
