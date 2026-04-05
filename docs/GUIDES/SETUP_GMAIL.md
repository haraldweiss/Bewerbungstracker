# 📧 Gmail Setup - Complete Guide / Vollständige Anleitung

## Überblick / Overview

Es gibt **2 Methoden** um Gmail mit Bewerbungs-Tracker zu verbinden:

1. **Google Apps Script** (Empfohlen) - Kostenlos, einfach, kein OAuth-Flow
2. **IMAP/POP3** (Alternativ) - Direkte Verbindung mit App Password

---

## 🔧 Methode 1: Google Apps Script (Empfohlen)

### Schritt 1: Script öffnen

1. Öffne [script.google.com](https://script.google.com)
2. Klick **"+ Neues Projekt"**
3. Lösche den vorhandenen Code
4. Kopiere folgenden Code:

```javascript
function doPost(e) {
  const query = e.parameter.query || 'ALL';
  const limit = parseInt(e.parameter.limit) || 20;

  try {
    const threads = GmailApp.search(query, 0, limit);
    const emails = [];

    for (const thread of threads) {
      const messages = thread.getMessages();
      for (const message of messages) {
        emails.push({
          subject: message.getSubject(),
          from: message.getFrom(),
          date: message.getDate().toISOString(),
          snippet: message.getPlainBody().substring(0, 200),
          labels: thread.getLabels().map(l => l.getName())
        });
      }
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: 'ok',
      count: emails.length,
      emails: emails
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: 'error',
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return doPost(e);
}
```

### Schritt 2: Script veröffentlichen

1. Klick **"Ausführung"** (linke Seite)
2. Wähle Funktion: **"doPost"**
3. Klick **"Ausführen"**
4. Erlaube Berechtigungen wenn gefragt
5. Klick **"Bereitstellung"** → **"Neue Bereitstellung"** (rechts oben)
6. Wähle Typ: **"Web-App"**
7. Konfiguriere:
   - **Ausführung als**: Dein Google-Account
   - **Zugriff gewährt durch**: Mich (dein Konto)
8. Klick **"Bereitstellen"**
9. Kopiere die **Web-App URL** (sieht aus wie: `https://script.google.com/...`)

### Schritt 3: In Bewerbungs-Tracker eintragen

1. Gehe zu **📧 Mail Connector**
2. Wähle **🔧 Apps Script** Tab
3. Paste deine Web-App URL
4. Klick **"✅ Verbindung testen"**
5. Erlaube Gmail-Zugriff wenn gefragt
6. Sollte **"✅ Verbindung erfolgreich"** zeigen

### Vorteile dieser Methode

✅ **Kein OAuth-Flow** - Keine komplizierten Autorisierungen
✅ **Kostenlos** - Google Apps Script ist kostenlos
✅ **Sicher** - Dein Passwort bleibt privat
✅ **Einfach** - Nur Copy-Paste und Link
✅ **Zuverlässig** - Google verwaltet die Verbindung

---

## 🔐 Methode 2: IMAP mit App Password

Falls Apps Script nicht funktioniert oder du IMAP bevorzugst:

### Schritt 1: 2-Faktor-Authentifizierung aktivieren

Gmail erfordert 2FA für App Passwords:

1. Öffne [myaccount.google.com](https://myaccount.google.com)
2. Klick **"Sicherheit"** (linke Seite)
3. Aktiviere **"2-Schritt-Bestätigung"**:
   - Folge den Anweisungen
   - Verifiziere mit Telefon
4. Nach Aktivierung: **"App-Passwörter"** erscheint

### Schritt 2: App Password generieren

1. Gehe zu [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Wähle:
   - **App**: Mail
   - **Gerät**: Windows Computer (oder dein Gerät)
3. Klick **"Generieren"**
4. **Kopiere das 16-stellige Passwort** (ohne Leerzeichen)

### Schritt 3: In Bewerbungs-Tracker eintragen

1. Gehe zu **📧 Mail Connector**
2. Wähle **📮 IMAP / POP3** Tab
3. Email-Anbieter: **Gmail (IMAP)**
4. Konfiguriere:
   - **Server**: `imap.gmail.com`
   - **Port**: `993`
   - **Protokoll**: IMAP
   - **Benutzer**: Deine Gmail-Adresse (z.B. beispiel@gmail.com)
   - **Passwort**: Das 16-stellige App Password
5. Klick **"✅ Verbindung testen"**
6. Sollte **"✅ Verbindung erfolgreich"** zeigen
7. Klick **"💾 Speichern"**

### Wichtig für IMAP

⚠️ **Nicht dein Gmail-Passwort verwenden!**
- Nutze **immer das 16-stellige App Password**
- Finde es unter myaccount.google.com/apppasswords

---

## 📧 Email-Monitoring aktivieren

Nach erfolgreichem Setup:

1. Gehe zu **⚙️ Einstellungen**
2. Aktiviere **"☑️ Automatische Überwachung"**
3. Setze **"Alle 30 Minuten"**
4. Optional: **"Benachrichtigungen bei Antworten"**
5. Klick **"💾 Speichern"**

Die App wird jetzt **automatisch alle 30 Minuten** deine Emails prüfen!

---

## 📤 Email-Versand einrichten (SMTP)

Um Zusammenfassungen zu versenden:

1. Gehe zu **⚙️ Einstellungen** → **SMTP-Einstellungen**
2. Konfiguriere:
   - **SMTP-Server**: `smtp.gmail.com`
   - **Port**: `587`
   - **Benutzer**: Deine Gmail-Adresse
   - **Passwort**: Das 16-stellige App Password (gleich wie oben)
3. Klick **"🧪 Test-Email versenden"**
4. Prüfe dein Posteingang
5. Klick **"💾 Speichern"**

Dann zurück zu **Email-Zusammenfassungen**:
1. Aktiviere **"☑️ Automatischer Versand"**
2. Wähle Häufigkeit (täglich, wöchentlich, monatlich)
3. Gib Empfänger-Email ein
4. Klick **"💾 Speichern"**

---

## ❓ Troubleshooting

### "Authentifizierungsfehler" oder "Falsches Passwort"

**Problem:** IMAP/SMTP sagt Passwort ist falsch

**Lösungen:**
1. ✅ Verwendest du das **16-stellige App Password**? (nicht dein Gmail-Passwort)
2. ✅ Hast du **2-Schritt-Bestätigung aktiviert**?
3. ✅ Ist dein **App Password aktuell**? (regeneriere falls nötig)
4. ✅ Prüfe dass du **Leerzeichen im App Password entfernst**

### "Apps Script gibt 404 Error"

**Problem:** Web-App URL funktioniert nicht

**Lösungen:**
1. Prüfe dass deine URL korrekt kopiert ist
2. Führe das Script nochmal aus (Ausführung → doPost)
3. Erstelle eine neue Bereitstellung:
   - Bereitstellung → Neue Bereitstellung
   - Wähle Web-App
   - Kopiere neue URL

### "Gmail fragt nach Bestätigung"

**Das ist normal!** Gmail schützt sich vor unbekannten Apps:
1. Öffne den "Sicherheitshinweis" Link in Gmail
2. Erlaube "weniger sichere Apps" (für Apps Script)
3. Oder akzeptiere die Benachrichtigung

### Keine Emails werden erkannt

**Problem:** Monitoring läuft aber erkennt keine Bewerbungs-Antworten

**Lösungen:**
1. Prüfe dass Email tatsächlich eingegangen ist
2. Prüfe Spam-Ordner
3. Überprüfe dass Firmennamen in Bewerbung stimmen
4. Gehe zu **⚙️ Einstellungen** → **Email-Keywords**:
   - Füge spezifische Keywords hinzu
   - Z.B. Branchen-Keywords oder Firmennamen

---

## 🔒 Sicherheit & Best Practices

### Sicher mit App Passwords

✅ **App Passwords sind sicher weil:**
- Nur Zugriff auf Gmail (nicht dein ganzes Google-Konto)
- Leicht widerrufbar jederzeit
- Ändern sich nicht automatisch
- 16-stellige Zufallscodes

✅ **Best Practices:**
1. **Nutze niemals dein Gmail-Passwort**
2. **Generiere ein neues App Password pro Gerät**
3. **Widerruf alte App Passwords** wenn du Geräte wechselst
4. **Prüfe regelmäßig** deine App Passwords unter myaccount.google.com/apppasswords

### Falls du dein Passwort vergisst

1. Öffne [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Lösche das alte Passwort
3. Generiere ein neues
4. Trage das neue in Bewerbungs-Tracker ein

---

## 📚 Weitere Optionen

### Alternative: Yahoo Mail / Outlook / Andere Provider

Falls du **nicht Gmail nutzt**, siehe:
- [Outlook Setup Guide](SETUP_OUTLOOK.md)
- [IMAP Setup Guide](SETUP_IMAP.md)

---

## ✅ Checkliste

Vor du anfängst mit Email-Monitoring:

- [ ] Gmail-Account ist erstellt
- [ ] 2-Schritt-Bestätigung ist aktiviert (falls IMAP)
- [ ] App Password ist generiert (falls IMAP)
- [ ] Verbindung wurde getestet (**"✅ Erfolgreich"**)
- [ ] Monitoring ist aktiviert in Einstellungen
- [ ] Erste Test-Email wurde importiert

**Fertig! Deine Emails werden jetzt überwacht!** 🎉

---

## 📞 Support

Falls etwas nicht funktioniert:
1. Überprüfe alle Schritte oben
2. Versuche mit freshly generierten Passwörtern
3. Kontaktiere Google Support für Gmail-spezifische Fragen
