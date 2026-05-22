#!/bin/bash
# Watchdog: prueft VPS-Erreichbarkeit alle paar Minuten via launchd.
# Bei State-Change down -> up: macOS-Notification + Sound.
# Optional: Ollama-Zusammenfassung der IONOS-Status-Seite als zweite Notification.
#
# Logs:  ~/Library/Logs/vps-watchdog.log
# State: ~/Library/Logs/vps-watchdog.state  (Inhalt: "up" oder "down")

set -u

LOG=~/Library/Logs/vps-watchdog.log
STATE=~/Library/Logs/vps-watchdog.state
TS=$(date '+%Y-%m-%d %H:%M:%S')
VPS_HOST="bewerbungen.wolfinisoftware.de"
VPS_IP="bewerbungen.wolfinisoftware.de"
OLLAMA_MODEL="llama3.1:8b-instruct-q5_K_M"

# --- Probe ---
HTTP=$(curl -sS -o /dev/null -m 8 -w "%{http_code}" "https://${VPS_HOST}/" 2>/dev/null)
HTTP=${HTTP:-000}
if ping -c 1 -W 2000 "$VPS_IP" >/dev/null 2>&1; then
    PING=ok
else
    PING=fail
fi

# UP wenn HTTPS irgendwie antwortet. IONOS blockt offenbar ICMP, daher
# Ping nur informativ - HTTP != 000 ist das verlaessliche Recovery-Signal.
if [ "$HTTP" != "000" ]; then
    CUR=up
else
    CUR=down
fi

PREV=$(cat "$STATE" 2>/dev/null || echo "unknown")
echo "$CUR" > "$STATE"
echo "[$TS] state=$CUR (http=$HTTP ping=$PING) prev=$PREV" >> "$LOG"

# --- State-Change-Handling ---
if [ "$CUR" = up ] && [ "$PREV" != up ]; then
    osascript -e 'display notification "VPS ist wieder erreichbar - autossh-Tunnel jetzt reaktivierbar mit ~/bin/reactivate-tunnels.sh" with title "VPS RECOVERED" sound name "Hero"'
    echo "[$TS] *** RECOVERED ***" >> "$LOG"

    # Optional: Ollama-Summary der IONOS-Status-Seite
    if curl -sS -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        PAGE=$(curl -sS -m 8 https://www.ionos-status.de/ 2>/dev/null \
            | tr -d '\n' | sed 's/<[^>]*>/ /g; s/  */ /g' | head -c 4000)
        if [ -n "$PAGE" ]; then
            PROMPT_JSON=$(python3 -c "
import json, sys
text = sys.argv[1]
prompt = f'Fasse den aktuellen IONOS-Stoerungs-Status in 1-2 deutschen Saetzen zusammen. Antworte nur mit der Zusammenfassung, kein Kommentar.\n\nText von der Status-Seite:\n{text}'
print(json.dumps({'model': sys.argv[2], 'prompt': prompt, 'stream': False, 'options': {'num_predict': 120}}))
" "$PAGE" "$OLLAMA_MODEL" 2>/dev/null)

            SUMMARY=$(curl -sS -m 30 http://127.0.0.1:11434/api/generate \
                -H "Content-Type: application/json" \
                -d "$PROMPT_JSON" 2>/dev/null \
                | python3 -c "import sys,json; print(json.load(sys.stdin).get('response','').strip())" 2>/dev/null)

            if [ -n "$SUMMARY" ]; then
                # Notification-Text auf ~200 Zeichen kuerzen, Anfuehrungszeichen escapen
                SAFE=$(echo "$SUMMARY" | tr '\n' ' ' | head -c 200 | sed 's/"/\\"/g')
                osascript -e "display notification \"$SAFE\" with title \"IONOS Status (Ollama)\""
                echo "[$TS] ollama-summary: $SUMMARY" >> "$LOG"
            fi
        fi
    fi

elif [ "$CUR" = down ] && [ "$PREV" = up ]; then
    osascript -e 'display notification "VPS antwortet nicht mehr" with title "VPS DOWN" sound name "Basso"'
    echo "[$TS] *** WENT DOWN ***" >> "$LOG"
fi

exit 0
