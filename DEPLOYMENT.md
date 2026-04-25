# Deployment Guide

Dieses Dokument beschreibt zwei parallele Deployment-Profile:

- **A) Lokales Setup** – ein Mac/Linux-Rechner, alle Services auf `localhost`.
- **B) VPS Production** – z.B. IONOS VPS mit Apache, Let's Encrypt, gunicorn,
  systemd, SELinux.

Die Codebase enthält **dieselben Quellen für beide Profile**. Unterschiede
liegen ausschließlich in `.env`-Werten, systemd-Units, Apache-vhost und
SELinux-Contexts.

---

## A) Lokales Setup

Vorausgesetzt: Python ≥ 3.9, Git.

```bash
git clone <repo-url> bewerbungstracker
cd bewerbungstracker

# 1) venv + Pakete
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2) .env anlegen
cp .env.example .env
# In .env editieren:
#   FLASK_ENV=development
#   APP_URL=http://localhost:8080
#   CORS_ORIGINS=http://localhost:3000,http://localhost:8080
#   JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
#   MAIL_USERNAME=… MAIL_PASSWORD=…   # SMTP, falls Confirmation-Mails getestet werden

# 3) DB-Schema
python -m alembic upgrade head      # erstellt instance/bewerbungstracker.db
python scripts/create_user.py --email du@example.com --admin --auto-confirm

# 4) Services starten (3 Terminals oder per ./start.sh)
./start.sh
# startet: Flask (Port 8080), imap_proxy.py (8765), email_service.py (8766)
```

**Frontend öffnen:** `http://localhost:8080` – das Frontend erkennt
automatisch, dass `location.hostname` lokal ist und ruft `127.0.0.1:8765/8766`
direkt an.

---

## B) VPS / Production (IONOS oder vergleichbar)

### B1. Einmal-Setup auf dem Server

```bash
# Voraussetzung: root oder sudo, Python 3.9+, httpd, certbot
sudo dnf install -y python3 python3-venv httpd mod_ssl certbot python3-certbot-apache

# Code klonen
sudo mkdir -p /var/www/bewerbungen
sudo chown -R $USER:$USER /var/www/bewerbungen
git clone <repo-url> /var/www/bewerbungen
cd /var/www/bewerbungen

# venv (auf dem Server, nicht vom Mac übertragen!)
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Logs + Instance-Verzeichnis
sudo mkdir -p /var/log/bewerbungen /var/www/bewerbungen/instance
sudo chown -R root:root /var/log/bewerbungen
```

### B2. Konfiguration

```bash
# .env (chmod 600, enthält Secrets)
sudo cp .env.example /var/www/bewerbungen/.env
sudo $EDITOR /var/www/bewerbungen/.env
# Einstellen:
#   FLASK_ENV=production
#   APP_URL=https://bewerbungen.deinedomain.de
#   CORS_ORIGINS=https://bewerbungen.deinedomain.de,https://bewerbung.deinedomain.de
#   JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
#   MAIL_SERVER=smtp.ionos.de  MAIL_PORT=465  MAIL_USERNAME=...  MAIL_PASSWORD=...
sudo chmod 600 /var/www/bewerbungen/.env
```

### B3. SELinux (nur RHEL/Rocky/CentOS)

Pflichtschritt – sonst bekommt SQLAlchemy `attempt to write a readonly database`:

```bash
sudo chcon -R -t httpd_sys_rw_content_t /var/www/bewerbungen/instance/
sudo chcon -t httpd_sys_rw_content_t /var/www/bewerbungen/email_config.db || true
```

### B4. systemd-Services

```bash
sudo cp deploy/systemd/bewerbungen.service /etc/systemd/system/
sudo cp deploy/systemd/imap-proxy.service /etc/systemd/system/
sudo cp deploy/systemd/email-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bewerbungen imap-proxy email-service
sudo systemctl status bewerbungen imap-proxy email-service
```

### B5. Apache vhost + SSL

```bash
# vhost installieren
sudo cp deploy/apache/bewerbungen.conf /etc/httpd/conf.d/
sudo $EDITOR /etc/httpd/conf.d/bewerbungen.conf
# Hostnames im ServerName / ServerAlias / SSLCertificateFile anpassen

# DocumentRoot für ACME-Challenge
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo apachectl configtest
sudo systemctl reload httpd

# SSL-Cert (zwei Hostnames – Plural + Singular sind eine gute Praxis)
sudo certbot certonly --webroot -w /var/www/html \
    -d bewerbungen.deinedomain.de \
    -d bewerbung.deinedomain.de \
    --agree-tos -m admin@deinedomain.de
sudo systemctl reload httpd
```

