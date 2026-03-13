# 📧 Email-Service Dokumentation

Dokumentation für den automatischen Email-Service (SMTP-Versand & Email-Monitoring).

## Übersicht

Der Email-Service ist ein Python-basierter Microservice, der folgende Funktionen bereitstellt:

1. **SMTP Email-Versand** - Automatischer Versand von Email-Zusammenfassungen
2. **Email-Monitoring** - Automatische Erkennung von Bewerbungsantworten
3. **Benachrichtigungen** - Email-Alerts bei erkannten Antworten
4. **SQLite-Datenbank** - Persistente Speicherung von Konfigurationen

## Architektur

### Port & Binding
- **Port**: 8766
- **Host**: 127.0.0.1 (localhost nur, keine Netzwerk-Exposition)
- **Protocol**: HTTP REST API

### Komponenten

```
email_service.py
├── Database Layer (SQLite)
│   ├── email_config - Konfigurationen (SMTP, IMAP, etc.)
│   ├── email_log - Versand-Historie
│   └── email_monitoring - Erkannte Email-Responses
├── SMTP Service
│   ├── send_email() - Versand per SMTP
│   ├── check_and_send_summary() - Geplanter Versand
│   └── notify_monitoring_results() - Alert-Versand
├── Email Monitoring
│   ├── fetch_imap_emails() - Abrufen von Emails
│   ├── check_email_for_application() - Firma-Matching
│   └── check_and_monitor_emails() - Monitoring-Logik
├── HTTP Handler
│   ├── /api/config/* - Konfiguration
│   ├── /api/email/* - Email-Funktionen
│   ├── /api/monitoring/* - Monitoring-Funktionen
│   └── /api/status - Service-Status
└── Background Scheduler
    ├── check_and_send_summary() - Alle 5 Min.
    └── check_and_monitor_emails() - Alle 30 Min.
```

## API-Referenz

### Configuration Endpoints

#### GET Config
```
POST /api/config/get
{
  "key": "smtp_user"
}

Response:
{
  "status": "ok",
  "key": "smtp_user",
  "value": "user@gmail.com"
}
```

#### Save Config
```
POST /api/config/save
{
  "key": "smtp_host",
  "value": "smtp.gmail.com"
}

Response:
{
  "status": "ok",
  "message": "Config saved"
}
```

### Email Endpoints

#### Send Email
```
POST /api/email/send
{
  "recipient": "test@example.com",
  "subject": "Test Email",
  "html": "<h1>Test</h1>",
  "text": "Test Email"
}

Response:
{
  "status": "ok",
  "message": "Email sent"
}
```

#### Send Test Email
```
POST /api/email/test
{
  "recipient": "test@example.com"
}

Response:
{
  "status": "ok",
  "message": "Test email sent"
}
```

### Monitoring Endpoints

#### Enable/Disable Monitoring
```
POST /api/monitoring/enable
{
  "enabled": true,
  "recipient": "alerts@example.com",
  "notify": true
}

Response:
{
  "status": "ok",
  "message": "Monitoring enabled"
}
```

#### Check Email Now
```
POST /api/monitoring/check
{}

Response:
{
  "status": "ok",
  "detected": 2,
  "responses": [
    {
      "company": "Microsoft",
      "from": "recruitment@microsoft.com",
      "subject": "Interview Invitation"
    }
  ]
}
```

#### Save Applications Cache
```
POST /api/applications/cache
{
  "bewerbungen": [
    {
      "firma": "Microsoft",
      "position": "Engineer",
      ...
    }
  ]
}

Response:
{
  "status": "ok",
  "message": "Cached 10 applications"
}
```

### Status Endpoint

#### Get Service Status
```
POST /api/status
{}

Response:
{
  "status": "ok",
  "service": "Bewerbungs-Tracker Email Service",
  "smtp_configured": true,
  "summary_enabled": true,
  "summary_recipient": "user@example.com",
  "summary_frequency": "weekly",
  "should_send_now": false,
  "monitoring_enabled": true,
  "imap_configured": true
}
```

## Konfiguration

### Erforderliche SMTP-Einstellungen

```
smtp_host       - Email-Server Adresse (z.B. smtp.gmail.com)
smtp_port       - Email-Server Port (z.B. 587)
smtp_user       - Email-Adresse für Versand
smtp_pass       - Email-Passwort (nicht persistiert)
```

### Email-Zusammenfassung Einstellungen

```
summary_enabled     - true/false
summary_recipient   - Empfänger-Email
summary_frequency   - daily|weekly|monthly
last_sent          - ISO-Timestamp des letzten Versands
```

### Email-Monitoring Einstellungen

```
email_monitoring_enabled - true/false
imap_host               - IMAP-Server Adresse
imap_port              - IMAP-Port (z.B. 993)
imap_user              - Email-Adresse
imap_pass              - Email-Passwort (nicht persistiert)
monitoring_recipient   - Benachrichtigungsempfänger
monitoring_notify      - true/false
```

## Background Scheduler

Der Scheduler läuft permanent im Hintergrund und führt folgende Aufgaben durch:

### Alle 5 Minuten
- Prüfe ob Email-Zusammenfassung versendet werden soll
- Falls ja: Versende Zusammenfassung per Email

### Alle 30 Minuten
- Prüfe auf neue Emails
- Vergleiche mit Bewerbungsliste
- Erkenne Antworten
- Sende Alert-Email wenn konfiguriert

## Email-Monitoring Logik

### Firmenerkennung

