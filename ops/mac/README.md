# Mac Operations Scripts

Operative Skripte und LaunchAgents für die zwei Macs (MacBook Pro + Mac mini),
die mit der Bewerbungstracker-VPS verbunden sind. Dies ist die Source-of-Truth —
die Dateien in `~/bin` und `~/Library/LaunchAgents` auf den Macs werden hier
hin abgeglichen.

## Struktur

```
ops/mac/
├── install.sh         # Smart-Installer (erkennt Host am Computer-Namen)
├── shared/            # Identisch auf beiden Macs
│   ├── bin/
│   │   ├── reactivate-tunnels.sh   (Helfer, MacBook-only deployed)
│   │   └── vps-watchdog.sh
│   └── LaunchAgents/
│       ├── de.haraldweiss.vps-watchdog.plist
│       └── de.haraldweiss.ollama-tunnel-monitor.plist
├── macbook/           # Nur MacBook (Tunnel auf VPS-Port 11434)
│   ├── bin/check-ollama-tunnel.sh        (checkt VPS:11434)
│   └── LaunchAgents/com.ai-provider.ollama-tunnel.plist  (-R 11434:127.0.0.1:11434)
└── mini/              # Nur Mini (Tunnel auf VPS-Port 11435)
    ├── bin/check-ollama-tunnel.sh        (checkt VPS:11435)
    └── LaunchAgents/com.ai-provider.ollama-tunnel.plist  (-R 11435:127.0.0.1:11434)
```

## Was die einzelnen Komponenten machen

| Datei | Zweck |
|---|---|
| `vps-watchdog.sh` + `de.haraldweiss.vps-watchdog.plist` | Prüft alle 5 Min VPS-Erreichbarkeit (curl + ping). Bei State-Change `down→up`: macOS-Notification + optional Ollama-Summary der IONOS-Status-Seite. |
| `com.ai-provider.ollama-tunnel.plist` | autossh-Reverse-Tunnel: macht lokales Ollama auf dem VPS unter `127.0.0.1:11434` (MacBook) bzw. `:11435` (Mini) erreichbar. KeepAlive=true. |
| `check-ollama-tunnel.sh` + `de.haraldweiss.ollama-tunnel-monitor.plist` | Prüft alle 5 Min ob der Tunnel funktioniert (SSH ins VPS + curl auf entsprechenden Port). Bei Fehler: unload+load des Tunnel-LaunchAgents + macOS-Notification. |
| `reactivate-tunnels.sh` | Helfer-Skript für nach VPS-Ausfällen: lädt alle relevanten LaunchAgents auf MacBook UND Mini (per SSH zum Mini) und macht Smoke-Test. |

## Erstinstallation auf einem Mac

```bash
git clone <repo>
cd Bewerbungstracker/ops/mac
./install.sh --load
```

Der Installer erkennt anhand des Computer-Namens (`scutil --get ComputerName`),
ob es ein MacBook oder Mini ist, und kopiert die passenden Dateien nach
`~/bin` und `~/Library/LaunchAgents`. Mit `--load` werden die LaunchAgents
direkt via `launchctl bootstrap` gestartet.

## Update nach Änderungen in diesem Ordner

Auf dem jeweiligen Mac:

```bash
cd /pfad/zum/repo/ops/mac
git pull
./install.sh        # neue Versionen kopieren
# LaunchAgents neu starten wenn deren plist geaendert wurde:
launchctl bootout gui/$(id -u)/<label>
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
```

## Voraussetzungen (manuell, nicht hier eingecheckt)

- `~/.ssh/config` muss einen Host-Alias `ionos-vps` definieren mit dem
  passenden Identity-File (siehe `reference_vps_ssh.md` im Memory).
- `brew install autossh`
- Lokales Ollama läuft auf `127.0.0.1:11434` (für die Tunnel) — typischerweise
  via `homebrew.mxcl.ollama` LaunchAgent (nicht hier verwaltet, ist Brew-default).
- Für `vps-watchdog.sh`: optionaler Ollama-Summary-Schritt nutzt Modell
  `llama3.1:8b-instruct-q5_K_M` — falls nicht installiert: `ollama pull llama3.1:8b-instruct-q5_K_M`.
  Fehlt das Modell, fällt die zweite Notification aus, der Watchdog läuft trotzdem.

## Verwandte Memory-Einträge

- `project_vps_watchdog_2026_05_22.md` — Hintergrund + Steuerung Watchdog
- `incident_claude_cost_burst_2026_05_14.md` — Warum es den Tunnel-Monitor gibt
- `incident_ollama_tunnel_2026_05_14.md` — Lehren aus Tunnel-Outage
