# 📧 Email-Integration & Monitoring / Email Integration Guide

## Überblick / Overview

Die **Email-Integration** ermöglicht es dir:
- 📬 **Automatisch Emails prüfen** - Bewerber-Antworten erkennen
- 📤 **Zusammenfassungen versenden** - Tägliche/wöchentliche Berichte
- 🔔 **Benachrichtigungen erhalten** - Alerts bei Antworten
- 🔐 **Verschlüsselte Passwörter** - AES-128 Sicherheit

The **Email Integration** enables you to:
- 📬 **Auto-check emails** - Detect job application replies
- 📤 **Send summaries** - Daily/weekly reports
- 🔔 **Get notifications** - Alerts when replies detected
- 🔐 **Encrypted passwords** - AES-128 security

---

## 🔧 Einrichtung / Setup

### Schritt 1: Verbindung konfigurieren / Configure Connection

1. Gehe zu **📧 Mail Connector**
2. Wähle **Methode**:
   - 🔧 **Apps Script** (Gmail nur, kostenlos)
   - 📂 **EML Import** (manuell, keine Einrichtung)
   - 📋 **Text/Paste** (manuell, keine Einrichtung)
   - 📮 **IMAP/POP3** (alle Provider)

3. Folge der Anleitung für deine Methode

### Schritt 2: Email-Parameter / Email Settings

Nach erfolgreicher Verbindung:
1. Gehe zu **⚙️ Einstellungen** → Email-Einstellungen
2. Konfiguriere:
   - **Email-Anbieter**: Wähle aus oder "Sonstiges"
   - **IMAP Host**: z.B. `imap.gmail.com`
   - **Port**: Normalerweise `993` (SSL) oder `143` (STARTTLS)
   - **Benutzer**: Deine Email
   - **Passwort**: Dein Passwort (verschlüsselt)

3. **Testen**: Klick "🔗 Verbindung testen"
4. **Speichern**: Klick "💾 Speichern"

### Schritt 3: Monitoring aktivieren / Enable Monitoring

1. Gehe zu **⚙️ Einstellungen** → Monitoring
2. Aktiviere: **☑️ Automatische Überwachung aktivieren**
3. Einstellen: **Alle 30 Minuten prüfen**
4. Optional: **Benachrichtigungen bei Antworten** aktivieren

---

## 🌐 Unterstützte Provider / Supported Providers

| Provider | IMAP-Host | Port | Besonderheiten |
|----------|-----------|------|---|
| **Gmail** | imap.gmail.com | 993 | Needs App Password (2FA) |
| **Outlook/Hotmail** | outlook.office365.com | 993 | Needs App Password |
| **Yahoo** | imap.mail.yahoo.com | 993 | Needs App Password |
| **GMX** | imap.gmx.net | 993 | Standard IMAP |
| **WEB.DE** | imap.web.de | 993 | Standard IMAP |
| **T-Online** | imap.t-online.de | 993 | Standard IMAP |

Für detaillierte Setup-Anleitung: Siehe [GUIDES/](../GUIDES/)

---

## 📊 Intelligente Email-Erkennung / Smart Email Detection

### Wie funktioniert es?

Die App prüft eingehende Emails auf:

1. **Firma-Match**: Erkennt Firma aus Email-Absender
2. **Keyword-Match**: Sucht nach bewerbungsrelevanten Keywords
   - Priority Keywords: "bewerbung", "application", "stellenausschreibung"
   - Weitere Keywords: "interview", "position", "candidacy", "cv", etc.
3. **Kontext-Analyse**: Bewertet Relevanz basierend auf:
   - Subject-Zeile (2x Gewichtung)
   - From-Adresse (2x Gewichtung)
   - Email-Snippet (1x Gewichtung)

### Erkannte Email speichern

Erkannte Emails werden:
1. **In Monitoring-Log gespeichert**
2. **Mit Firma verlinkt** (wenn erkannt)
3. **Als Benachrichtigung gesendet** (wenn aktiviert)
4. **Status zu "Antwort" gesetzt** (optional)

---

## 💌 Email-Versand / Email Sending

### SMTP Einrichtung

1. Gehe zu **⚙️ Einstellungen** → SMTP-Einstellungen
2. Geben Sie ein:
   - **SMTP-Server**: z.B. `smtp.gmail.com`
   - **Port**: `587` (STARTTLS) oder `465` (SSL)
   - **Benutzer**: Deine Email
   - **Passwort**: Dein Passwort (verschlüsselt)

3. **Test**: "🧪 Test-Email versenden"
4. **Speichern**: "💾 Speichern"

### Zusammenfassungen versenden

1. Gehe zu **⚙️ Einstellungen** → Email-Zusammenfassungen
2. Aktiviere: **☑️ Automatischer Versand**
3. Wähle Häufigkeit:
   - **Täglich** - Jeden Tag um X Uhr
   - **Wöchentlich** - Jeden Montag um X Uhr
   - **Monatlich** - Am 1. des Monats um X Uhr

4. **Empfänger**: Gib deine Email-Adresse ein
5. **Test versenden**: "📧 Test-Zusammenfassung"

