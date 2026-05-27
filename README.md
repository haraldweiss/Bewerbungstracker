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
- 📅 **Kalender-Export (.ics)** - Im Detail-Modal jeder Bewerbung mit Status `antwort`/`interview`/`zusage`: ein Klick lädt eine `.ics`-Datei mit Interview-Termin, Teams-/Zoom-Link, Passcode und Teilnehmer. Importierbar in Apple Calendar, Google Calendar, Outlook. Termin wird aus den Notizen oder zugeordneten Email-Bodies geparsed (Datum, Link, Passcode), keine DB-Migration, keine OAuth
- 📋 **CV Vergleich** - Vergleiche deine CV mit Bewerbungsanforderungen — direkte Analyse via konfiguriertem KI-Provider (mit Fallback) oder Copy-Paste an Web-Plattformen
- ✍️ **Anschreiben-Generator** - Generiert deutsche Anschreiben aus CV + Stellenausschreibung. Confidence-Scoring pro Absatz (grün = faktisch / gelb = überwiegend faktisch / orange = interpretiert), Export als PDF oder DOCX, Detailanalyse mit Skill-Matching, Pre-Fill aus Job-Vorschlägen. Erfindet keine Skills — nutzt nur was im CV/Job-Posting steht
- 🤖 **Multi-Provider AI** - Claude (Anthropic), lokales Ollama, ChatGPT/OpenAI, Mammouth, eigener OpenAI-kompatibler Endpoint. Per-User-Konfiguration mit verschlüsselten API-Keys. Optional: Fallback-Provider und Queue-Persistenz bei Nicht-Erreichbarkeit (z.B. lokales Ollama)
- 🎯 **Pro-Task-Modelle** - Verschiedene Modelle pro KI-Task (Job-Match, Cover-Letter, CV-Summarize, Email-Analyse) frei konfigurierbar. Heuristische Empfehlungs-Engine bewertet jedes Modell pro Task (✅/⚠️/❌). Z.B. kleines lokales Ollama-Modell für Job-Matching, Claude für Anschreiben
- 🌐 **Multi-User Local-Ollama via Tailscale** - mehrere User können ihr eigenes Ollama anbinden ohne Port-Konflikt. VPS + User-Macs in einem privaten Tailnet, ACL erlaubt nur Port 11434 pro Member. Siehe Handbuch-Sektion *"Eigenes Ollama anbinden"* + [deploy/tailscale-acl.hujson](deploy/tailscale-acl.hujson)
- 🔍 **Job-Discovery** - Automatische Stellensuche aus RSS-Feeds + Bundesagentur/Adzuna/Arbeitnow APIs mit KI-Match-Score gegen deinen CV (Provider frei wählbar). Inkl. Quellen-Verwaltung, Pagination, Volltextsuche, Filter (Remote/PLZ/Anstellungsart), Browser-Push für Top-Matches und Onboarding-Checkliste
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

# ENV-Vars (Pflicht)
export JOB_CRON_TOKEN=<random-secret-32+chars>
export ANTHROPIC_API_KEY=<dein-key>
export CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001

# Optional: zentralen ai-provider-service nutzen (Multi-Provider + Fallback + Queue)
# Wenn gesetzt, werden alle KI-Calls dorthin delegiert.
export AI_PROVIDER_SERVICE_URL=http://127.0.0.1:8767
export AI_PROVIDER_SERVICE_TOKEN=<service-token>

