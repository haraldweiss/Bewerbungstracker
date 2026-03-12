# 📋 Bewerbungs-Tracker

A powerful, privacy-focused application for managing job applications and tracking your recruitment journey. Built with vanilla JavaScript, Python, and jsPDF for a seamless experience.

## ✨ Features

### 📊 Dashboard & Analytics
- **Visual Status Distribution** - Track applications by status (Applied, Response, Interview, Offer, Rejection, Ghosting)
- **Key Metrics** - Total applications, open positions, interviews, offers, rejections
- **Response Rate** - See what percentage of applications have received responses
- **Activity Timeline** - Monitor recent application changes

### 📧 Email Integration
- **Gmail/Outlook/IMAP Support** - Connect to multiple email providers via secure IMAP proxy
- **Smart Email Detection** - Automatically identifies recruitment-related emails with keyword matching
- **False Positive Reduction** - Advanced filtering to minimize incorrect classifications
- **Batch Import** - Import multiple emails at once
- **Date Filtering** - Set a start date to only import recent emails

### 💾 Data Management
- **JSON Backup/Restore** - Full backup of all applications and settings
- **PDF Export** - Generate professional PDF reports with clickable job links
- **No Cloud Storage** - All data stored locally in browser (localStorage)
- **Settings Sync** - Backup and restore all configurations including keywords, email filters, and provider settings

### 🎯 Application Tracking
- **Rich Application Data** - Store company, position, status, date, salary, location, contact email, job link, and notes
- **Quick Status Updates** - Change application status directly from the list
- **Search & Filter** - Find applications by company, position, or source
- **Ghosting Detection** - Automatically mark applications as ghosting after X days without response
- **Multiple Sources** - Track applications from Gmail, LinkedIn, Indeed, XING, websites, and manual entries

### 🌙 UI/UX
- **Dark/Light Mode** - Toggle between dark and light themes
- **Responsive Design** - Works seamlessly on desktop and mobile
- **Keyboard Shortcuts** - Efficient navigation with keyboard support
- **Toast Notifications** - Real-time feedback for all actions

## 🚀 Quick Start

### Prerequisites
- Python 3.7+ (for IMAP proxy)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

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

### Using Launch Configuration

If you have Claude Code installed:
```bash
# Configuration is in .claude/launch.json
preview_start "Web Server"
preview_start "IMAP Proxy"
```

## 📖 Usage

### Adding Applications Manually
1. Click **"+ Bewerbung"** button
2. Fill in company, position, date, and other details
3. Paste the job link
4. Click **"💾 Speichern"** to save

### Connecting Email

#### Gmail/Yahoo/Outlook
1. Go to **Settings → Mail Connector**
2. Select your provider from the dropdown
3. Enter your email and **app password** (not your regular password!)
4. Click **"Verbinden"**

#### Other IMAP Providers
1. Enter IMAP host, port, and protocol manually
2. Use your email credentials (app password recommended)
3. The proxy securely connects to your email provider

### Importing Emails
1. Go to **Mail Connector**
2. Choose import method:
   - **Script Emails**: Via Google Apps Script
   - **EML Files**: Import from downloaded .eml files
   - **IMAP/POP3**: Live connection to email server
3. Set optional **start date** to avoid importing old emails
4. Preview and selectively import emails

### Exporting Data
- **JSON Backup**: Settings → "📥 JSON Backup" (includes all data and settings)
- **PDF Report**: Settings → "📄 PDF Export" (clickable links to job postings)
- **JSON Import**: Settings → "📤 JSON Import" (restore from backup)

## 🔒 Security & Privacy

### Local-First Architecture
- **No Cloud Storage** - All data remains in your browser
- **No Server Login** - No authentication, no user accounts
- **No Tracking** - No analytics, no data collection

### IMAP Proxy Security
- **Localhost-Only** - Proxy binds to 127.0.0.1 (no network access)
- **Credential Protection** - Passwords never logged, cached, or stored
- **Read-Only Access** - IMAP in readonly mode, POP3 without DELETE
- **SSL/TLS** - Encrypted connections with certificate validation
- **IP Validation** - Extra security check on every request

### Data Protection
- Sensitive data excluded from localStorage
- Backups don't include passwords
- App passwords recommended over regular passwords

## ⚙️ Configuration

### Email Keywords
Edit keywords used for automatic email detection in **Settings**. Default includes:
- Bewerbung, Application, Stelle, Interview, Absage, Zusage, Job, Recruiting, Kandidat

### Ghosting Threshold
Set days without response before marking as ghosting (default: 30 days)

### Email Import Date Filter
Set a start date to only import emails from specific period (optional)

## 📁 Project Structure

```
Bewerbungstracker/
├── index.html              # Main application (HTML + CSS + JavaScript)
├── imap_proxy.py          # Python IMAP/POP3 proxy (port 8765)
├── config.json            # Proxy configuration
├── ANLEITUNG_IMAP.md      # IMAP documentation (DE/EN)
├── README.md              # This file
├── .gitignore             # Git ignore rules
└── .claude/
    └── launch.json        # Dev server configuration
```

## 🛠️ Technologies

- **Frontend**: HTML5, CSS3, JavaScript (Vanilla - no frameworks)
- **Backend**: Python 3 (IMAP/POP3 Proxy)
- **PDF Generation**: jsPDF + jsPDF AutoTable
- **Storage**: Browser localStorage (no backend database)
- **Icons**: Unicode Emojis

## 📝 API Reference

### IMAP Proxy Endpoints

**POST /fetch**
- Fetch emails from IMAP/POP3 server
- Parameters: `host`, `user`, `folder`, `limit`, `offset`, `search_keywords`
- Returns: Email list with headers

**POST /test_connection**
- Test IMAP/POP3 connection
- Parameters: `host`, `port`, `protocol`, `user`, `password`
- Returns: Connection status

See `ANLEITUNG_IMAP.md` for detailed API documentation.

## 📊 Data Format

### Application Object
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

### Status Values
- `beworben` - Applied
- `antwort` - Response received
- `interview` - Interview scheduled
- `zusage` - Job offer
- `absage` - Rejection
- `ghosting` - No response (auto-marked)

### Source Values
- `gmail` - Gmail
- `imap` - IMAP/POP3
- `manuell` - Manual entry
- `linkedin` - LinkedIn
- `indeed` - Indeed
- `xing` - XING
- `website` - Company website
- `empfehlung` - Referral

## 🐛 Troubleshooting

### IMAP Proxy Connection Issues
1. Check IMAP host and port are correct
2. Use **app password** (not regular password) for Gmail/Yahoo
3. Enable "Less secure apps" if using Gmail with regular password
4. Verify proxy is running: `python3 imap_proxy.py`

### Email Import Not Working
1. Check email account credentials
2. Ensure IMAP is enabled in email settings
3. Try importing a specific date range
4. Check browser console for error messages

### PDF Not Exporting
1. Ensure you have applications to export
2. Check browser console for JavaScript errors
3. Try browser's developer tools if export fails silently

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests with improvements or bug fixes.

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Made with ❤️ for managing your job search efficiently and privately**
