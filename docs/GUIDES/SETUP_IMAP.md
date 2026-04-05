# 📧 Generic IMAP/POP3 Setup - Complete Guide / Vollständige Anleitung

## Überblick / Overview

Diese Anleitung zeigt wie du **beliebige IMAP/POP3-Email-Provider** mit Bewerbungs-Tracker verbindest.

Es gibt **2 Methoden:**
- **IMAP** (empfohlen) - Standard-Protokoll, gute Synchronisierung
- **POP3** (alternativ) - Download-only, weniger ideal

**Unterstützte Provider:**
- 🇩🇪 GMX, WEB.DE, T-Online, 1&1
- 🇬🇧 Yahoo, AOL
- 🇨🇭 Bluewin, UPC Cablecom
- 🇦🇹 A1, T-Mobile AT
- Andere mit IMAP/POP3-Zugang

---

## ✅ Voraussetzungen / Requirements

- Ein aktives Email-Konto bei deinem Provider
- IMAP/POP3 aktiviert (nicht bei allen Standard)
- Internetverbindung
- **Optional:** 2-Faktor-Authentifizierung (manche Provider)

---

## 🔍 Provider-Informationen finden

### Schritt 1: IMAP-Host und Port herausfinden

**Option A: Provider-Einstellungen Seite**
1. Melde dich bei deinem Email-Account an
2. Gehe zu **Einstellungen** (⚙️ Icon)
3. Suche **"IMAP"**, **"POP3"** oder **"Verbundene Apps"**
4. Dort stehen IMAP-Host und Port

**Option B: Dein Provider unten finden**

| Provider | IMAP-Host | Port | POP3-Host | Port |
|----------|-----------|------|-----------|------|
| **GMX** | imap.gmx.net | 993 | pop.gmx.net | 995 |
| **WEB.DE** | imap.web.de | 993 | pop.web.de | 995 |
| **T-Online** | imap.t-online.de | 993 | pop.t-online.de | 995 |
| **1&1** | imap.ionos.de | 993 | pop.ionos.de | 995 |
| **Yahoo** | imap.mail.yahoo.com | 993 | pop.mail.yahoo.com | 995 |
| **AOL** | imap.aol.com | 993 | pop.aol.com | 995 |
| **Bluewin** | imap.bluewin.ch | 993 | pop3.bluewin.ch | 995 |
| **1&1 (alt)** | mail.1und1.de | 993 | pop.1und1.de | 995 |

**Option C: Online suchen**
Google: `"[dein-provider] IMAP Host Port"`
Beispiel: `"GMX IMAP Host Port"` → findet offizielle Dokumentation

---

## 🔧 Setup: IMAP (empfohlen)

### Schritt 1: Besonderheiten deines Providers checken

Einige Provider erfordern **App Passwords** statt Kontopasswort:

**Nutzt dein Provider App Passwords?**
- ✅ Ja: GMX, WEB.DE, Yahoo, AOL, T-Online (teilweise)
- ❌ Nein: Bluewin, 1&1 (meist normales Passwort)

**Falls "Ja":**
- Siehe Abschnitt "App Password generieren" unten
- Falls "Nein": Nutze dein normales Kontopasswort

### Schritt 2: App Password generieren (falls nötig)

**Für GMX:**
1. Öffne https://www.gmx.net
2. Melde dich an
3. Gehe zu **Einstellungen** → **Sicherheit**
4. Unter **"App-Passwörter"** klick **"Neues App-Passwort erstellen"**
5. **Kopiere das 16-stellige Passwort**

**Für WEB.DE:**
1. Öffne https://www.web.de
2. Melde dich an
3. Gehe zu **Einstellungen** → **Sicherheit**
4. Unter **"App-Passwörter"** klick **"+ Hinzufügen"**
5. **Kopiere das 16-stellige Passwort**

**Für Yahoo:**
1. Öffne https://account.yahoo.com
2. Klick **"Sicherheit"**
3. Unter **"App-Passwörter"** wähle **Mail** und dein Gerät
4. Klick **"Generieren"**
5. **Kopiere das 16-stellige Passwort**

**Für andere Provider:**
- Wenn verfügbar: Suche in Einstellungen nach **"App Password"** oder **"Anwendungspasswort"**
- Falls nicht vorhanden: Nutze dein normales Kontopasswort

### Schritt 3: In Bewerbungs-Tracker eintragen

1. Öffne **📧 Mail Connector**
2. Wähle **📮 IMAP / POP3** Tab
3. Email-Anbieter: **Sonstiger IMAP-Provider**
4. Konfiguriere:
   - **Server**: Dein IMAP-Host (z.B. `imap.gmx.net`)
   - **Port**: `993` (IMAP mit SSL, standard)
   - **Protokoll**: IMAP
   - **Benutzer**: Deine vollständige Email-Adresse (z.B. `beispiel@gmx.net`)
   - **Passwort**: Das App Password (oder normales Passwort)
