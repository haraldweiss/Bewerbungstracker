# 🚀 Bewerbungs-Tracker - Startup Guide

Quick start scripts to launch all services (Web Server, IMAP Proxy, Email Service) on macOS, Linux, and Windows.

## Prerequisites

### All Platforms
- **Python 3.7+** - [Download here](https://www.python.org)
- **Required modules** (usually included with Python):
  - `imaplib` - IMAP email protocol
  - `smtplib` - SMTP email protocol
  - `sqlite3` - SQLite database
  - `json` - JSON handling
  - `os` - Operating system utilities

### Verify Python Installation

```bash
python3 --version
```

You should see: `Python 3.x.x`

---

## 🍎 macOS & 🐧 Linux

### Quick Start

```bash
chmod +x start.sh
./start.sh
```

### What It Does

The `start.sh` script:
1. ✅ Checks Python 3 installation
2. ✅ Verifies all required modules
3. ✅ Checks port availability (8080, 8765, 8766)
4. ✅ Starts Web Server (port 8080)
5. ✅ Starts IMAP Proxy (port 8765)
6. ✅ Starts Email Service (port 8766)
7. ✅ Displays service URLs and log locations

### Manual Start (Alternative)

Open three terminal windows:

**Window 1 - Web Server:**
```bash
python3 -m http.server 8080 --directory .
```

**Window 2 - IMAP Proxy:**
```bash
python3 imap_proxy.py
```

**Window 3 - Email Service:**
```bash
python3 email_service.py
```

### Stop Services

Press `Ctrl+C` in each terminal window, or run:
```bash
ps aux | grep python3
kill -9 <PID>
```

### Troubleshooting

**"Permission denied" error:**
```bash
chmod +x start.sh
```

**"Python 3 not found":**
- Install Python: `brew install python3` (macOS with Homebrew)
- Or download from https://www.python.org

**"Port already in use":**
```bash
# Find and kill process on port 8080
lsof -ti:8080 | xargs kill -9

# Check all ports
netstat -an | grep 8080
```

**Check service logs:**
```bash
tail -f /tmp/webserver.log
tail -f /tmp/imap_proxy.log
tail -f /tmp/email_service.log
```

---

## 🪟 Windows (CMD)

### Quick Start

1. **Open Command Prompt** as Administrator
2. **Navigate to project folder:**
   ```cmd
   cd C:\path\to\Bewerbungstracker
   ```
3. **Run the startup script:**
   ```cmd
   start.bat
   ```

### What It Does

The `start.bat` script:
1. ✅ Checks Python installation
2. ✅ Verifies all required modules
3. ✅ Checks port availability (8080, 8765, 8766)
4. ✅ Starts all three services in separate windows
5. ✅ Displays service URLs

### Manual Start (Alternative)

Open three Command Prompt windows:

**Window 1 - Web Server:**
```cmd
python -m http.server 8080 --directory .
```

**Window 2 - IMAP Proxy:**
```cmd
python imap_proxy.py
```

**Window 3 - Email Service:**
```cmd
python email_service.py
```

### Stop Services

- Press `Ctrl+C` in each Command Prompt window
- Or close the window directly

### Troubleshooting

**"Python is not recognized":**
1. Install Python from https://www.python.org
2. **Important:** Check "Add Python to PATH" during installation
3. Restart Command Prompt

**"Port is already in use":**
```cmd
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

**Check running processes:**
```cmd
netstat -ano | findstr :8080
netstat -ano | findstr :8765
netstat -ano | findstr :8766
```

---

## 🪟 Windows (PowerShell)

### Quick Start

1. **Open PowerShell** (press `Win+X`, select Windows PowerShell)
2. **Navigate to project folder:**
   ```powershell
   cd C:\path\to\Bewerbungstracker
   ```
3. **Allow script execution** (first time only):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. **Run the startup script:**
   ```powershell
   .\start.ps1
   ```

### What It Does

The `start.ps1` script:
1. ✅ Checks Python installation
2. ✅ Verifies all required modules
3. ✅ Checks port availability
4. ✅ Starts all services with colored status output
5. ✅ Shows service URLs

### Troubleshooting

**"cannot be loaded because running scripts is disabled":**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**"Python not found":**
- Install Python and check "Add Python to PATH"
- Restart PowerShell

---

## 📍 Service URLs

Once all services are running:

| Service | URL | Purpose |
|---------|-----|---------|
| **Web App** | http://localhost:8080 | Main application interface |
| **IMAP Proxy** | http://localhost:8765 | Email fetch (backend) |
| **Email Service** | http://localhost:8766 | Email sending & monitoring |

---

## ✅ Verify Services Are Running

### macOS/Linux

```bash
curl -s http://localhost:8080 | head -20
curl -s -X POST http://localhost:8765/api/status -H "Content-Type: application/json" -d '{}'
curl -s -X POST http://localhost:8766/api/status -H "Content-Type: application/json" -d '{}'
```

### Windows (PowerShell)

```powershell
Invoke-WebRequest http://localhost:8080
Invoke-WebRequest -Method POST http://localhost:8765/api/status -ContentType "application/json" -Body '{}'
Invoke-WebRequest -Method POST http://localhost:8766/api/status -ContentType "application/json" -Body '{}'
```

---

## 🔧 Configuration

After starting the services:

1. **Open** http://localhost:8080 in your browser
2. **Go to Settings** → **Notifications**
3. **Configure SMTP** (for sending emails):
   - Server: `smtp.gmail.com`
   - Port: `587`
   - Email: Your Gmail address
   - Password: Gmail App Password (see README.md)
4. **Configure IMAP** (for monitoring responses):
   - Server: `imap.gmail.com`
   - Port: `993`
   - Email: Your Gmail address
   - Password: Same App Password
5. **Click "Save"** to apply settings

---

## 📊 Log Files

### macOS/Linux

- Web Server: `/tmp/webserver.log`
- IMAP Proxy: `/tmp/imap_proxy.log`
- Email Service: `/tmp/email_service.log`

View logs in real-time:
```bash
tail -f /tmp/email_service.log
```

### Windows

Logs are displayed in each service window. Close the window to stop that service.

---

## 🆘 Need Help?

### Check Service Status

```bash
# macOS/Linux
curl -s -X POST http://localhost:8766/api/status -H "Content-Type: application/json" -d '{}' | jq .
```

### Kill All Services (macOS/Linux)

```bash
pkill -f "python3.*http.server"
pkill -f "python3.*imap_proxy"
pkill -f "python3.*email_service"
```

### Kill All Services (Windows)

```cmd
taskkill /F /IM python.exe
```

---

## 📝 Notes

- **Passwords** are not stored in logs or cached
- **Email database** is created at runtime: `email_config.db`
- **Application cache** is stored in: `applications_cache.json`
- All services are **localhost-only** for security
- Services run in **foreground** (can be killed with Ctrl+C)

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| Port already in use | Kill the process using that port |
| Python not found | Install Python and add to PATH |
| Module not found | Python modules are built-in |
| Services won't start | Check Python version (3.7+) |
| Can't access Web UI | Check firewall, verify port 8080 |

---

**Version**: 1.0
**Last Updated**: March 2026
**Platform Support**: macOS, Linux, Windows (CMD & PowerShell)
