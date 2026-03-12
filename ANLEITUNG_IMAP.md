# IMAP / POP3 Anleitung – Bewerbungs-Tracker
# IMAP / POP3 Guide – Job Application Tracker

---

## DEUTSCH

---

### Was ist der IMAP/POP3 Proxy?

Da Browser aus Sicherheitsgründen keine direkten Mail-Server-Verbindungen
aufbauen können, läuft ein kleines Python-Hilfsprogramm (`imap_proxy.py`)
lokal auf deinem Rechner. Es nimmt Anfragen vom Browser entgegen, verbindet
sich mit deinem Mail-Server und gibt die gefundenen Emails als JSON zurück.

**Dein Passwort verlässt deinen Rechner nie** – der Proxy ist ausschließlich
über `127.0.0.1:8765` (localhost) erreichbar. Kein externer Server ist
beteiligt.

---

### Voraussetzungen

| Anforderung        | Details                                              |
|--------------------|------------------------------------------------------|
| Python 3.9 oder neuer | Prüfen: `python3 --version` im Terminal          |
| Laufender Apache   | Bewerbungs-Tracker muss im Browser geöffnet sein     |
| Internetzugang     | Nur für die Verbindung zum Mail-Server               |

Alle nötigen Python-Module (`imaplib`, `poplib`, `ssl`, `http.server`) sind
im Python-Standard-Lieferumfang enthalten – kein `pip install` nötig.

---

### Schritt-für-Schritt Anleitung

#### Schritt 1 – Proxy starten