5. Klick **"✅ Verbindung testen"**
6. Sollte **"✅ Verbindung erfolgreich"** zeigen
7. Klick **"💾 Speichern"**

---

## 🔧 Setup: POP3 (alternativ)

Falls IMAP nicht funktioniert oder deaktiviert ist:

### Schritt 1: POP3 konfigurieren

1. Öffne **📧 Mail Connector**
2. Wähle **📮 IMAP / POP3** Tab
3. Email-Anbieter: **Sonstiger IMAP-Provider** (POP3 wird auch hier unterstützt)
4. Konfiguriere:
   - **Server**: Dein POP3-Host (z.B. `pop.gmx.net`)
   - **Port**: `995` (POP3 mit SSL, standard)
   - **Protokoll**: POP3
   - **Benutzer**: Deine vollständige Email-Adresse
   - **Passwort**: Das App Password (oder normales Passwort)
5. Klick **"✅ Verbindung testen"**
6. Klick **"💾 Speichern"**

**⚠️ Wichtig bei POP3:**
- Emails werden **gelöscht** vom Server nach Download (kann nicht rückgängig gemacht werden!)
- Nutze POP3 nur wenn IMAP nicht verfügbar
- IMAP ist sicherer und flexibler

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
   - **SMTP-Server**: Siehe Tabelle unten (z.B. `smtp.gmx.net`)
   - **Port**: `587` (STARTTLS, empfohlen) oder `465` (SSL)
   - **Benutzer**: Deine Email
   - **Passwort**: Das 16-stellige App Password (gleich wie oben)
3. Klick **"🧪 Test-Email versenden"**
4. Prüfe dein Email-Posteingang
5. Klick **"💾 Speichern"**

### SMTP-Server für verschiedene Provider

| Provider | SMTP-Server | Port (STARTTLS) | Port (SSL) |
|----------|-------------|-----------------|------------|
| **GMX** | smtp.gmx.net | 587 | 465 |
| **WEB.DE** | smtp.web.de | 587 | 465 |
| **T-Online** | smtp.t-online.de | 587 | 465 |
| **1&1** | smtp.ionos.de | 587 | 465 |
| **Yahoo** | smtp.mail.yahoo.com | 587 | 465 |
| **AOL** | smtp.aol.com | 587 | 465 |
| **Bluewin** | smtp.bluewin.ch | 587 | 465 |

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
1. ✅ **App Password vs. Kontopasswort**: Prüfe ob dein Provider App Passwords nutzt
   - Falls ja: Nutze das 16-stellige **App Password**
   - Falls nein: Nutze dein normales **Kontopasswort**
2. ✅ **Korrekte Email-Adresse**: Prüfe deine **komplette Email-Adresse**
   - ❌ Falsch: `beispiel` (nur Lokalpart)
   - ✅ Richtig: `beispiel@gmx.net` (komplette Adresse)
3. ✅ **Tippfehler im Passwort**: Prüfe dass du das Passwort **exakt kopierst**
   - Leerzeichen, Bindestriche oder Sonderzeichen zählen
4. ✅ **Provider korrekt eingestellt**: Prüfe Server-Host und Port
   - Wrong: `pop.gmx.net` für IMAP (das ist POP3!)
   - Correct: `imap.gmx.net` für IMAP
5. ✅ **2-Schritt-Bestätigung aktiviert**: Prüfe ob dein Provider 2FA erfordert
   - Manche Provider (GMX, WEB.DE) **erfordern** 2FA für App Passwords

### "Verbindung fehlgeschlagen"

**Problem:** Kann nicht zum Server verbinden

**Lösungen:**
1. Prüfe dass **Port nicht blockiert** ist
   - Versuche Port `143` (IMAP mit STARTTLS) statt `993`
   - Falls das funktioniert: Nutze Port 143
2. Prüfe **Internetverbindung**
   - Öffne https://google.com im Browser
   - Falls nicht erreichbar: Prüfe deine Internet-Verbindung
3. Versuche **andere Port-Kombinationen**:
   - Standard IMAP: 993 (SSL) oder 143 (STARTTLS)
   - Standard POP3: 995 (SSL) oder 110 (STARTTLS)
4. Warte **5-10 Minuten** und versuche erneut
   - Server können temporär überlastet sein

### "IMAP ist auf meinem Account nicht aktiviert"

**Problem:** Server sagt IMAP ist deaktiviert

**Lösungen:**
1. Öffne deine Email-Einstellungen
2. Suche **"IMAP aktivieren"**, **"POP3/IMAP aktivieren"**, oder **"Verbundene Apps"**
3. **Aktiviere** die Option
4. **Speichern** und versuche erneut

**Für spezifische Provider:**

**GMX:**
1. Öffne https://www.gmx.net
2. Gehe zu **Einstellungen** → **E-Mail** → **POP3/IMAP**
3. Aktiviere **"IMAP-Zugriff"**

