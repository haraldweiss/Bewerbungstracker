#!/bin/bash
# Prüft ob der Ollama-Reverse-Tunnel auf VPS erreichbar ist.
# Bei Down: macOS-Notification + Versuch autossh neu zu starten.
LOG=~/Library/Logs/ollama-tunnel-monitor.log
STATE=~/Library/Logs/ollama-tunnel-monitor.state
TS=$(date '+%Y-%m-%d %H:%M:%S')

CODE=$(ssh -o BatchMode=yes -o ConnectTimeout=10 ionos-vps \
  "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:11434/api/tags" 2>/dev/null)

if [ "$CODE" = "200" ]; then
  PREV=$(cat "$STATE" 2>/dev/null)
  echo "ok" > "$STATE"
  if [ "$PREV" = "down" ]; then
    echo "[$TS] RECOVERED: Tunnel wieder up" >> "$LOG"
    osascript -e 'display notification "Ollama-Tunnel wieder up" with title "Tunnel Monitor" sound name "Glass"' 2>/dev/null
  fi
  exit 0
fi

echo "[$TS] DOWN: VPS curl returned '$CODE'" >> "$LOG"
echo "down" > "$STATE"

osascript -e 'display notification "Ollama-Tunnel zum VPS ist DOWN — versuche restart" with title "Tunnel Monitor" sound name "Sosumi"' 2>/dev/null

# Restart autossh LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.ai-provider.ollama-tunnel.plist 2>>"$LOG"
sleep 2
launchctl load ~/Library/LaunchAgents/com.ai-provider.ollama-tunnel.plist 2>>"$LOG"
echo "[$TS] autossh LaunchAgent reload triggered" >> "$LOG"