# Cron einrichten (entweder system-cron oder cron-job.org)
# 5 Endpoints: /api/jobs/{crawl-source,prefilter,claude-match,notify,cleanup}
```

**Optional: ai-provider-service** — separates Repo, läuft als systemd-Unit auf
Port 8767 und kapselt alle Provider hinter einer einheitlichen REST-API.
Vorteile: zentrale API-Key-Verwaltung, automatischer Fallback, Queue-Persistenz
bei lokalen Providern (z.B. Ollama auf Mac via autossh-Reverse-Tunnel).
Setup-Anleitung im jeweiligen Repo.

### 📚 Dokumentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Schritt-für-Schritt Anleitung
- **[Features](docs/FEATURES/)** - Detaillierte Feature-Dokumentation
  - [CV Vergleich & Verarbeitung](docs/FEATURES/CV.md)
  - [Email-Integration](docs/FEATURES/EMAIL.md)
  - [Job-Discovery](docs/FEATURES/JOB_DISCOVERY.md)
- **[Deployment](docs/DEPLOYMENT/)** - Installation & Hosting
  - [Generic Server](docs/DEPLOYMENT/DEPLOYMENT_GENERIC.md)
  - [IONOS Shared Hosting](docs/DEPLOYMENT/DEPLOYMENT_IONOS.md)
  - [API-Key Rotation](docs/DEPLOYMENT/KEY_ROTATION.md) - Anthropic-Key auf VPS rotieren via `bewerbungen-rotate-anthropic-key`
  - **[Apache ProxyPass Deployment Rules](DEPLOYMENT.md)** - ⚠️ Safety-Checklist für Multi-Service VPS mit Safeguards gegen Config-Konflikte
- **[Setup Guides](docs/GUIDES/)** - Provider-spezifische Konfiguration
  - [Gmail Setup](docs/GUIDES/SETUP_GMAIL.md)
  - [Outlook Setup](docs/GUIDES/SETUP_OUTLOOK.md)
  - [IMAP Setup](docs/GUIDES/SETUP_IMAP.md)

### 🔧 Technologie

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (keine Frameworks), PWA mit Service-Worker
- **Backend:** Python 3.12 (Flask) + SQLite + JWT-Auth; modulare `services/`-Schicht für KI-Matching, Email-Import, Provider-Routing und Task-Queue-Worker
- **Job-Pipeline:** 5 Cron-Stages (crawl → prefilter → claude-match → notify → cleanup), idempotent + Token-geschützt, teils über async Task-Queue
- **Source-Adapter:** RSS (`feedparser`), Adzuna-API, Bundesagentur Jobsuche-API (mit parallel Detail-Fetch), Arbeitnow-API
- **AI-Routing:** entweder Anthropic Claude SDK direkt (Default), oder Delegation an externen `ai-provider-service` (separates Repo) für Multi-Provider, Fallback und Queue-Persistenz. Beide Modi via gleicher User-Settings-UI bedienbar.
- **Libraries:** jsPDF, TweetNaCl.js, Mammoth (DOCX), pdf.js, cryptography (Fernet)
- **Production-Safeguards:** Git pre-commit hooks, Apache-Config Validation, Hourly Health-Check Timer (siehe [DEPLOYMENT.md](DEPLOYMENT.md))

### 💾 Datenschutz

- ✅ Self-Hosted — keine Cloud-Abhängigkeiten, keine Tracker, keine Analytics
- ✅ **Envelope-Encryption** für sensible User-Daten (Backups, IMAP-Credentials): pro-User Data-Encryption-Key (DEK), gewrapped mit aus Passwort abgeleitetem KEK (PBKDF2 600k iterations)
- ✅ User-spezifischer localStorage wird beim Logout vollständig gelöscht (kein Daten-Leak zwischen Usern auf gemeinsamen Browsern)
- ✅ Passwörter verschlüsselt mit AES-128-CBC + Fernet
- ✅ IMAP-Proxy läuft auf localhost (Port 8765)
- ✅ JWT-Tokens mit konfigurierbarer TTL, Refresh-Token-Flow

### 📋 System-Anforderungen

- **Browser:** Chrome, Firefox, Safari, Edge (ES6+)
- **Server:** Python 3.9+ (Production-Setup: 3.12 empfohlen)
- **Optional:** `ai-provider-service` (separates Repo) für Multi-Provider-Routing

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
- 📅 **Calendar Export (.ics)** - In the detail modal of any application with status `antwort`/`interview`/`zusage`: one click downloads an `.ics` file with the interview slot, Teams/Zoom link, passcode and attendees. Imports into Apple Calendar, Google Calendar, Outlook. The event is parsed from notes or the linked email body (date, link, passcode), no DB migration, no OAuth required
- 📋 **CV Comparison** - Compare your CV against job requirements — direct analysis via your configured AI provider (with fallback) or copy-paste to web platforms
- ✍️ **Cover-Letter Generator** - Generates German cover letters from CV + job posting. Per-paragraph confidence scoring (green = factual / yellow = mostly factual / orange = interpreted), PDF/DOCX export, detail analysis with skill matching, pre-fill from job suggestions. Does not invent skills — only uses what's in CV/job posting
- 🤖 **Multi-Provider AI** - Claude (Anthropic), local Ollama, ChatGPT/OpenAI, Mammouth, custom OpenAI-compatible endpoints. Per-user configuration with encrypted API keys. Optional: fallback provider and queue persistence for unavailable providers (e.g. local Ollama)
- 🎯 **Per-Task Model Overrides** - Different models per AI task (job-match, cover-letter, CV-summarize, email-analyse) freely configurable. Heuristic recommendation engine rates each model per task (✅/⚠️/❌). E.g. small local Ollama model for job-matching, Claude for cover-letter generation
- 🌐 **Multi-User Local-Ollama via Tailscale** - multiple users can plug their own Ollama instance without port conflicts. VPS + user Macs in a private Tailnet, ACL limits members to port 11434. See in-app manual section *"Eigenes Ollama anbinden"* + [deploy/tailscale-acl.hujson](deploy/tailscale-acl.hujson)
- 🔍 **Job-Discovery** - Automated job search from RSS feeds + Bundesagentur/Adzuna/Arbeitnow APIs with AI match-scoring against your CV (provider freely selectable). Includes source management, pagination, full-text search, filters (Remote/postal-code/employment-type), browser push notifications for top matches, and onboarding checklist
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

# ENV vars (required)
export JOB_CRON_TOKEN=<random-secret-32+chars>
export ANTHROPIC_API_KEY=<your-key>
export CLAUDE_DEFAULT_MODEL=claude-haiku-4-5-20251001

# Optional: use central ai-provider-service (multi-provider + fallback + queue)
# When set, all AI calls are delegated there.
export AI_PROVIDER_SERVICE_URL=http://127.0.0.1:8767
export AI_PROVIDER_SERVICE_TOKEN=<service-token>

# Cron setup (system cron or cron-job.org)
# 5 endpoints: /api/jobs/{crawl-source,prefilter,claude-match,notify,cleanup}
```

