# 🚀 Deployment auf wolfinisoftware.de

Dieses Dokument beschreibt, wie man den Bewerbungstracker mit Login-Authentifizierung auf wolfinisoftware.de deployed.

## Voraussetzungen

- Domain `wolfinisoftware.de` mit vollständigem Zugriff (SSH/FTP)
- Python 3.7+ auf dem Server installiert
- Nginx oder Apache als Reverse Proxy
- ~50MB Speicherplatz (Frontend + Backend + SQLite-DB)

## Installation Steps

### 1. Code auf den Server uploaden

```bash
# Lokal: Alle Dateien ausser .git in einen Ordner packen
cd /Library/WebServer/Documents/Bewerbungstracker
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    -czf bewerbungstracker.tar.gz .

# Zu Server uploaden (z.B. via SCP oder Cyberduck)
scp bewerbungstracker.tar.gz user@wolfinisoftware.de:/var/www/tracker/
```

### 2. Server-Seite: Code entpacken und Setup

```bash
# SSH auf Server
ssh user@wolfinisoftware.de

# Ordner erstellen & entpacken
mkdir -p /var/www/tracker
cd /var/www/tracker
tar -xzf bewerbungstracker.tar.gz
rm bewerbungstracker.tar.gz

# Python-Dependencies installieren
pip3 install flask flask-cors

# Permissions setzen
chmod 755 /var/www/tracker
chmod 644 /var/www/tracker/app.py
chmod 644 /var/www/tracker/index.html
```

### 3. Nginx als Reverse Proxy konfigurieren

Erstelle `/etc/nginx/sites-available/tracker`:

```nginx
server {
    listen 80;
    server_name tracker.wolfinisoftware.de;

    # Optional: Redirect auf HTTPS (empfohlen!)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Dann aktivieren:
```bash
sudo ln -s /etc/nginx/sites-available/tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. App mit Supervisor im Hintergrund starten

Erstelle `/etc/supervisor/conf.d/bewerbungstracker.conf`:

```ini
[program:bewerbungstracker]
directory=/var/www/tracker
command=python3 app.py
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/bewerbungstracker.log
environment=PORT=8000,AUTH_USERNAME=admin,AUTH_PASSWORD=dein-sicheres-passwort
```

Dann:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start bewerbungstracker
```

### 5. Login-Credentials anpassen

**Wichtig**: Standard-Credentials sind:
- Benutzername: `admin`
- Passwort: `password123`

Diese MÜSSEN geändert werden!

```bash
# /etc/supervisor/conf.d/bewerbungstracker.conf ändern:
# environment=AUTH_USERNAME=dein-username,AUTH_PASSWORD=dein-super-sicheres-passwort

sudo supervisorctl restart bewerbungstracker
```

## HTTPS Setup (empfohlen!)

Mit Let's Encrypt:
```bash
sudo certbot --nginx -d tracker.wolfinisoftware.de
```

## Daten-Persistenz

SQLite-DB speichert automatisch in `bewerbungen.db`.

**Backups:**
```bash
# Tägliches Backup
0 2 * * * cp /var/www/tracker/bewerbungen.db /backup/bewerbungen_$(date +\%Y\%m\%d).db
```

## API-Endpoints

```bash
# Login
curl -X POST https://tracker.wolfinisoftware.de/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"dein-passwort"}'

# Logout
curl -X POST -H "Authorization: Bearer TOKEN" \
  https://tracker.wolfinisoftware.de/api/auth/logout
```

## Troubleshooting

- Port belegt? `lsof -i :8000`
- Flask läuft? `sudo supervisorctl status bewerbungstracker`
- Logs? `tail -f /var/log/bewerbungstracker.log`
- DB-Fehler? `chmod 666 /var/www/tracker/bewerbungen.db`