Terminal öffnen (z. B. über Spotlight: `Cmd + Leertaste` → „Terminal") und
folgenden Befehl eingeben:

```
python3 /Library/WebServer/Documents/Bewerbungstracker/imap_proxy.py
```

Erfolgreiche Ausgabe:

```
╔══════════════════════════════════════════════════╗
║   Bewerbungs-Tracker  IMAP/POP3 Proxy           ║
║   Läuft auf http://127.0.0.1:8765              ║
║   Stoppen: Strg+C                               ║
╚══════════════════════════════════════════════════╝
```

Das Terminal-Fenster **offen lassen** – der Proxy läuft nur solange das
Fenster aktiv ist. Mit `Strg + C` wird er gestoppt.

#### Schritt 2 – Im Browser öffnen

1. Bewerbungs-Tracker im Browser aufrufen
2. In der linken Seitenleiste auf **„📧 Gmail Connect"** klicken
3. Den Tab **„📮 IMAP / POP3"** auswählen
4. Der Status-Indikator sollte **✅ Proxy aktiv (Port 8765)** anzeigen

Falls der Status rot bleibt: Schritt 1 wiederholen, danach auf
**„🔍 Proxy-Status prüfen"** klicken.

#### Schritt 3 – Anbieter auswählen und verbinden

1. Im Dropdown **„E-Mail Anbieter"** den passenden Eintrag wählen.
   Server-Adresse und Port werden automatisch eingetragen.
2. **E-Mail-Adresse** eingeben (z. B. `dein@gmail.com`)
3. **Passwort** eingeben (siehe anbieter-spezifische Hinweise unten)
4. Optional: Maximale Anzahl abzurufender Emails anpassen (Standard: 50)
5. Auf **„🔌 Verbinden & Abrufen"** klicken

---

### Anbieter-spezifische Einstellungen

#### Gmail

Gmail erlaubt aus Sicherheitsgründen keine normalen Passwörter für
IMAP/POP3. Stattdessen wird ein **App-Passwort** benötigt.

**App-Passwort erstellen:**

1. Google-Konto öffnen: https://myaccount.google.com
2. Links auf **„Sicherheit"** klicken
3. Unter „Wie du dich bei Google anmeldest" auf
   **„2-Schritt-Verifizierung"** klicken und aktivieren (falls noch nicht aktiv)
4. Zurück zu „Sicherheit" → ganz unten **„App-Passwörter"** öffnen
   (erscheint erst nach Aktivierung der 2-Schritt-Verifizierung)
5. App: **„Mail"**, Gerät: **„Mac"** → **„Erstellen"**
6. Das angezeigte 16-stellige Passwort (z. B. `abcd efgh ijkl mnop`)
   kopieren und im Tracker einfügen – **dieses Passwort nur einmal anzeigen!**

**IMAP in Gmail aktivieren** (falls noch nicht aktiv):
Gmail → Einstellungen (Zahnrad) → „Alle Einstellungen aufrufen" →
Tab „Weiterleitung und POP/IMAP" → IMAP aktivieren → Speichern

| Einstellung      | Wert                  |
|------------------|-----------------------|
| Anbieter         | Gmail (IMAP)          |
| Server           | imap.gmail.com        |
| Port             | 993                   |
| Protokoll        | IMAP                  |
| Passwort         | App-Passwort (16 Zeichen) |

#### Outlook / Hotmail / Live

Normale Microsoft-Zugangsdaten funktionieren hier direkt.
Falls ein Microsoft-Konto mit 2FA verwendet wird, ggf. ein
App-Passwort über https://account.microsoft.com/security erstellen.

| Einstellung | Wert                        |
|-------------|-----------------------------|
| Anbieter    | Outlook / Hotmail / Live    |
| Server      | imap-mail.outlook.com       |
| Port        | 993                         |
| Protokoll   | IMAP                        |
| Passwort    | Microsoft-Passwort          |

#### Yahoo Mail

Yahoo erfordert ebenfalls ein App-Passwort.

**App-Passwort bei Yahoo erstellen:**
Yahoo-Konto → Kontosicherheit →
„App-Passwort generieren" → App: „Andere App" → Name vergeben → Generieren

| Einstellung | Wert                   |
|-------------|------------------------|
| Anbieter    | Yahoo Mail             |
| Server      | imap.mail.yahoo.com    |
| Port        | 993                    |
| Protokoll   | IMAP                   |
| Passwort    | App-Passwort           |

#### GMX

| Einstellung | Wert           |
|-------------|----------------|
| Anbieter    | GMX            |
| Server      | imap.gmx.net   |
| Port        | 993            |
| Protokoll   | IMAP           |
| Passwort    | GMX-Passwort   |

IMAP muss in den GMX-Einstellungen aktiviert sein:
E-Mail → Einstellungen → POP3/IMAP Abruf → IMAP aktivieren

#### WEB.DE

| Einstellung | Wert           |
|-------------|----------------|
| Anbieter    | WEB.DE         |
| Server      | imap.web.de    |
| Port        | 993            |
| Protokoll   | IMAP           |
| Passwort    | WEB.DE-Passwort |

#### Eigener Mail-Server

Bei selbst gehosteten Mail-Servern mit selbst-signiertem Zertifikat die
Checkbox **„Zertifikat nicht prüfen"** aktivieren. Für alle bekannten
Anbieter diese Option deaktiviert lassen.

---

### Sicherheitshinweise

- Das **Passwort wird niemals gespeichert** – weder im Browser (localStorage)
  noch in einer Datei. Es wird ausschließlich für die direkte Verbindung
  zum Mail-Server verwendet.
- Der Proxy antwortet nur auf `127.0.0.1` (Loopback) – kein anderer Rechner
  im Netzwerk kann ihn erreichen.
- Alle Mail-Server-Verbindungen erfolgen über **SSL/TLS** (Port 993/995).
- Der Proxy öffnet **nur lesenden Zugriff** (IMAP `readonly=True`,
  POP3 ohne `DELE`-Befehl) – keine Email wird verändert oder gelöscht.
- Es werden nur **Header-Daten** übertragen (Betreff, Absender, Datum) –
  keine Anhänge, kein vollständiger Email-Text.
- Fehlermeldungen vom Mail-Server werden vor der Anzeige von Passwörtern
  bereinigt.

---

### Konfiguration (config.json)

Der Proxy wird über eine `config.json` Datei konfiguriert. Alle Einstellungen sind **optional** – der Proxy
funktioniert auch ohne Config-Datei mit sensiblen Defaults.

**Konfigurierbare Werte:**

```json
{
  "server": {
    "host": "127.0.0.1",     // IP-Adresse (loopback, nicht ändern!)
    "port": 8765              // HTTP-Port für den Proxy
  },
  "connection": {
    "timeout_seconds": 20,    // Verbindungs-Timeout zum Mail-Server
    "fallback_days": 90       // Tage in der Vergangenheit für Fallback-Suche
  },
  "cache": {
    "ttl_seconds": 300        // Dauer, wie lange Responses gecacht werden (5 Min)
  },
  "search": {
    "keywords": [             // Keywords für Server-seitige Betreff-Suche
      "Bewerbung", "Application", "Stelle", "Interview",
      "Absage", "Zusage", "Job", "Recruiting", "Kandidat"
    ]
  }
}
```

**Beispiele für Anpassungen:**

*Beispiel 1: Anderer Port (z.B. für mehrere Instanzen)*
```json
{ "server": { "port": 8766 } }
```

*Beispiel 2: Längeres Timeout (für langsame Verbindungen)*
```json
{ "connection": { "timeout_seconds": 30 } }
```

*Beispiel 3: Custom Keywords für spezifische Branche*
```json
{
  "search": {
    "keywords": ["Engineering", "Developer", "Praktikum", "Senior", "Offer"]
  }
}
```

*Beispiel 4: Längeres Caching (für bessere Performance)*
```json
{
  "cache": {
    "ttl_seconds": 600    // 10 Minuten statt 5
  }
}
```

**Hinweise:**
- Nur geänderte Werte in config.json eintragen – alles andere nutzt Defaults
- Fehlerhafte JSON wird ignoriert, Proxy startet mit Defaults
- Keine Neustarts nötig bei Config-Änderungen (wird beim nächsten Request geladen)
- Port 8765 ist Standard – nur ändern wenn Port belegt ist

---

### Performance-Optimierungen (v3.2)

Der Proxy nutzt mehrere Techniken zur Performance-Verbesserung:

#### 1. Response-Caching (TTL-basiert)
- Wiederholte Anfragen mit gleichen Parametern werden aus dem Cache bedient
- **Cache-Key**: host:user:folder:limit:offset (keine Passwörter!)
- **Standard-TTL**: 5 Minuten (300 Sekunden) – konfigurierbar in config.json
- **Sicherheit**: Cache läuft nur während Proxy aktiv ist, wird bei Stopp geleert
- **Vorteil**: ~100x schneller bei Browser-Reload oder mehreren Tabs

#### 2. Batch-Fetching (IMAP)
- Statt Emails einzeln zu fetchen (50 Requests), werden alle auf einmal geholt (1 Request)
- **Vorteil**: ~80% schneller bei 50+ Emails, weniger Netzwerk-Overhead
- Transparent für User – keine Konfiguration nötig

#### 3. Pagination-Support
- Neuer Parameter `offset` in API für „Lazy Loading" im Frontend
- **Neue Response-Felder**:
  ```json
  {
    "status": "ok",
    "count": 20,         // Emails in dieser Response
    "total": 350,        // Gesamt-Email-Count
    "has_more": true,    // Sind mehr Emails verfügbar?
    "next_offset": 20,   // Nächster offset für Pagination
    "emails": [...]
  }
  ```
- **Vorteil**: Browser lädt nur erste 20 Emails statt alle 350 auf einmal

---

### Fehlerbehebung

| Problem | Mögliche Ursache | Lösung |
|---------|-----------------|--------|
| „Proxy nicht erreichbar" | Proxy nicht gestartet | `python3 imap_proxy.py` im Terminal ausführen |
| „Proxy nicht erreichbar" | Falscher Port belegt | Prüfen ob Port 8765 frei ist: `lsof -i :8765` |
| „Verbindung abgelehnt" | Falscher Server/Port | Anbieter-Voreinstellung wählen |
| „Mail-Server Fehler: … login …" | Falsches Passwort | App-Passwort prüfen (kein normales Passwort!) |
| „SSL-Zertifikat ungültig" | Selbst-signiertes Zertifikat | „Zertifikat nicht prüfen" aktivieren |
| „Timeout" | Mail-Server antwortet nicht | Internetzugang und Firewall prüfen |
| Keine Emails gefunden | Keywords passen nicht | Einstellungen → Keywords anpassen |
| Python nicht gefunden | Python nicht installiert | `brew install python3` (Homebrew) |

**Python-Version prüfen:**
```
python3 --version
```
Mindestens Python 3.9 wird benötigt.

**Port prüfen:**
```
lsof -i :8765
```
Ist der Port belegt, den Proxy stoppen (`Strg+C`) und neu starten.

---
---

## ENGLISH

---

### What Is the IMAP/POP3 Proxy?

Because browsers cannot open direct mail-server connections for security
reasons, a small Python helper (`imap_proxy.py`) runs locally on your
machine. It accepts requests from the browser, connects to your mail server,
and returns matching emails as JSON.

**Your password never leaves your machine** – the proxy is only reachable at
`127.0.0.1:8765` (localhost). No external server is involved.

---

### Prerequisites

| Requirement         | Details                                              |
|---------------------|------------------------------------------------------|
| Python 3.9 or newer | Check: `python3 --version` in Terminal               |
| Apache running      | The Job Tracker must be open in the browser          |
| Internet access     | Only for connecting to the mail server               |

All required Python modules (`imaplib`, `poplib`, `ssl`, `http.server`) are
part of the Python standard library – no `pip install` needed.

---

### Step-by-Step Instructions

#### Step 1 – Start the Proxy

Open Terminal (e.g. via Spotlight: `Cmd + Space` → "Terminal") and run:

```
python3 /Library/WebServer/Documents/Bewerbungstracker/imap_proxy.py
```

Expected output:

```
╔══════════════════════════════════════════════════╗
║   Bewerbungs-Tracker  IMAP/POP3 Proxy           ║
║   Läuft auf http://127.0.0.1:8765              ║
║   Stoppen: Strg+C                               ║
╚══════════════════════════════════════════════════╝
```

**Keep the Terminal window open** – the proxy only runs while the window
is active. Press `Ctrl + C` to stop it.

#### Step 2 – Open in the Browser

1. Open the Job Application Tracker in your browser
2. Click **"📧 Gmail Connect"** in the left sidebar
3. Select the **"📮 IMAP / POP3"** tab
4. The status indicator should show **✅ Proxy aktiv (Port 8765)**

If the status stays red: repeat Step 1, then click
**"🔍 Proxy-Status prüfen"**.

#### Step 3 – Select Provider and Connect

1. Choose your email provider in the **"E-Mail Anbieter"** dropdown.
   The server address and port are filled in automatically.
2. Enter your **email address** (e.g. `you@gmail.com`)
3. Enter your **password** (see provider-specific notes below)
4. Optionally adjust the maximum number of emails to fetch (default: 50)
5. Click **"🔌 Verbinden & Abrufen"**

---

### Provider-Specific Settings

#### Gmail

Gmail does not allow regular passwords for IMAP/POP3 access.
An **App Password** is required instead.

**Create an App Password:**

1. Open your Google Account: https://myaccount.google.com
2. Click **"Security"** in the left navigation
3. Under "How you sign in to Google", click
   **"2-Step Verification"** and enable it (if not already active)
4. Go back to "Security" → scroll down and open **"App passwords"**
   (only appears after 2-Step Verification is enabled)
5. App: **"Mail"**, Device: **"Mac"** → **"Create"**
6. Copy the displayed 16-character password (e.g. `abcd efgh ijkl mnop`)
   and paste it into the tracker – **this password is shown only once!**

**Enable IMAP in Gmail** (if not already active):
Gmail → Settings (gear icon) → "See all settings" →
"Forwarding and POP/IMAP" tab → Enable IMAP → Save

| Setting     | Value                     |
|-------------|---------------------------|
| Provider    | Gmail (IMAP)              |
| Server      | imap.gmail.com            |
| Port        | 993                       |
| Protocol    | IMAP                      |
| Password    | App Password (16 chars)   |

#### Outlook / Hotmail / Live

Regular Microsoft credentials work directly here.
If your Microsoft account uses 2FA, you may need to create an App Password
at https://account.microsoft.com/security.

| Setting  | Value                       |
|----------|-----------------------------|
| Provider | Outlook / Hotmail / Live    |
| Server   | imap-mail.outlook.com       |
| Port     | 993                         |
| Protocol | IMAP                        |
| Password | Microsoft password          |

#### Yahoo Mail

Yahoo also requires an App Password.

**Create an App Password in Yahoo:**
Yahoo Account → Account Security →
"Generate app password" → App: "Other app" → give it a name → Generate

| Setting  | Value                  |
|----------|------------------------|
| Provider | Yahoo Mail             |
| Server   | imap.mail.yahoo.com    |
| Port     | 993                    |
| Protocol | IMAP                   |
| Password | App Password           |

#### GMX

| Setting  | Value          |
|----------|----------------|
| Provider | GMX            |
| Server   | imap.gmx.net   |
| Port     | 993            |
| Protocol | IMAP           |
| Password | GMX password   |

IMAP must be enabled in GMX settings:
E-Mail → Settings → POP3/IMAP retrieval → Enable IMAP

#### WEB.DE

| Setting  | Value           |
|----------|-----------------|
| Provider | WEB.DE          |
| Server   | imap.web.de     |
| Port     | 993             |
| Protocol | IMAP            |
| Password | WEB.DE password |

#### Custom Mail Server

For self-hosted mail servers with a self-signed certificate, enable the
**"Zertifikat nicht prüfen"** ("Don't verify certificate") checkbox.
Leave this option disabled for all well-known providers.

---

### Security Notes

- Your **password is never stored** – not in the browser (localStorage)
  and not in any file. It is used solely for the direct connection to your
  mail server.
- The proxy only listens on `127.0.0.1` (loopback) – no other machine on
  your network can reach it.
- All mail-server connections use **SSL/TLS** (ports 993 / 995).
- The proxy only opens **read-only access** (IMAP `readonly=True`,
  POP3 without the `DELE` command) – no email is modified or deleted.
- Only **header data** is transferred (subject, sender, date) –
  no attachments, no full email body text.
- Error messages from the mail server are scrubbed of passwords before
  being displayed.

---

### Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| "Proxy nicht erreichbar" | Proxy not started | Run `python3 imap_proxy.py` in Terminal |
| "Proxy nicht erreichbar" | Port 8765 in use | Check: `lsof -i :8765` |
| "Verbindung abgelehnt" | Wrong server/port | Use the provider preset |
| "Mail-Server Fehler: … login …" | Wrong password | Check App Password (not your regular password!) |
| "SSL-Zertifikat ungültig" | Self-signed certificate | Enable "Zertifikat nicht prüfen" |
| "Timeout" | Mail server not responding | Check internet access and firewall |
| No emails found | Keywords don't match | Settings → adjust keywords |
| Python not found | Python not installed | `brew install python3` (Homebrew) |

**Check Python version:**
```
python3 --version
```
Python 3.9 or newer is required.

**Check if port is in use:**
```
lsof -i :8765
```
If the port is occupied, stop the proxy (`Ctrl+C`) and restart it.

---

### Frontend-Verbesserungen (v3.3)

#### 1. Passwort-Sichtbarkeits-Toggle
- 👁 Button neben dem Passwort-Feld zeigt/verbirgt das Passwort
- Sicher: Passwort wird nicht gespeichert, nur für Session verwendet

#### 2. Dark/Light-Mode Toggle
- 🌙 / ☀️ Button in der Header zum Umschalten zwischen Dark und Light Mode
- **LocalStorage**: Präferenz wird gespeichert und über Reload beibehalten
- Light Mode hat invertierte Farben: helle Hintergründe, dunkler Text

#### 3. Proxy-Status Indikator (erweitert)
- Zeigt Proxy-Verbindungsstatus: ✅ Aktiv / ❌ Nicht verbunden
- **Cache-Tracking**: Zeigt Anzahl der Cache-Hits seit Session-Start
- Grün (aktiv) / Rot (inaktiv)
- Update bei jedem IMAP-Request

---

*Bewerbungs-Tracker v3 – IMAP/POP3 Anleitung / Guide*
