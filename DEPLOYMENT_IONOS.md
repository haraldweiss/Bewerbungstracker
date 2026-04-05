# 🚀 Deployment auf IONOS Shared-Hosting

**Basis-URL:** `/kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker`
**Server-IP:** `82.165.88.152`

Dies ist eine spezialisierte Anleitung für IONOS **Shared-Hosting** mit SSH-Zugriff.

## ⚠️ Wichtig: Python auf Shared-Hosting

IONOS Shared-Hosting hat **keine nativen persistenten Python-Prozesse**. Die beste Lösung ist:

### ✅ EMPFOHLEN: SSH-basiertes Starten (diese Anleitung)
- Flask läuft auf Port 8080
- Wird via SSH gestartet und in der Session gehalten
- Einfach zu testen und zu debuggen
- Perfekt für Entwicklung und kleine Nutzung

---

## 🚀 Schnellstart (empfohlen)

### Schritt 1: Verbinde via SSH

```bash
ssh ionos-webspace
```

Falls du keinen SSH-Host konfiguriert hast:
```bash
ssh -i ~/.ssh/id_rsa_webspace u111662521@82.165.88.152
```

### Schritt 2: Starte die App

```bash
cd /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker
bash start-on-ionos.sh
```

### Schritt 3: Öffne die App

**Lokal auf dem Server:**
```
http://localhost:8080
```

**Von außen (vom Browser):**
```
http://82.165.88.152:8080
```

### Schritt 4: Login

**Standard-Admin Login:**
- **Benutzername:** `admin`
- **Passwort:** `password123`

⚠️ **WICHTIG:** Ändere diese Credentials sofort!

---

## 🔌 Langfristiges Hosting (Option 2: Screen/Tmux)

Falls die SSH-Session öfter unterbrochen wird, nutze `screen`:

```bash
# Neue Screen-Session starten
screen -S bewerbungstracker

# Innerhalb der Session:
cd /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker
bash start-on-ionos.sh

# Dann: Ctrl+A, dann D zum Detachieren
# Später erneut verbinden:
# screen -r bewerbungstracker
```

Dadurch läuft die App weiter, auch wenn du dich abmeldest!

---

## 💡 Für echte Production: VPS oder Upgrade

Falls die App ständig laufen soll ohne SSH:

### Option A: IONOS VPS
- Volle Python/Systemd-Unterstützung
- Supervisor oder systemd für Auto-Restart
- Siehe `DEPLOYMENT.md` für VPS-Setup

### Option B: Externer Hosting-Service
- Heroku, Railway, Render, etc.
- Verbesserter "One-Click" Python-Support
- Siehe Dokumentation dieser Services

---

## 🔐 Credentials & Sicherheit

### 1. Standard-Admin ändern

Nach dem ersten Login (**WICHTIG!**):

1. Öffne die App: `http://82.165.88.152:8080`
2. Melde dich mit `admin` / `password123` an
3. Klick auf `👥 Nutzer-Management`
4. Bearbeite Admin-User und ändere Passwort
5. Erstelle neue Benutzer für Team-Mitglieder

### 2. Eigene SSH-Key für Deployment (optional)

Falls mehrere Personen deployen sollen, konfiguriere SSH-Keys in `~/.ssh/config`:

```bash
Host ionos-bewerbungstracker
    HostName 82.165.88.152
    User u111662521
    IdentityFile ~/.ssh/id_rsa_ionos
```

Dann: `ssh ionos-bewerbungstracker`

---

## 👥 User-Management

**Neue Benutzer erstellen:**
1. Als Admin anmelden (`admin` / `password123` initial)
2. Navigiere zu `👥 Nutzer-Management` (nur für Admins sichtbar)
3. Klick `+ Neuer Nutzer`
4. Fülle Benutzername, Email, Passwort aus
5. Speichern
6. Teile Credentials mit dem Benutzer

**Multi-Tenant Features:**
- Jeder Benutzer sieht nur seine eigenen Bewerbungen
- Admin sieht alle Bewerbungen aller Benutzer
- Admin kann Benutzer bearbeiten/löschen

---

## 🗄️ Datenbank-Verwaltung

Die SQLite-Datenbank (`bewerbungen.db`) wird automatisch erstellt beim Start.

**Regelmäßige Backups:**

1. **via SSH (lokal):**
   ```bash
   scp ionos-webspace:/kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker/bewerbungen.db ~/backup/bewerbungen_$(date +%Y%m%d).db
   ```

2. **via IONOS Control Panel:**
   - Dateimanager → `bewerbungen.db` → Download
   - Speichere regelmäßig lokal (z.B. wöchentlich)

3. **Automatisches Backup via Cron (falls Cron verfügbar):**
   ```bash
   # via SSH:
   crontab -e

   # Dann hinzufügen:
   0 2 * * * cp /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker/bewerbungen.db /home/u111662521/backups/bewerbungen_$(date +\%Y\%m\%d).db
   ```

---

## 🔗 URL-Struktur

Wenn Flask läuft (Port 8080):
```
Homepage:   http://82.165.88.152:8080/
API:        http://82.165.88.152:8080/api/*
Login:      POST /api/auth/login
Status:     GET /api/auth/status
Users:      GET/POST/PUT/DELETE /api/admin/users (nur Admin)
Logout:     POST /api/auth/logout

Lokal (via SSH):
Homepage:   http://localhost:8080/
```

⚠️ **Hinweis:** Diese IP-Adresse ist dynamisch! Für stabilen Zugang: Verwende DNS-Name oder konfiguriere Port-Forwarding.

---

## ⚠️ Troubleshooting

### Problem: App startet nicht / zeigt Fehler

