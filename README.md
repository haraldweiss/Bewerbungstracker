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
- 🔍 **Job-Discovery** - Automatische Stellensuche aus RSS-Feeds + Bundesagentur/Adzuna/Arbeitnow APIs mit Claude-basiertem Match-Score gegen deinen CV. Inkl. Quellen-Verwaltung, Pagination, Volltextsuche, Filter (Remote/PLZ/Anstellungsart), Browser-Push für Top-Matches und Onboarding-Checkliste
- 👤 **Multi-User mit Admin-Approval** - User registrieren sich selbst, Admin schaltet Konten + Job-Discovery frei
- 🔐 **Envelope-Encryption** - Pro-User-DEK + KEK aus Passwort, Backups bleiben bei Passwort-Reset entschlüsselbar
- 🌙 **Dark/Light Mode** - Responsive Design für alle Geräte

### 🚀 Quick Start

**Für User:**
1. **Account anlegen:** `/login` aufrufen → Registrieren → Email bestätigen → Admin-Freigabe abwarten
2. **CV hochladen:** Tab "📋 CV Vergleich" → Upload (PDF/DOCX)
3. **Job-Discovery aktivieren:** Modal beim ersten CV-Upload bestätigen → Admin schaltet frei
4. **Bewerbungen tracken:** "+ Bewerbung" Button oder Übernahme aus Job-Vorschlägen
5. **Email-Monitoring:** Tab "📧 Mail Connector" → Provider verbinden

**Für Admins (Server-Setup):**
```bash
# Initial-Setup
python scripts/migrate_job_discovery.py     # DB-Schema
python scripts/seed_job_sources.py          # 3 globale Default-Quellen

# ENV-Vars
export JOB_CRON_TOKEN=<random-secret-32+chars>
export ANTHROPIC_API_KEY=<dein-key>
export CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001

# Cron einrichten (entweder system-cron oder cron-job.org)
# 5 Endpoints: /api/jobs/{crawl-source,prefilter,claude-match,notify,cleanup}
```

### 📚 Dokumentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Schritt-für-Schritt Anleitung
- **[Features](docs/FEATURES/)** - Detaillierte Feature-Dokumentation
  - [CV Vergleich & Verarbeitung](docs/FEATURES/CV.md)
  - [Email-Integration](docs/FEATURES/EMAIL.md)
  - [Job-Discovery](docs/FEATURES/JOB_DISCOVERY.md)
- **[Deployment](docs/DEPLOYMENT/)** - Installation & Hosting
  - [Generic Server](docs/DEPLOYMENT/DEPLOYMENT_GENERIC.md)
  - [IONOS Shared Hosting](docs/DEPLOYMENT/DEPLOYMENT_IONOS.md)
- **[Setup Guides](docs/GUIDES/)** - Provider-spezifische Konfiguration
  - [Gmail Setup](docs/GUIDES/SETUP_GMAIL.md)
  - [Outlook Setup](docs/GUIDES/SETUP_OUTLOOK.md)
  - [IMAP Setup](docs/GUIDES/SETUP_IMAP.md)

### 🔧 Technologie

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (keine Frameworks), PWA mit Service-Worker
- **Backend:** Python 3 (Flask) + SQLite + JWT-Auth
- **Job-Pipeline:** 5 Cron-Stages (crawl → prefilter → claude-match → notify → cleanup), idempotent + Token-geschützt
- **Source-Adapter:** RSS (`feedparser`), Adzuna-API, Bundesagentur Jobsuche-API (mit parallel Detail-Fetch), Arbeitnow-API
- **AI:** Anthropic Claude SDK (Haiku-4.5 default) für Job↔CV Match-Scoring mit Cost-Tracking pro User
- **Libraries:** jsPDF, TweetNaCl.js, Mammoth (DOCX), pdf.js, cryptography (Fernet)

### 💾 Datenschutz

- ✅ Self-Hosted — keine Cloud-Abhängigkeiten, keine Tracker, keine Analytics
- ✅ **Envelope-Encryption** für sensible User-Daten (Backups, IMAP-Credentials): pro-User Data-Encryption-Key (DEK), gewrapped mit aus Passwort abgeleitetem KEK (PBKDF2 600k iterations)
- ✅ User-spezifischer localStorage wird beim Logout vollständig gelöscht (kein Daten-Leak zwischen Usern auf gemeinsamen Browsern)
- ✅ Passwörter verschlüsselt mit AES-128-CBC + Fernet
- ✅ IMAP-Proxy läuft auf localhost (Port 8765)
- ✅ JWT-Tokens mit konfigurierbarer TTL, Refresh-Token-Flow

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
- 🔍 **Job-Discovery** - Automated job search from RSS feeds + Bundesagentur/Adzuna/Arbeitnow APIs with Claude-based match-scoring against your CV. Includes source management, pagination, full-text search, filters (Remote/postal-code/employment-type), browser push notifications for top matches, and onboarding checklist
- 👤 **Multi-User with Admin Approval** - Users self-register, admin approves accounts + Job-Discovery activation
- 🔐 **Envelope-Encryption** - Per-user DEK + KEK derived from password, backups remain decryptable on password reset
- 🌙 **Dark/Light Mode** - Responsive design for all devices

### 🚀 Quick Start

**For users:**
1. **Create account:** Visit `/login` → Register → Confirm email → Wait for admin approval
2. **Upload CV:** Tab "📋 CV Comparison" → Upload (PDF/DOCX)
3. **Activate Job-Discovery:** Confirm modal on first CV upload → Admin approves
4. **Track applications:** "+ Application" button or import from Job suggestions
5. **Email monitoring:** Tab "📧 Mail Connector" → Connect provider

**For admins (server setup):**
```bash
# Initial setup
python scripts/migrate_job_discovery.py     # DB schema
python scripts/seed_job_sources.py          # 3 global default sources

# ENV vars
export JOB_CRON_TOKEN=<random-secret-32+chars>
export ANTHROPIC_API_KEY=<your-key>
export CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001

# Cron setup (system cron or cron-job.org)
# 5 endpoints: /api/jobs/{crawl-source,prefilter,claude-match,notify,cleanup}
```

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