**WEB.DE:**
1. Öffne https://www.web.de
2. Gehe zu **Einstellungen** → **E-Mail** → **POP3/IMAP**
3. Aktiviere **"IMAP-Zugriff"**

**Yahoo:**
1. Öffne https://account.yahoo.com
2. Gehe zu **Sicherheit** → **Bestätigung in zwei Schritten**
3. Prüfe dass **"POP3/IMAP-Zugriff"** aktiviert ist

### "Test-Email kommt nicht an"

**Problem:** SMTP Test schlägt fehl

**Lösungen:**
1. Prüfe **SMTP-Server und Port**
   - Richtig: `smtp.gmx.net` mit Port `587` oder `465`
   - Falsch: `mail.gmx.net` oder Port `25`
2. Nutze **App Password** nicht Kontopasswort
3. Prüfe dass du die **richtige Email** im Benutzer-Feld hast
4. Versuche Port **`587` (STARTTLS)** statt `465`
   - STARTTLS ist häufig zuverlässiger

### Keine Emails werden erkannt

**Problem:** Monitoring läuft aber erkennt keine Bewerbungs-Antworten

**Lösungen:**
1. Prüfe dass Email **tatsächlich eingegangen** ist
   - Öffne dein Email-Konto direkt
   - Siehst du die Email?
2. Prüfe **Junk/Spam-Ordner**
   - Bewerbungs-Antworten landen oft dort
3. Überprüfe dass **Firmennamen** in der Bewerbung stimmt
   - Email-Absender muss exakt wie in Bewerbung sein
4. Gehe zu **⚙️ Einstellungen** → **Email-Keywords**:
   - Füge spezifische Keywords hinzu
   - Z.B. deine Branche oder Firmennamen

### Provider nicht in Tabelle aufgelistet

**Problem:** Mein Email-Provider ist nicht in den Listen

**Lösungen:**
1. Suche online nach deinem Provider
   - Google: `"[mein-provider] IMAP Host Port"`
   - Beispiel: `"arcor IMAP Host Port"`
2. Öffne dein Email-Account online
   - Gehe zu Einstellungen/Sicherheit
   - Suche nach "IMAP", "POP3" oder "Clients"
3. Falls nicht gefunden: Kontaktiere Provider-Support
   - Die meisten großen Provider unterstützen IMAP

---

## 🔒 Sicherheit & Best Practices

### Sicher mit App Passwords

✅ **App Passwords sind sicher weil:**
- Nur Zugriff auf Email (nicht dein ganzes Konto)
- Leicht widerrufbar jederzeit
- Können nicht zum Anmelden bei deinem Account verwendet werden
- 16-stellige Zufallscodes

✅ **Best Practices:**
1. **Nutze App Password statt Kontopasswort** (wenn dein Provider unterstützt)
2. **Generiere ein neues App Password pro Gerät/App**
3. **Widerruf alte App Passwords** wenn du Geräte wechselst
4. **Prüfe regelmäßig** deine App Passwords in deinen Einstellungen
5. **Teile App Passwords nie** mit anderen Personen

### IMAP vs. POP3 Vergleich

| Feature | IMAP | POP3 |
|---------|------|------|
| **Synchronisation** | Cloud ↔ Client | Download nur |
| **Mehrere Geräte** | ✅ Ja | ❌ Nein |
| **Sichere Backup** | ✅ Ja | ⚠️ Nein |
| **Gelöschte Emails wiederherstellen** | ✅ Ja | ❌ Nein |
| **Empfohlene Option** | ✅ Ja | ❌ Nein |

**Empfehlung:** Nutze immer **IMAP** statt POP3!

---

## 📚 Weitere Optionen

Falls du spezifische Plattformen nutzt, siehe:
- [Gmail Setup Guide](SETUP_GMAIL.md)
- [Outlook Setup Guide](SETUP_OUTLOOK.md)

---

## ✅ Checkliste

Vor du anfängst mit Email-Monitoring:

- [ ] Mein Email-Provider ist bekannt
- [ ] Ich habe meinen IMAP-Host und Port gefunden
- [ ] Falls nötig: App Password ist generiert und kopiert
- [ ] IMAP ist auf meinem Account aktiviert
- [ ] Verbindung wurde getestet (**"✅ Erfolgreich"**)
- [ ] Monitoring ist aktiviert in Einstellungen
- [ ] SMTP ist konfiguriert (optional)
- [ ] Erste Test-Email wurde importiert

**Fertig! Deine Emails werden jetzt überwacht!** 🎉

---

## 📞 Support

Falls etwas nicht funktioniert:
1. Überprüfe alle Schritte oben
2. Versuche mit frisch generierten Passwörtern
3. Prüfe dass IMAP auf deinem Account aktiviert ist
4. Suche online nach "[dein-provider] IMAP" für offizielle Dokumentation
5. Kontaktiere deinen Provider-Support für Fragen
