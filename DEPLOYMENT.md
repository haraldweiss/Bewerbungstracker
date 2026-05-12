# Apache ProxyPass Deployment Rules

**Problem (2026-05-12):** Globale ProxyPass-Regel in claudetracker.conf intercepted `/api/*` requests für bewerbungen.wolfinisoftware.de. Login schlug fehl weil Requests an Node.js auf 3001 statt Flask auf 5000 geroutet wurden.

## Regel 1: Keine globalen ProxyPass-Regeln ⚠️

ProxyPass IMMER in der VirtualHost einfügen, nie auf Root-Level:

```apache
# ✅ RICHTIG - ProxyPass IN der VirtualHost
<VirtualHost *:443>
    ServerName wolfinisoftware.de
    <IfModule mod_proxy.c>
        ProxyPass /api/ http://127.0.0.1:3001/api/
        ProxyPassReverse /api/ http://127.0.0.1:3001/api/
    </IfModule>
</VirtualHost>

# ❌ FALSCH - ProxyPass global (beeinträchtigt ALLE Domains!)
<IfModule mod_proxy.c>
    ProxyPass /api/ http://127.0.0.1:3001/api/
</IfModule>
```

Apache verarbeitet ProxyPass-Regeln global, die erste Übereinstimmung gewinnt — auch über VirtualHost-Grenzen!

## Regel 2: Für neue Services

1. **Eigene `.conf` Datei erstellen** mit dem Service-Namen
   ```bash
   /etc/httpd/conf.d/<service-name>.conf
   ```

2. **NUR VirtualHost-Definitionen** dort, keine globalen Regeln
   
3. **ProxyPass Domain-spezifisch** (alle Regeln IN die VirtualHost)

## Regel 3: Testing vor Deploy

```bash
# 1. Syntax validieren
httpd -t
# Output sollte: "Syntax OK"

# 2. Sanft neuladen (nicht restart!)
systemctl reload httpd

# 3. API testen
curl -i https://bewerbungen.wolfinisoftware.de/api/auth/login
# Sollte JSON sein, NICHT HTML "Cannot POST"
```

## Regel 4: Backup vor Änderung

```bash
cp /etc/httpd/conf.d/service.conf /etc/httpd/conf.d/service.conf.$(date +%s)
```

## Regel 5: Health-Check nach Deploy

```bash
/usr/local/bin/api-health-check.sh
# Prüft ob alle kritischen APIs erreichbar sind
```

---

**Checkliste für Apache-Config-Änderungen:**

- [ ] Backup: `cp service.conf service.conf.$(date +%s)`
- [ ] Syntax: `httpd -t` → "Syntax OK"
- [ ] ProxyPass IN `<VirtualHost>`, nie global
- [ ] Reload: `systemctl reload httpd`
- [ ] Test API: `curl -i https://domain/api/endpoint`
- [ ] Health-Check: `/usr/local/bin/api-health-check.sh`
- [ ] Commit + Push mit Details