### B6. DB-Schema

```bash
cd /var/www/bewerbungen
sudo -u root venv/bin/python -m alembic upgrade head
sudo -u root venv/bin/python scripts/create_user.py \
    --email harald@example.com --admin --auto-confirm
```

### B7. Verifikation

```bash
curl -sI https://bewerbungen.deinedomain.de/                            # 200
curl -s  https://bewerbungen.deinedomain.de/api/auth/me                  # 401 ohne Token
curl -s  https://bewerbungen.deinedomain.de/email-service/api/status     # 200
curl -s -X POST https://bewerbungen.deinedomain.de/imap-proxy/ -d '{}'   # 400 (no body)
```

---

## C) Architektur-Übersicht

| Komponente | Lokal | VPS (Production) |
|---|---|---|
| Flask-App | `python app.py` (Port 8080) | gunicorn 127.0.0.1:5000 (systemd) |
| imap_proxy.py | `python imap_proxy.py` (8765) | systemd `imap-proxy` (8765) |
| email_service.py | `python email_service.py` (8766) | systemd `email-service` (8766) |
| TLS / Routing | nicht nötig | Apache 443 → reverse-proxy |
| Frontend-URL für Services | `http://127.0.0.1:8765/6` | `/imap-proxy`, `/email-service` |
| Auth-Backend | bcrypt + JWT | identisch |
| Encryption | Envelope-Encryption (DEK + KEK) | identisch |
| SMTP für Confirmation-Mails | Flask-Mail (.env) | identisch |

Frontend-Auto-Detect (siehe `index.html`):

```js
const _isLocalSetup = ['localhost','127.0.0.1',''].includes(location.hostname);
const EMAIL_SERVICE_URL = _isLocalSetup ? 'http://127.0.0.1:8766' : '/email-service';
const IMAP_PROXY        = _isLocalSetup ? 'http://127.0.0.1:8765' : '/imap-proxy';
```

---

## D) Was im Repo steht vs. was nicht

**Universal (im Git):**

- gesamter Python-, JS-, HTML-Code
- `alembic/versions/*.py` (Schema-Migrationen)
- `requirements.txt`
- `deploy/systemd/*.service`, `deploy/apache/bewerbungen.conf` (Templates)
- `scripts/create_user.py`, `scripts/migrate_legacy_data.py`,
  `scripts/reconcile_localstorage.py`
- `.env.example`, `DEPLOYMENT.md`

**Per-Deployment, NICHT im Git** (`.gitignore` deckt das ab):

- `.env` (Secrets!)
- `instance/bewerbungstracker.db` (User-Daten)
- `email_config.db` (verschlüsselte SMTP/IMAP-Credentials)
- `venv/` (Python-venv – muss pro Host neu erzeugt werden, da plattformabhängig)
- `*.deprecated`, `*.bak` (lokale Sicherungen)

**Nicht im Git, in `deploy/` aber Template:**

- systemd-Units (real liegen sie in `/etc/systemd/system/`)
- Apache vhost (real liegt in `/etc/httpd/conf.d/`)

---

## E) Häufige Stolpersteine

| Symptom | Ursache | Fix |
|---|---|---|
| `attempt to write a readonly database` | SELinux blockt schreiben | `chcon -R -t httpd_sys_rw_content_t instance/` |
| `from app import app` ImportError | Alte `wsgi.py` ohne `app = create_app()` | aktualisierte `wsgi.py` (im Repo) |
| `203/EXEC` bei systemd | SELinux blockt venv-Python | systemd-Unit nutzt `/bin/bash -c 'exec …'` (im Repo) |
| `dict \| None` SyntaxError | Python 3.9 ohne PEP 604 | `Optional[dict]` (im Repo gefixt) |
| Frontend findet imap_proxy nicht | URL hartkodiert | Auto-Detect in `index.html` (im Repo) |
| Cert-Mismatch | Hostname nicht im Cert | `certbot --expand -d primary -d alias` |
| 404 für `manifest.json` / `service-worker.js` | Flask-Routes fehlten | Routes in `app.py` (im Repo) |