**Optional: ai-provider-service** — separate repo, runs as systemd unit on
port 8767 and wraps all providers behind a unified REST API. Benefits:
centralized API key management, automatic fallback, queue persistence for
local providers (e.g. Ollama on Mac via autossh reverse tunnel). Setup
instructions in the corresponding repo.

### 📚 Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Step-by-step guide
- **[Features](docs/FEATURES/)** - Detailed feature documentation
  - [CV Comparison & Processing](docs/FEATURES/CV.md)
  - [Email Integration](docs/FEATURES/EMAIL.md)
- **[Deployment](docs/DEPLOYMENT/)** - Installation & hosting
  - [Generic Server](docs/DEPLOYMENT/DEPLOYMENT_GENERIC.md)
  - [IONOS Shared Hosting](docs/DEPLOYMENT/DEPLOYMENT_IONOS.md)
  - [API key rotation](docs/DEPLOYMENT/KEY_ROTATION.md) - Rotate the Anthropic key on the VPS via `bewerbungen-rotate-anthropic-key`
- **[Setup Guides](docs/GUIDES/)** - Provider-specific configuration
  - [Gmail Setup](docs/GUIDES/SETUP_GMAIL.md)
  - [Outlook Setup](docs/GUIDES/SETUP_OUTLOOK.md)
  - [IMAP Setup](docs/GUIDES/SETUP_IMAP.md)

### 🔧 Technology

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (no frameworks), PWA with service worker
- **Backend:** Python 3.12 (Flask) + SQLite + JWT auth; modular `services/` layer for AI matching, email import, provider routing, and task-queue workers
- **AI-Routing:** either Anthropic Claude SDK directly (default), or delegation to external `ai-provider-service` (separate repo) for multi-provider, fallback and queue persistence. Both modes operable through the same user settings UI.
- **Libraries:** jsPDF, TweetNaCl.js (Encryption), Mammoth (DOCX), pdf.js, cryptography (Fernet)

### 💾 Privacy

- ✅ Self-hosted — no cloud dependencies, no tracking, no analytics
- ✅ Envelope encryption (per-user DEK + KEK from password) for sensitive data
- ✅ Passwords encrypted with bcrypt + Fernet
- ✅ IMAP proxy runs on localhost (Port 8765)
- ✅ JWT tokens with configurable TTL, refresh-token flow

### 📋 System Requirements

- **Browser:** Chrome, Firefox, Safari, Edge (ES6+)
- **Server:** Python 3.9+ (production: 3.12 recommended)
- **Optional:** `ai-provider-service` (separate repo) for multi-provider routing

### 📞 Support

For issues or feature requests: See [GETTING_STARTED.md](docs/GETTING_STARTED.md) for troubleshooting

---
## 🌐 More on wolfinisoftware.de
[Visit **wolfinisoftware.de**](https://www.wolfinisoftware.de/) for more news, projects, tools & resources.

## Mitwirken

Pull-Requests sind willkommen. Bitte einmal kurz [`CONTRIBUTING.md`](CONTRIBUTING.md)
lesen — wir nutzen das Developer Certificate of Origin (DCO), Commits müssen
also mit `git commit -s` signiert werden.

## Lizenz

Veröffentlicht unter der [GNU AGPL v3.0](LICENSE) — © 2026 Harald Weiss.

Die AGPL stellt sicher, dass auch netzbasierte Bereitstellungen den Quellcode
ihrer Modifikationen weitergeben müssen. Ideen und Konzepte sind durch keine
Lizenz schützbar.