**Schritt 1:** Überprüfe direkt, ob die Dependencies installiert sind:
```bash
ssh ionos-webspace
python3 -m pip list | grep -i flask
```

Sollte zeigen:
```
Flask                    2.x.x
Flask-CORS              3.x.x
```

Falls nicht vorhanden:
```bash
pip3 install --user flask flask-cors
```

### Problem: "Port 8080 is already in use"

```bash
# Prozess auf Port 8080 finden:
ssh ionos-webspace
lsof -i :8080

# Process killen:
kill -9 <PID>

# Oder anderen Port nutzen, z.B. 8081:
cd /kunden/homepages/.../Bewerbungstracker
python3 app.py --port 8081
```

### Problem: "no such table: users" oder "no such column: user_id"

Die Datenbank ist veraltet. Alle Tabellen müssen neu erstellt werden:

```bash
ssh ionos-webspace
cd /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker

# Alte Datenbank löschen (BACKUP zuerst!)
cp bewerbungen.db bewerbungen.db.backup
rm bewerbungen.db

# App neu starten - erstellt neue DB:
python3 app.py
```

### Problem: Datenbank-Fehler "database is locked"

```bash
# Mehrere Flask-Prozesse laufen? Alle killen:
ssh ionos-webspace
pkill -f "python3 app.py"

# Lockfile entfernen (falls vorhanden):
rm /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker/bewerbungen.db-journal

# Neu starten:
bash start-on-ionos.sh
```

### Problem: "ModuleNotFoundError: No module named 'flask'"

Flask nicht installiert:
```bash
ssh ionos-webspace
pip3 install --user flask flask-cors werkzeug
```

### Problem: Login funktioniert nicht

1. Überprüfe Login-Daten: Admin / password123
2. Überprüfe Datenbank: Hat Nutzer-Tabelle die richtigen Daten?
   ```bash
   ssh ionos-webspace
   sqlite3 bewerbungen.db "SELECT username, is_admin FROM users;"
   ```

3. Falls Nutzer leer: Neue Benutzer über UI erstellen

---

## 🆘 Wenn SSH/Python nicht funktioniert

Falls die SSH-Methode nicht funktioniert:

1. **IONOS Support fragen:**
   - "Kann ich Python-Anwendungen auf meinem Shared-Hosting laufen lassen?"
   - "Gibt es Python-Application-Support (z.B. via Plesk)?"
   - "Kann ich auf einen VPS upgraden für bessere Python-Unterstützung?"

2. **Alternativen:**
   - **IONOS VPS:** Vollständige Python-Unterstützung mit Systemd
   - **Heroku/Railway/Render:** "One-Click" Python-Deployment
   - **Docker-Hosting:** Für containerisierte Deployment

3. **Upgrade-Empfehlung für echte Production:**
   - IONOS VPS mit Ubuntu 20.04+
   - Systemd Service für Auto-Restart
   - Nginx Reverse Proxy
   - Let's Encrypt SSL

---

## 📊 Performance & Limitierungen

Shared-Hosting hat **natürliche Limitierungen:**
- CPU: Geteilt mit anderen Nutzern
- RAM: Oft 256MB-512MB gesamt
- I/O: Gedrosselt

**Was funktioniert gut:**
- ✅ Kleine Teams (1-5 Personen)
- ✅ <100 Bewerbungen
- ✅ Gelegenheitliche Nutzung
- ✅ Entwicklung & Testing

**Was kann problematisch sein:**
- ❌ Große Excel-Importe (>1000 Zeilen)
- ❌ 24/7 Verfügbarkeit ohne SSH-Session
- ❌ High-Traffic-Szenarien
- ❌ Automatische Email-Synchronisierung

**Optimierungen:**
1. Regelmäßige Backups erstellen
2. Große Dateien nicht gleichzeitig hochladen
3. Bei 24/7 Bedarf: VPS upgraden

---

## ✅ Deployment-Checkliste

### Vorbereitung:
- [ ] SSH-Zugang getestet: `ssh ionos-webspace`
- [ ] Python 3.9+ vorhanden: `python3 --version`
- [ ] Flask installiert: `pip3 list | grep -i flask`

### Start:
- [ ] Startup-Script vorhanden: `start-on-ionos.sh`
- [ ] App startet ohne Fehler
- [ ] Port 8080 antwortet: `http://82.165.88.152:8080`

### Sicherheit:
- [ ] Admin-Password geändert (nicht `password123`!)
- [ ] Neue Benutzer für Team erstellt
- [ ] Datenbank-Backup erstellt
- [ ] SSH-Keys gesichert

### Funktionalität:
- [ ] Login funktioniert
- [ ] 👥 Nutzer-Management sichtbar für Admin
- [ ] Neue Bewerbung erstellen funktioniert
- [ ] Multi-Tenant: User A sieht nur User A's Bewerbungen

### Optional (für Production):
- [ ] Cron-Backup konfiguriert
- [ ] Screen/Tmux Session für kontinuierliche Nutzung
- [ ] Regelmäßige manuelle Backups geplant

---

## 📞 Quick-Anleitung (TL;DR)

```bash
# 1. Verbinde via SSH
ssh ionos-webspace

# 2. Starte die App
cd /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker
bash start-on-ionos.sh

# 3. Öffne im Browser
# http://82.165.88.152:8080

# 4. Login
# Benutzer: admin
# Passwort: password123

# 5. ändere Admin-Passwort!
# → 👥 Nutzer-Management → Admin bearbeiten
```

---

## 📚 Weitere Dokumentation

- `DEPLOYMENT.md` → VPS/Linux-Deployment
- `STARTUP_GUIDE.md` → Allgemeine Feature-Dokumentation
- `README.md` → Projektübersicht
- `.claude/plans/` → Implementierungsdetails