### Inhalt der Zusammenfassung

Die automatische Zusammenfassung enthält:
- 📊 **Statistiken**: Gesamtbewerbungen, Erfolgsquote, Durchschnittliche Antwortzeit
- 📈 **Status-Übersicht**: Beworben, Interview, Zusage, Absage, Ghosting
- 📬 **Neue Antworten**: Erkannte Email-Antworten
- 📌 **Offene Positionen**: Bewerbungen ohne Antwort
- 📅 **Aktuelle Aktivitäten**: Letzte Änderungen

---

## 🔐 Sicherheit / Security

### Verschlüsslung

✅ **Passwort-Speicherung:**
- Verschlüsselung: Fernet (AES-128-CBC)
- Key-Derivation: PBKDF2 (100,000 Iterationen)
- Speicherung: Lokal im Browser

✅ **Datensicherheit:**
- Alle Daten bleiben lokal
- Keine Daten an Cloud-Server
- Emails werden nicht synchronisiert
- Nur Header-Informationen werden gepuffert

### Best Practices

1. **App Passwords nutzen**:
   - Gmail, Outlook, Yahoo: Erstelle "App Password" statt Kontopasswort
   - Länger und sicherer
   - Leicht widerrufbar

2. **Passwort-Verwaltung**:
   - Nutze Passwort-Manager
   - Ändere Passwörter regelmäßig
   - Widerruf alte App-Passwörter

3. **Monitoring**:
   - Prüfe gelegentlich unerwartete Emails
   - Aktualisiere Firmenbezeichnungen falls nötig
   - Überprüfe erkannte Antworten regelmäßig

---

## ❓ FAQ & Troubleshooting

### "Verbindungsfehler"
**Problem**: Kann nicht zu Email-Server verbinden
**Lösung**:
- Prüfe IMAP-Host und Port
- Prüfe Benutzername und Passwort
- Für Gmail/Outlook: Nutze App Password statt Kontopasswort
- Prüfe Firewall/ISP blockiert nicht den Port

### "Keine Emails erkannt"
**Problem**: Monitoring aktiv aber keine Emails erkannt
**Lösung**:
- Prüfe dass Email wirklich eingegangen ist
- Prüfe Email nicht in Spam-Ordner
- Prüfe dass Firma-Name in der Bewerbung korrekt ist
- Versuche Keywords in Einstellungen zu anpassen

### "Test-Email kommt nicht an"
**Problem**: SMTP Test schlägt fehl
**Lösung**:
- Prüfe SMTP-Host und Port
- Für Gmail: Port `587` (nicht 465 oder 25)
- Nutze App Password nicht Kontopasswort
- Prüfe dass "weniger sichere Apps" nicht blockiert sind (Gmail)

### "Token ungültig" Fehler
**Problem**: OAuth Token für Apps Script hat abgelaufen
**Lösung**:
- Gehe zu "📧 Mail Connector" → Apps Script Tab
- Reauthorisiere die Verbindung
- Folge den Anweisungen nochmal

---

## 📊 Email-Monitoring Log

Gehe zu **📧 Mail Connector** → Monitoring-Tab um zu sehen:
- ✅ **Erkannte Antworten**: Welche Emails erkannt wurden
- 📅 **Erkannt am**: Wann die Email eingegangen ist
- 👤 **Firma**: Welche Firma antwortet hat
- 📧 **Email-Subject**: Betreffzeile der Antwort

---

## 🔧 Erweiterte Einstellungen / Advanced

### Keywords anpassen

1. Gehe zu **⚙️ Einstellungen** → Email-Keywords
2. Füge neue Keywords hinzu (z.B. deine Branche)
3. Keywords werden bei zukünftigen Emails verwendet
4. **Speichern**

### Email-Import Startdatum

1. Gehe zu **⚙️ Einstellungen** → Email-Import
2. Setze **Startdatum**: z.B. "2025-01-01"
3. Nur Emails nach diesem Datum werden importiert
4. **Speichern**

---

## 📱 Benachrichtigungen / Notifications

### Lokale Browser-Benachrichtigungen

1. Öffne "⚙️ Einstellungen" → Benachrichtigungen
2. Aktiviere: **☑️ Desktop-Benachrichtigungen**
3. Wähle Benachrichtigungstypen:
   - **Neue Antwort erkannt**
   - **Erfolgreiche Email-Zusammenfassung versandt**
4. Browser fragt nach Berechtigung
5. **Zulassen** um Benachrichtigungen zu erhalten

✅ **Alle Benachrichtigungen sind lokal** - Keine Daten an Server!

---

## 🔗 Weitere Ressourcen / More Resources

- [Getting Started Guide](../GETTING_STARTED.md)
- [Gmail Setup Guide](../GUIDES/SETUP_GMAIL.md)
- [Outlook Setup Guide](../GUIDES/SETUP_OUTLOOK.md)
- [IMAP Setup Guide](../GUIDES/SETUP_IMAP.md)

---

## 📝 Version-Info

- **Feature hinzugefügt**: v3.0
- **Intelligent Detection**: v3.4
- **Auto-Monitoring**: v4.0
- **Letztes Update**: 2025-03-16
