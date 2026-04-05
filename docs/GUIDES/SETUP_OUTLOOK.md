# 📧 Outlook/Hotmail Setup - Complete Guide / Vollständige Anleitung

## Überblick / Overview

Diese Anleitung zeigt wie du **Outlook, Hotmail oder Live-Mail** mit Bewerbungs-Tracker verbindest.

Es gibt **1 Methode:**
- **IMAP/POP3** - Mit App Password (sicher und einfach)

---

## ✅ Voraussetzungen / Requirements

- Ein aktives Outlook.com oder Hotmail.com Konto
- 2-Faktor-Authentifizierung aktiviert (für App Passwords)
- Internetverbindung

---

## 🔧 Setup: IMAP mit App Password

### Schritt 1: 2-Faktor-Authentifizierung aktivieren

Outlook erfordert 2FA für App Passwords:

1. Öffne [account.microsoft.com](https://account.microsoft.com)
2. Klick **"Sicherheit"** (linke Seite)
3. Unter **"Sicherheit"** suche nach **"App-Passwörter"**
4. Falls es nicht angezeigt wird:
   - Gehe zu **"Erweiterte Sicherheitsoptionen"**
   - Aktiviere **"2-Schritt-Bestätigung"**
   - Folge den Anweisungen (E-Mail oder Telefon)

### Schritt 2: App Password generieren

1. Gehe zu [account.microsoft.com/security](https://account.microsoft.com/security)
2. Klick **"App-Passwörter"**
3. Wähle:
   - **App**: Mail
   - **Gerät**: Windows (oder dein Gerät)
4. Klick **"Erstellen"** oder **"Weiter"**
5. **Kopiere das 16-stellige Passwort** (Format: `xxxx-xxxx-xxxx-xxxx`)

### Schritt 3: In Bewerbungs-Tracker eintragen

1. Öffne **📧 Mail Connector**
2. Wähle **📮 IMAP / POP3** Tab
3. Email-Anbieter: **Outlook / Hotmail**
4. Konfiguriere:
   - **Server**: `outlook.office365.com`
   - **Port**: `993`
   - **Protokoll**: IMAP
   - **Benutzer**: Deine Outlook-Email (z.B. beispiel@outlook.com)
   - **Passwort**: Das 16-stellige App Password
5. Klick **"✅ Verbindung testen"**
6. Sollte **"✅ Verbindung erfolgreich"** zeigen
7. Klick **"💾 Speichern"**

---

## 📧 Email-Monitoring aktivieren

Nach erfolgreichem Setup:

1. Gehe zu **⚙️ Einstellungen**
2. Aktiviere **"☑️ Automatische Überwachung"**
3. Setze **"Alle 30 Minuten"**
4. Optional: **"Benachrichtigungen bei Antworten"**
5. Klick **"💾 Speichern"**

Die App wird jetzt **automatisch alle 30 Minuten** deine Outlook-Emails prüfen!

---

## 📤 Email-Versand einrichten (SMTP)

Um Zusammenfassungen zu versenden:

1. Gehe zu **⚙️ Einstellungen** → **SMTP-Einstellungen**
2. Konfiguriere:
   - **SMTP-Server**: `smtp.office365.com`
   - **Port**: `587`
   - **Benutzer**: Deine Outlook-Email
   - **Passwort**: Das 16-stellige App Password (gleich wie oben)
3. Klick **"🧪 Test-Email versenden"**
4. Prüfe dein Outlook-Posteingang
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
1. ✅ Verwendest du das **16-stellige App Password**? (nicht dein Outlook-Passwort)
2. ✅ Hast du **2-Schritt-Bestätigung aktiviert**?
3. ✅ Ist dein **App Password aktuell**? (regeneriere falls nötig)
4. ✅ Prüfe dass du **Leerzeichen/Bindestriche genau kopierst**
5. ✅ Server ist `outlook.office365.com` (nicht `pop.outlook.com`)

### "Verbindung fehlgeschlagen"

**Problem:** Kann nicht zum Server verbinden

**Lösungen:**
1. Prüfe dass **Port 993** nicht blockiert ist
2. Prüfe deine **Internetverbindung**
3. Versuche **Port 143** mit STARTTLS statt 993
4. Warte 5-10 Minuten und versuche erneut

### App-Passwort wird nicht angezeigt

**Problem:** App-Passwörter Option ist nicht sichtbar

**Lösungen:**
1. Prüfe dass du **2-Schritt-Bestätigung aktiviert** hast
2. Warte 24 Stunden nach Aktivierung
3. Versuche es in einem anderen Browser
4. Öffne [account.microsoft.com/security](https://account.microsoft.com/security) direkt

### Keine Emails werden erkannt

**Problem:** Monitoring läuft aber erkennt keine Bewerbungs-Antworten

**Lösungen:**
1. Prüfe dass Email tatsächlich eingegangen ist
2. Prüfe Junk/Spam-Ordner
3. Überprüfe dass Firmennamen in Bewerbung stimmen
4. Gehe zu **⚙️ Einstellungen** → **Email-Keywords**:
   - Füge spezifische Keywords hinzu
   - Z.B. Firmennamen oder Branchen-Keywords

### IMAP ist auf meinem Account nicht aktiviert

**Problem:** Outlook sagt IMAP ist deaktiviert

**Lösungen:**
1. Öffne [outlook.live.com](https://outlook.live.com)
2. Gehe zu **Einstellungen** (⚙️ Icon)
3. Wähle **"Alle Einstellungen anzeigen"**
4. Gehe zu **"Synchronisierung"** oder **"Verbundene Apps"**
5. Aktiviere **"POP und IMAP"**
6. Speichere und versuche erneut

---

## 🔒 Sicherheit & Best Practices

### Sicher mit App Passwords

✅ **App Passwords sind sicher weil:**
- Nur Zugriff auf Mail (nicht dein ganzes Konto)
- Leicht widerrufbar jederzeit
- Können nicht zum Anmelden bei account.microsoft.com verwendet werden
- 16-stellige Zufallscodes

✅ **Best Practices:**
1. **Nutze niemals dein Outlook-Passwort**
2. **Generiere ein neues App Password pro Gerät**
3. **Widerruf alte App Passwords** wenn du Geräte wechselst
4. **Prüfe regelmäßig** deine App Passwords unter account.microsoft.com

### Falls du dein App Password vergisst

1. Öffne [account.microsoft.com/security](https://account.microsoft.com/security)
2. Klick **"App-Passwörter"**
3. Lösche das alte Passwort aus der Liste
4. Generiere ein neues
5. Trage das neue in Bewerbungs-Tracker ein

---

## 📊 IMAP vs. POP3

| Feature | IMAP | POP3 |
|---------|------|------|
| **Synchronisation** | Cloud ↔ Client | Download nur |
| **Mehrere Geräte** | ✅ Ja | ❌ Nein |
| **Empfohlene Option** | ✅ Ja | Nein |
| **Server**: outlook.office365.com | ✅ Ja | `pop-mail.outlook.com` |
| **Port** | 993 | 995 |

**Empfehlung:** Nutze immer **IMAP** statt POP3!

---

## 📚 Weitere Optionen

Falls du **nicht Outlook nutzt**, siehe:
- [Gmail Setup Guide](SETUP_GMAIL.md)
- [IMAP Setup Guide](SETUP_IMAP.md) (für andere Provider)

---

## ✅ Checkliste

Vor du anfängst mit Email-Monitoring:

- [ ] Outlook-Account ist erstellt
- [ ] 2-Schritt-Bestätigung ist aktiviert
- [ ] App Password ist generiert
- [ ] Verbindung wurde getestet (**"✅ Erfolgreich"**)
- [ ] IMAP ist auf meinem Account aktiviert
- [ ] Monitoring ist aktiviert in Einstellungen
- [ ] Erste Test-Email wurde importiert

**Fertig! Deine Outlook-Emails werden jetzt überwacht!** 🎉

---

## 📞 Support

Falls etwas nicht funktioniert:
1. Überprüfe alle Schritte oben
2. Versuche mit frisch generierten Passwörtern
3. Prüfe dass du IMAP aktiviert hast
4. Kontaktiere Microsoft Support für Outlook-spezifische Fragen
