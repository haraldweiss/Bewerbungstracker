# 🚀 Getting Started - Bewerbungs-Tracker

Willkommen! Diese Anleitung zeigt dir, wie du mit dem Bewerbungs-Tracker startest.

## Installation

### Option 1: Lokal (Keine Installation nötig)
1. Öffne `index.html` direkt im Browser
2. Die App lädt sofort - es ist keine Internetverbindung nötig!
3. Deine Daten werden lokal gespeichert

### Option 2: Mit Python-Server (für IMAP/SMTP)
Wenn du Email-Monitoring aktivieren möchtest:
```bash
cd Bewerbungstracker
python3 app.py
```
Öffne dann `http://localhost:5000/` im Browser

### Option 3: Hosted
Siehe [Deployment Guides](DEPLOYMENT/) für Hosting-Optionen

---

## 🎯 Erste Schritte

### 1. Deine erste Bewerbung hinzufügen
1. Klicke auf "+ Bewerbung" oben rechts
2. Fülle das Formular aus:
   - **Firma** - Unternehmen (z.B. "Google")
   - **Position** - Job-Titel (z.B. "Software Engineer")
   - **Status** - Aktuelle Phase (Beworben, Interview, Zusage, etc.)
   - **Datum** - Wann hast du dich beworben
   - **Quelle** - Wo hast du die Stelle gefunden (LinkedIn, XING, Website, etc.)
3. Optional: Gehalt, Ort, Email, Job-Link, Notizen
4. Klicke "Speichern"

### 2. Dashboard erkunden
Das Dashboard zeigt dir:
- **Statistiken** - Gesamtbewerbungen, offene Positionen, Erfolgsquote
- **Status-Verteilung** - Visuelle Übersicht deiner Bewerbungen
- **Letzte Aktivitäten** - Deine kürzlichen Änderungen

### 3. Email-Monitoring (optional)
Gehe zu "📧 Mail Connector":
1. Wähle deine Email-Plattform (Gmail, Outlook, Yahoo, IMAP)
2. Folge der Anleitung für deine Plattform
3. **Die App wird dann automatisch nach Antworten suchen!**

Setup-Guides für spezifische Provider:
- [Gmail Setup](GUIDES/SETUP_GMAIL.md)
- [Outlook Setup](GUIDES/SETUP_OUTLOOK.md)
- [IMAP Setup](GUIDES/SETUP_IMAP.md)

---

## 📊 Hauptfunktionen

### Bewerbungen verwalten (📁 Bewerbungen)
- **Suchen & Filtern** - Finde Bewerbungen nach Firma oder Position
- **Status aktualisieren** - Ändere Status mit einem Klick
- **Ghosting prüfen** - Findet automatisch Bewerbungen ohne Antwort
- **PDF Export** - Exportiere deine Übersicht als PDF
- **Gelöschte Einträge** - Wiederherstellung von gelöschten Bewerbungen

### Kanban-Board (🗂️ Kanban)
Visuelle Spalten für jeden Status - ziehe Bewerbungen zwischen Spalten

### CV Vergleich (📋 CV Vergleich)
1. Lade deine CV (PDF oder DOCX) hoch
2. Paste eine Stellenausschreibung
3. Die App vergleicht deine Skills mit den Anforderungen
4. Nutze das Feedback um deine CV zu verbessern

Siehe [CV Guide](FEATURES/CV.md) für Details

### Benachrichtigungen (⚙️ Einstellungen)
- **Desktop Notifications** - Erhalte Benachrichtigungen auf deinem Desktop
- **Automatische Antwort-Benachrichtigung** - Wird benachrichtigt wenn eine Antwort erkannt wird
- **Nur lokal** - Keine Cloud-Daten

### Daten speichern & zurückstellen
1. Gehe zu "⚙️ Einstellungen"
2. **Backup speichern** - Downloade deine Daten als JSON
3. **Backup wiederherstellen** - Importiere vorherige Backups
4. Die Daten werden auch automatisch lokal im Browser gespeichert

---

## 🔒 Datenschutz & Sicherheit

✅ **Deine Daten gehört dir:**
- Alle Daten bleiben auf deinem Computer/Browser
- Keine Cloud-Server, kein Tracking
- Du kontrollierst wo deine Daten gespeichert werden

✅ **Passwörter sind sicher:**
- Email-Passwörter werden mit AES-128-Bit verschlüsselt
- Keine Passwörter werden jemals im Klartext gespeichert

✅ **Email-Proxy:**
- Der IMAP-Proxy (falls aktiviert) läuft nur lokal auf Port 8765
- Deine Emails werden nicht auf externen Servern synchronisiert

---

## ❓ FAQ

### Q: Wo werden meine Daten gespeichert?
**A:** Im Browser-LocalStorage deines Geräts. Nicht in der Cloud!

### Q: Kann ich meine Daten exportieren?
**A:** Ja! Gehe zu Einstellungen → "Backup speichern" um eine JSON-Datei zu downloaden

### Q: Funktioniert die App ohne Internet?
**A:** Ja, wenn du nur Bewerbungen verwalten möchtest. Für IMAP/SMTP brauchst du Internetverbindung.

### Q: Kann ich mehrere Email-Accounts überwachen?
**A:** Zurzeit 1 pro Installation. Öffne mehrere Tabs für mehrere Accounts.

### Q: Warum wird meine Bewerbung als "Ghosting" markiert?
**A:** Wenn mehr als X Tage vergangen sind ohne Status-Update. Ändere die Tage in den Einstellungen.

### Q: Wie kann ich die App aktualisieren?
**A:** Siehe [Deployment Guides](DEPLOYMENT/) für Aktualisierungsanweisungen

---

## 🆘 Troubleshooting

### Problem: Email-Imports funktionieren nicht
**Lösung:**
1. Prüfe deine Email-Anmeldedaten
2. Für Gmail: [Gmail Setup](GUIDES/SETUP_GMAIL.md)
3. Für andere: [IMAP Setup](GUIDES/SETUP_IMAP.md)

### Problem: Benachrichtigungen funktionieren nicht
**Lösung:**
1. Prüfe Browser-Permissions (Settings → Notifications)
2. Erlaube Benachrichtigungen für diese Website
3. Versuche Benachrichtigungen zu testen

### Problem: Daten sind weg!
**Lösung:**
1. Prüfe die LocalStorage: Öffne DevTools (F12) → Application → LocalStorage
2. Falls gelöscht: Wiederherstellung von Backup in Einstellungen
3. Stelle sicher dass du nicht im Private-Mode browst (wird gelöscht beim Schließen)

### Problem: Alte Daten von meinem alten Computer?
**Lösung:**
1. Auf altem Computer: Settings → "Backup speichern"
2. Auf neuem Computer: Settings → "Backup wiederherstellen"
3. Wähle die JSON-Datei

---

## 📚 Weitere Dokumentation

- [Email-Integration Details](FEATURES/EMAIL.md)
- [CV Vergleich Guide](FEATURES/CV.md)
- [Deployment Options](DEPLOYMENT/)
- [Email Provider Setup](GUIDES/)

---

**Viel Erfolg bei deiner Jobsuche! 🎉**
