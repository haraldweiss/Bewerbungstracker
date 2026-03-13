# 📋 Bewerbungs-Tracker / Application Tracker

**[Deutsch](#-bewerbungs-tracker---deutsch) | [English](#-application-tracker---english)**

---

## 📋 Bewerbungs-Tracker - Deutsch

Ein leistungsstarkes, datenschutzfreundliches Tool zur Verwaltung von Bewerbungen und Verfolgung deiner Jobsuche. Gebaut mit vanilla JavaScript, Python und jsPDF für ein nahtloses Erlebnis.

### ✨ Features

#### 📊 Dashboard & Analysen
- **Visuelle Status-Verteilung** - Verfolge Bewerbungen nach Status (Beworben, Antwort, Interview, Zusage, Absage, Ghosting)
- **Kennzahlen** - Gesamtbewerbungen, offene Positionen, Interviews, Zusagen, Absagen
- **Rückmeldungsquote** - Sehe den Prozentsatz der Bewerbungen mit Rückmeldung
- **Aktivitätszeitleiste** - Überwache letzte Änderungen

#### 📧 Email-Integration
- **Gmail/Outlook/IMAP-Support** - Verbinde mit mehreren Email-Providern über sichere IMAP-Proxy
- **Intelligente Email-Erkennung** - Erkennt automatisch bewerbungsrelevante Emails
- **Reduzierte Falsch-Positive** - Fortgeschrittene Filterung zur Minimierung falscher Treffer
- **Batch-Import** - Importiere mehrere Emails gleichzeitig
- **Datum-Filterung** - Setze Startdatum, um nur aktuelle Emails zu importieren
- **Benutzerdefinierte Keywords** - Füge deine eigenen Keywords hinzu (auch kurze wie "CV", "HR")

#### 💾 Datenverwaltung
- **JSON Backup/Wiederherstellung** - Vollständiges Backup aller Bewerbungen und Einstellungen
- **PDF-Export** - Generiere professionelle PDF-Berichte mit anklickbaren Job-Links
- **Keine Cloud-Speicherung** - Alle Daten lokal im Browser (localStorage)
- **Einstellungs-Synchronisation** - Sicherung und Wiederherstellung aller Konfigurationen

#### 🎯 Bewerbungsverfolgung
- **Umfangreiche Bewerbungsdaten** - Speichere Firma, Position, Status, Datum, Gehalt, Ort, Email, Link, Notizen
- **Schnelle Status-Updates** - Ändere Status direkt aus der Liste
- **Suche & Filter** - Finde Bewerbungen nach Firma, Position oder Quelle
- **Ghosting-Erkennung** - Markiert automatisch Bewerbungen ohne Rückmeldung nach X Tagen
- **Mehrere Quellen** - Verfolge Bewerbungen aus Gmail, LinkedIn, Indeed, XING, Websites und manuell

#### 🌙 Benutzeroberfläche
- **Dark/Light Mode** - Wechsle zwischen dunklem und hellem Theme
- **Responsive Design** - Funktioniert nahtlos auf Desktop und Mobilgeräten
- **Toast-Benachrichtigungen** - Echtzeitfeedback für alle Aktionen

### 🚀 Schnellstart

#### Voraussetzungen
- Python 3.7+ (für IMAP-Proxy)
- Moderner Webbrowser (Chrome, Firefox, Safari, Edge)

#### Installation

1. **Repository klonen**
   ```bash
   git clone https://github.com/haraldweiss/Bewerbungstracker.git
   cd Bewerbungstracker
   ```

2. **Web Server starten**
   ```bash
   python3 -m http.server 8080 --directory .
   ```
   Öffne dann `http://localhost:8080` in deinem Browser

3. **IMAP-Proxy starten** (für Email-Integration)
   ```bash
   python3 imap_proxy.py
   ```
   Der Proxy läuft auf `http://localhost:8765` (nur localhost aus Sicherheitsgründen)

#### Mit Launch-Konfiguration

Wenn Claude Code installiert ist:
```bash
# Konfiguration ist in .claude/launch.json
preview_start "Web Server"
preview_start "IMAP Proxy"
```

### 📖 Verwendung

#### Bewerbungen manuell hinzufügen
1. Klicke auf **"+ Bewerbung"** Button
2. Fülle Firma, Position, Datum und weitere Details aus
3. Füge den Job-Link ein
4. Klicke **"💾 Speichern"**

#### Email verbinden

**Gmail/Yahoo/Outlook:**
1. Gehe zu **Einstellungen → Mail Connector**
2. Wähle deinen Provider aus der Dropdown
3. Gib deine Email und **App-Passwort** ein (nicht dein normales Passwort!)
4. Klicke **"Verbinden"**

**Andere IMAP-Provider:**
1. Gib IMAP-Host, Port und Protokoll manuell ein
2. Verwende deine Email-Anmeldedaten (App-Passwort empfohlen)
3. Der Proxy verbindet sich sicher mit deinem Email-Provider

#### Emails importieren
1. Gehe zu **Mail Connector**
2. Wähle Importmethode:
   - **Script Emails**: Via Google Apps Script
   - **EML Dateien**: Aus heruntergeladenen .eml Dateien
   - **IMAP/POP3**: Live-Verbindung zum Email-Server
3. Setze optional **Startdatum**, um alte Emails zu vermeiden
4. Vorschau und selektives Importieren von Emails

#### Daten exportieren
- **JSON Backup**: Einstellungen → "📥 JSON Backup" (alle Daten und Einstellungen)
- **PDF Report**: Einstellungen → "📄 PDF Export" (mit anklickbaren Job-Links)
- **JSON Import**: Einstellungen → "📤 JSON Import" (aus Backup wiederherstellen)

### 🔒 Sicherheit & Datenschutz

#### Local-First Architektur
- **Keine Cloud-Speicherung** - Alle Daten bleiben in deinem Browser
- **Keine Server-Anmeldung** - Keine Authentifizierung, keine Benutzerkonten
- **Kein Tracking** - Keine Analytik, keine Datenerfassung

#### IMAP-Proxy Sicherheit
- **Nur Localhost** - Proxy bindet an 127.0.0.1 (kein Netzwerkzugriff)
- **Passwort-Schutz** - Passwörter werden nicht geloggt, gecacht oder gespeichert
- **Nur Lesezugriff** - IMAP im readonly-Modus, POP3 ohne DELETE
- **SSL/TLS** - Verschlüsselte Verbindungen mit Zertifikatsprüfung
- **IP-Validierung** - Zusätzliche Sicherheitsprüfung bei jedem Request

#### Datenschutz
- Sensible Daten ausgeschlossen aus localStorage
- Backups enthalten keine Passwörter
- App-Passwörter empfohlen statt normaler Passwörter

### ⚙️ Konfiguration

#### Email-Keywords
Bearbeite Keywords für automatische Email-Erkennung in **Einstellungen**. Standard beinhaltet:
- Bewerbung, Application, Stelle, Interview, Absage, Zusage, Job, Recruiting, Kandidat

Du kannst deine eigenen Keywords hinzufügen, auch kurze wie "CV", "HR", "IT".

#### Ghosting-Schwelle
Setze Tage ohne Rückmeldung, bevor als Ghosting markiert (Standard: 30 Tage)

#### Email-Import Datum-Filter
Setze Startdatum, um Emails nur aus bestimmter Periode zu importieren (optional)

### 📁 Projektstruktur

```
Bewerbungstracker/
├── index.html              # Hauptanwendung (HTML + CSS + JavaScript)
├── imap_proxy.py          # Python IMAP/POP3 Proxy (Port 8765)
├── config.json            # Proxy-Konfiguration
├── ANLEITUNG_IMAP.md      # IMAP-Dokumentation
├── README.md              # Diese Datei
├── .gitignore             # Git-Ignore-Regeln
└── .claude/
    └── launch.json        # Dev Server Konfiguration
```

### 🛠️ Technologien

- **Frontend**: HTML5, CSS3, JavaScript (Vanilla - keine Frameworks)
- **Backend**: Python 3 (IMAP/POP3 Proxy)
- **PDF-Generierung**: jsPDF + jsPDF AutoTable
- **Speicherung**: Browser localStorage (kein Backend)
- **Icons**: Unicode Emojis

### 📊 Datenformat

#### Bewerbungs-Objekt
```json
{
  "id": "bew_1234567890_abc123",
  "firma": "Firma GmbH",
  "position": "Software Engineer",
  "status": "beworben",
  "datum": "2024-03-12",
  "gehalt": "60.000-80.000 EUR",
  "ort": "Berlin",
  "email": "hr@firma.de",
  "quelle": "gmail",
  "link": "https://...",
  "notizen": "...",
  "createdAt": "2024-03-12T...",
  "updatedAt": "2024-03-12T..."
}
```

#### Status-Werte
- `beworben` - Beworben
- `antwort` - Antwort erhalten
- `interview` - Interview vereinbart
- `zusage` - Jobangebot
- `absage` - Ablehnung
- `ghosting` - Keine Rückmeldung (automatisch markiert)

### 🐛 Fehlerbehebung

#### IMAP-Proxy Verbindungsprobleme
1. Überprüfe IMAP-Host und Port
2. Verwende **App-Passwort** (nicht normales Passwort) für Gmail/Yahoo
3. Aktiviere "Unsichere Apps" wenn normales Passwort bei Gmail verwendet
4. Verifiziere Proxy läuft: `python3 imap_proxy.py`

#### Email-Import funktioniert nicht
1. Überprüfe Email-Anmeldedaten
2. Stelle sicher IMAP ist in Email-Einstellungen aktiviert
3. Versuche spezifischen Datumbereich zu importieren
4. Überprüfe Browser-Konsole auf Fehlermeldungen

#### PDF Export funktioniert nicht
1. Stelle sicher du hast Bewerbungen zum Exportieren
2. Überprüfe Browser-Konsole auf JavaScript-Fehler
3. Versuche mit Browser-Developer-Tools

---

## 📋 Application Tracker - English

A powerful, privacy-focused application for managing job applications and tracking your recruitment journey. Built with vanilla JavaScript, Python, and jsPDF for a seamless experience.

### ✨ Features

#### 📊 Dashboard & Analytics
- **Visual Status Distribution** - Track applications by status (Applied, Response, Interview, Offer, Rejection, Ghosting)
- **Key Metrics** - Total applications, open positions, interviews, offers, rejections
- **Response Rate** - See what percentage of applications have received responses
- **Activity Timeline** - Monitor recent application changes

#### 📧 Email Integration
- **Gmail/Outlook/IMAP Support** - Connect to multiple email providers via secure IMAP proxy
- **Smart Email Detection** - Automatically identifies recruitment-related emails with keyword matching
- **False Positive Reduction** - Advanced filtering to minimize incorrect classifications
- **Batch Import** - Import multiple emails at once
- **Date Filtering** - Set a start date to only import recent emails
- **Custom Keywords** - Add your own keywords (even short ones like "CV", "HR")

#### 💾 Data Management
- **JSON Backup/Restore** - Full backup of all applications and settings
- **PDF Export** - Generate professional PDF reports with clickable job links
- **No Cloud Storage** - All data stored locally in browser (localStorage)
- **Settings Sync** - Backup and restore all configurations including keywords, email filters, and provider settings

#### 🎯 Application Tracking
- **Rich Application Data** - Store company, position, status, date, salary, location, contact email, job link, and notes
- **Quick Status Updates** - Change application status directly from the list
- **Search & Filter** - Find applications by company, position, or source
- **Ghosting Detection** - Automatically mark applications as ghosting after X days without response
- **Multiple Sources** - Track applications from Gmail, LinkedIn, Indeed, XING, websites, and manual entries

#### 🌙 UI/UX
- **Dark/Light Mode** - Toggle between dark and light themes
- **Responsive Design** - Works seamlessly on desktop and mobile
- **Toast Notifications** - Real-time feedback for all actions

### 🚀 Quick Start

#### Prerequisites
- Python 3.7+ (for IMAP proxy)
- Modern web browser (Chrome, Firefox, Safari, Edge)

#### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/haraldweiss/Bewerbungstracker.git
   cd Bewerbungstracker
   ```

2. **Start the Web Server**
   ```bash
   python3 -m http.server 8080 --directory .
   ```
   Then open `http://localhost:8080` in your browser

3. **Start the IMAP Proxy** (for email integration)
   ```bash
   python3 imap_proxy.py
   ```
   The proxy runs on `http://localhost:8765` (localhost-only for security)

#### Using Launch Configuration

If you have Claude Code installed:
```bash
# Configuration is in .claude/launch.json
preview_start "Web Server"
preview_start "IMAP Proxy"
```

### 📖 Usage

#### Adding Applications Manually
1. Click **"+ Bewerbung"** button
2. Fill in company, position, date, and other details
3. Paste the job link
4. Click **"💾 Speichern"** to save

#### Connecting Email

**Gmail/Yahoo/Outlook:**
1. Go to **Settings → Mail Connector**
2. Select your provider from the dropdown
3. Enter your email and **app password** (not your regular password!)
4. Click **"Verbinden"**

**Other IMAP Providers:**
1. Enter IMAP host, port, and protocol manually
2. Use your email credentials (app password recommended)
3. The proxy securely connects to your email provider

#### Importing Emails
1. Go to **Mail Connector**
2. Choose import method:
   - **Script Emails**: Via Google Apps Script
   - **EML Files**: Import from downloaded .eml files
   - **IMAP/POP3**: Live connection to email server
3. Set optional **start date** to avoid importing old emails
4. Preview and selectively import emails

#### Exporting Data
- **JSON Backup**: Settings → "📥 JSON Backup" (includes all data and settings)
- **PDF Report**: Settings → "📄 PDF Export" (clickable links to job postings)
- **JSON Import**: Settings → "📤 JSON Import" (restore from backup)

### 🔒 Security & Privacy

#### Local-First Architecture
- **No Cloud Storage** - All data remains in your browser
- **No Server Login** - No authentication, no user accounts
- **No Tracking** - No analytics, no data collection

#### IMAP Proxy Security
- **Localhost-Only** - Proxy binds to 127.0.0.1 (no network access)
- **Credential Protection** - Passwords never logged, cached, or stored
- **Read-Only Access** - IMAP in readonly mode, POP3 without DELETE
- **SSL/TLS** - Encrypted connections with certificate validation
- **IP Validation** - Extra security check on every request

#### Data Protection
- Sensitive data excluded from localStorage
- Backups don't include passwords
- App passwords recommended over regular passwords

### ⚙️ Configuration

#### Email Keywords
Edit keywords used for automatic email detection in **Settings**. Default includes:
- Bewerbung, Application, Stelle, Interview, Absage, Zusage, Job, Recruiting, Kandidat

You can add your own keywords, including short ones like "CV", "HR", "IT".

#### Ghosting Threshold
Set days without response before marking as ghosting (default: 30 days)

#### Email Import Date Filter
Set a start date to only import emails from specific period (optional)

### 📁 Project Structure

```
Bewerbungstracker/
├── index.html              # Main application (HTML + CSS + JavaScript)
├── imap_proxy.py          # Python IMAP/POP3 proxy (port 8765)
├── config.json            # Proxy configuration
├── ANLEITUNG_IMAP.md      # IMAP documentation
├── README.md              # This file
├── .gitignore             # Git ignore rules
└── .claude/
    └── launch.json        # Dev server configuration
```

### 🛠️ Technologies

- **Frontend**: HTML5, CSS3, JavaScript (Vanilla - no frameworks)
- **Backend**: Python 3 (IMAP/POP3 Proxy)
- **PDF Generation**: jsPDF + jsPDF AutoTable
- **Storage**: Browser localStorage (no backend database)
- **Icons**: Unicode Emojis

### 📊 Data Format

#### Application Object
```json
{
  "id": "bew_1234567890_abc123",
  "firma": "Company GmbH",
  "position": "Software Engineer",
  "status": "beworben",
  "datum": "2024-03-12",
  "gehalt": "60,000-80,000 EUR",
  "ort": "Berlin",
  "email": "hr@company.de",
  "quelle": "gmail",
  "link": "https://...",
  "notizen": "...",
  "createdAt": "2024-03-12T...",
  "updatedAt": "2024-03-12T..."
}
```

#### Status Values
- `beworben` - Applied
- `antwort` - Response received
- `interview` - Interview scheduled
- `zusage` - Job offer
- `absage` - Rejection
- `ghosting` - No response (auto-marked)

#### Source Values
- `gmail` - Gmail
- `imap` - IMAP/POP3
- `manuell` - Manual entry
- `linkedin` - LinkedIn
- `indeed` - Indeed
- `xing` - XING
- `website` - Company website
- `empfehlung` - Referral

### 🐛 Troubleshooting

#### IMAP Proxy Connection Issues
1. Check IMAP host and port are correct
2. Use **app password** (not regular password) for Gmail/Yahoo
3. Enable "Less secure apps" if using Gmail with regular password
4. Verify proxy is running: `python3 imap_proxy.py`

#### Email Import Not Working
1. Check email account credentials
2. Ensure IMAP is enabled in email settings
3. Try importing a specific date range
4. Check browser console for error messages

#### PDF Not Exporting
1. Ensure you have applications to export
2. Check browser console for JavaScript errors
3. Try using browser's developer tools if export fails silently

---

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests with improvements or bug fixes.

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Made with ❤️ for managing your job search efficiently and privately**

**Gemacht mit ❤️ um deine Jobsuche effizient und privat zu verwalten**
