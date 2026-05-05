# Deployment & Incident Log

## 2026-05-05: CDN-Fehler + Virtual Host Config

### Incident 1: Reload-Loop bei Jobvorschläge

**Symptom:** 503-Fehler + Endlosschleife beim Laden von `/api/jobs/matches`

**Root Cause:** CDN (cdnjs.cloudflare.com) gab 404 für tweetnacl.js v1.0.3 zurück
- Service-Worker versuchte, fehlende Dateien zu cachen
- 404 triggerte Error → Reload-Loop

**Fix:** 
- `tweetnacl.js` + `tweetnacl-util.js` lokal deployed
- Ziel: `/var/www/bewerbungen/static/`
- `index.html` URLs aktualisiert: CDN → `/static/nacl*.min.js`
- Git-Commit: 912bfef

**Lerneffekt:** Externe CDN-Dependencies sind unzuverlässig. Lokales Hosting ist robuster.

---

### Incident 2: Hauptdomain nicht erreichbar

**Symptom:** `wolfinisoftware.de` gab DNS-Fehler (nicht erreichbar)

**Root Cause:** Fehlende Apache Virtual Host Config für `wolfinisoftware.de`
- Nur `bewerbungen.wolfinisoftware.de` war konfiguriert (siehe `bewerbungen.conf`)
- Hauptdomain hatte keine VirtualHost-Direktive

**Fix:**
- `/etc/httpd/conf.d/wolfinisoftware-main.conf` erstellt (VPS nur)
- DocumentRoot: `/var/www/wolfinisoftware`
- HTTP + HTTPS mit Let's Encrypt SSL

**Lerneffekt:** Jede gehostete Domain braucht explizite VirtualHost-Config.

---

## VPS Deployment Notes

**Webserver:** Apache httpd (nicht nginx)

**Reverse Proxy Setup:**
- Apache ProxyPass → Gunicorn (Port 5000) für Flask-App
- IMAP-Proxy (Port 8765), Email-Service (Port 8766) für bewerbungen.wolfinisoftware.de

**Domains:**
- `wolfinisoftware.de` → `/var/www/wolfinisoftware` (statische Website)
- `bewerbungen.wolfinisoftware.de` → Gunicorn Flask-App

**Key Locations:**
- Static Assets: `/var/www/bewerbungen/static/` (lokal hosting, kein CDN)
- Flask App: `/var/www/bewerbungen/`
- Apache Config: `/etc/httpd/conf.d/`