Der Monitor nutzt folgende Strategien zur Erkennung:

1. **Normalisierung**: Entfernt Suffixe wie "GmbH", "AG", "Ltd", "Inc"
2. **Sender-Matching**: Prüft ob Firmennamen im Absender enthalten ist
3. **Subject-Matching**: Prüft ob Firmennamen im Betreff enthalten ist
4. **Domain-Matching**: Prüft ob normalisierter Name in Email-Domain enthalten ist

### Beispiele

```
Bewerbung an: "Microsoft GmbH"
Email von: recruitment@microsoft.com
→ Erkannt: Normalisiert zu "microsoft", Domain match

Bewerbung an: "Apple Inc"
Email Subject: "Apple - Interview Invitation"
→ Erkannt: Subject match

Bewerbung an: "SAP SE"
Email von: careers@sap.com
→ Erkannt: Domain match (sap in domain)
```

## Sicherheit

### Passwort-Handling
- **SMTP-Passwort**: Nur im RAM während Versand, nicht persistiert
- **IMAP-Passwort**: Nur im RAM während Monitoring, nicht persistiert
- **Konfiguration**: Gespeicherte Configs enthalten keine Passwörter

### Netzwerk-Sicherheit
- Nur auf 127.0.0.1 erreichbar (localhost)
- IP-Validierung bei jedem Request
- Keine direkten Netzwerk-Exports

### Daten-Sicherheit
- SQLite-Datenbank lokal
- Keine Cloud-Speicherung
- Keine Passwort-Logs
- Email-Inhalte nur kurzzeitig im RAM

## Fehlerbehandlung

### SMTP Fehler
- **Authentication Failed**: Falsches Passwort oder SMTP-Konfiguration
- **Timeout**: SMTP-Server nicht erreichbar
- **Connection Error**: Netzwerk-Problem

### IMAP Fehler
- **Connection Failed**: IMAP-Server nicht erreichbar
- **Login Failed**: Falsches Passwort
- **No SSL**: Port 993 benötigt SSL

### Monitoring Fehler
- **No Applications**: applications_cache.json nicht vorhanden
- **No Emails**: Keine Emails in letzten 7 Tagen
- **IMAP Disabled**: Email-Monitoring deaktiviert

## Performance

### Ressourcen-Nutzung
- **Memory**: ~50-100 MB (Python + Service)
- **Disk**: ~1-5 MB (SQLite-Datenbank)
- **CPU**: Minimal (Scheduler: ~1% wenn idle)

### Skalierbarkeit
- IMAP-Abruf: Max. 50 Emails pro Check
- Email-Matching: Linear mit Anzahl Bewerbungen
- Monitoring-Intervall: 30 Min (konfigurierbar in Code)

## Troubleshooting

### Service startet nicht
```bash
# Prüfe Python-Installation
python3 --version

# Prüfe erforderliche Module
python3 -c "import imaplib, smtplib, sqlite3; print('OK')"

# Prüfe Port-Verfügbarkeit
lsof -i :8766
```

### SMTP funktioniert nicht
```bash
# Test mit telnet
telnet smtp.gmail.com 587

# Test mit Python
python3 -c "import smtplib; s = smtplib.SMTP('smtp.gmail.com', 587); s.starttls(); print('OK')"
```

### IMAP funktioniert nicht
```bash
# Test mit telnet
telnet imap.gmail.com 993

# Test mit Python
python3 -c "import imaplib, ssl; i = imaplib.IMAP4_SSL('imap.gmail.com'); i.login('email@gmail.com', 'password'); print('OK')"
```

### Keine Antworten erkannt
1. Prüfe applications_cache.json existiert
2. Prüfe IMAP-Verbindung funktioniert
3. Prüfe ob Emails vorhanden sind
4. Versuche "Jetzt prüfen" im UI

## Logs & Monitoring

### Wichtige Log-Einträge
```
📧 Email Service Scheduler gestartet
✅ Email versendet: user@example.com
⏰ Zeit für Email-Zusammenfassung!
📧 Checking for application responses...
✅ Application response detected from: Microsoft
💌 Neue Antwort-Email versendet
```

### Datenbank-Inspektion
```bash
# SQLite CLI starten
sqlite3 email_config.db

# Konfigurationen anzeigen
SELECT * FROM email_config;

# Email-Log anzeigen
SELECT * FROM email_log ORDER BY sent_at DESC LIMIT 10;

# Erkannte Antworten anzeigen
SELECT * FROM email_monitoring ORDER BY detected_at DESC;
```

## Best Practices

### SMTP-Setup
1. Nutze App-Passwort statt normalem Passwort (Gmail)
2. Teste Verbindung vor Produktivbetrieb
3. Sendet Test-Email zur Verifikation
4. Überwache Email-Log auf Fehler

### Email-Monitoring
1. Aktualisiere applications_cache.json regelmäßig
2. Prüfe IMAP-Einstellungen sind korrekt
3. Testen Sie mit "Jetzt prüfen"
4. Überwachen Sie email_monitoring-Tabelle

### Wartung
1. Lösche alte Logs regelmäßig: `DELETE FROM email_log WHERE sent_at < DATE('now', '-30 days');`
2. Backup SQLite-Datenbank: `cp email_config.db email_config.db.backup`
3. Überwache Disk-Space für Datenbank
4. Prüfe regelmäßig ob Service noch läuft

---

**Version**: 1.0
**Letzte Aktualisierung**: März 2026
**Status**: Produktiv
