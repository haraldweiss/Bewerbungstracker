# 📋 Bewerbungs-Tracker / Application Tracker

**[Deutsch](#-bewerbungs-tracker---deutsch) | [English](#-application-tracker---english)**

---

## 📋 Bewerbungs-Tracker - Deutsch

Ein datenschutzfreundliches Tool zur Verwaltung von Bewerbungen mit automatischem Email-Monitor, Statistiken und PDF-Export. Alles läuft lokal – keine Cloud, keine Tracking.

### ✨ Kernfeatures

- 📊 **Dashboard** - Status-Verteilung, Erfolgsquoten, Aktivitätszeitleiste
- 📧 **Email-Integration** - Gmail, Outlook, IMAP/POP3 mit Automatischer Überwachung
- 💾 **Datenverwaltung** - JSON Backup, PDF-Export, Soft-Delete
- 🔔 **Benachrichtigungen** - Desktop & Browser Push-Benachrichtigungen
- 🎯 **Bewerbungsverfolgung** - Status, Datum, Gehalt, Notizen, Ghosting-Erkennung
- 🗂️ **Kanban-Board** - Visuelle Übersicht nach Status
- 📋 **CV Vergleich** - Vergleiche deine CV mit Bewerbungsanforderungen
- 🌙 **Dark/Light Mode** - Responsive Design für alle Geräte

### 🚀 Quick Start

1. **Öffne die App:** `index.html` im Browser öffnen
2. **Bewerbung hinzufügen:** "+ Bewerbung" Button oben rechts
3. **Email-Monitoring:** Gehe zu "📧 Mail Connector" und verbinde deinen Email-Account
4. **Daten speichern:** Nutze die Backup-Funktion in den Einstellungen

### 📚 Dokumentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Schritt-für-Schritt Anleitung
- **[Features](docs/FEATURES/)** - Detaillierte Feature-Dokumentation
  - [CV Vergleich & Verarbeitung](docs/FEATURES/CV.md)
  - [Email-Integration](docs/FEATURES/EMAIL.md)
- **[Deployment](docs/DEPLOYMENT/)** - Installation & Hosting
  - [Generic Server](docs/DEPLOYMENT/DEPLOYMENT_GENERIC.md)
  - [IONOS Shared Hosting](docs/DEPLOYMENT/DEPLOYMENT_IONOS.md)
- **[Setup Guides](docs/GUIDES/)** - Provider-spezifische Konfiguration
  - [Gmail Setup](docs/GUIDES/SETUP_GMAIL.md)
  - [Outlook Setup](docs/GUIDES/SETUP_OUTLOOK.md)
  - [IMAP Setup](docs/GUIDES/SETUP_IMAP.md)

### 🔧 Technologie

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (keine Frameworks)
- **Backend:** Python 3 (Flask) + SQLite
- **Libraries:** jsPDF, TweetNaCl.js (Encryption), Mammoth (DOCX), pdf.js

### 💾 Datenschutz

- ✅ Alle Daten lokal im Browser (localStorage)
- ✅ Keine Cloud-Server, keine Tracking
- ✅ Passwörter verschlüsselt mit AES-128-CBC
- ✅ IMAP-Proxy läuft auf localhost (Port 8765)

### 📋 System-Anforderungen

- **Browser:** Chrome, Firefox, Safari, Edge (ES6+)
- **Server** (optional): Python 3.8+ (für SMTP/IMAP-Server)

### 📞 Support

Für Probleme oder Feature-Anfragen: Siehe [GETTING_STARTED.md](docs/GETTING_STARTED.md) für Troubleshooting

---

## 🇬🇧 Application Tracker - English

A privacy-friendly job application tracker with automated email monitoring, statistics, and PDF export. Everything runs locally – no cloud, no tracking.

### ✨ Core Features

- 📊 **Dashboard** - Status distribution, success rates, activity timeline
- 📧 **Email Integration** - Gmail, Outlook, IMAP/POP3 with automatic monitoring
- 💾 **Data Management** - JSON backup, PDF export, soft-delete recovery
- 🔔 **Notifications** - Desktop & browser push notifications
- 🎯 **Application Tracking** - Status, dates, salary, notes, ghosting detection
- 🗂️ **Kanban Board** - Visual overview by status
- 📋 **CV Comparison** - Compare your CV against job requirements
- 🌙 **Dark/Light Mode** - Responsive design for all devices

### 🚀 Quick Start

1. **Open the App:** Open `index.html` in your browser
2. **Add Application:** Click "+ Application" button in top right
3. **Email Monitoring:** Go to "📧 Mail Connector" and connect your email account
4. **Save Data:** Use the backup feature in Settings

### 📚 Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Step-by-step guide
- **[Features](docs/FEATURES/)** - Detailed feature documentation
  - [CV Comparison & Processing](docs/FEATURES/CV.md)
  - [Email Integration](docs/FEATURES/EMAIL.md)
- **[Deployment](docs/DEPLOYMENT/)** - Installation & hosting
  - [Generic Server](docs/DEPLOYMENT/DEPLOYMENT_GENERIC.md)
  - [IONOS Shared Hosting](docs/DEPLOYMENT/DEPLOYMENT_IONOS.md)
- **[Setup Guides](docs/GUIDES/)** - Provider-specific configuration
  - [Gmail Setup](docs/GUIDES/SETUP_GMAIL.md)
  - [Outlook Setup](docs/GUIDES/SETUP_OUTLOOK.md)
  - [IMAP Setup](docs/GUIDES/SETUP_IMAP.md)

### 🔧 Technology

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (no frameworks)
- **Backend:** Python 3 (Flask) + SQLite
- **Libraries:** jsPDF, TweetNaCl.js (Encryption), Mammoth (DOCX), pdf.js

### 💾 Privacy

- ✅ All data stored locally in browser (localStorage)
- ✅ No cloud servers, no tracking
- ✅ Passwords encrypted with AES-128-CBC
- ✅ IMAP proxy runs on localhost (Port 8765)

### 📋 System Requirements

- **Browser:** Chrome, Firefox, Safari, Edge (ES6+)
- **Server** (optional): Python 3.8+ (for SMTP/IMAP server)

### 📞 Support

For issues or feature requests: See [GETTING_STARTED.md](docs/GETTING_STARTED.md) for troubleshooting
