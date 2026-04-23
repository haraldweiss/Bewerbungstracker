# Deploy Bewerbungstracker to wolfinisoftware.de – Multi-User Edition

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy Bewerbungstracker as a multi-user web application on wolfinisoftware.de subdomain with user registration, JWT authentication, and per-user data isolation.

**Architecture:** 
- Backend: Flask + SQLAlchemy (already multi-user ready via user_id foreign keys)
- Frontend: Vanilla JS + localStorage for tokens, fetch API for application data
- Auth: JWT tokens (access + refresh), secure token storage
- Database: PostgreSQL (production) or SQLite (staging)
- Hosting: VPS with Nginx reverse proxy, Let's Encrypt SSL

**Tech Stack:** Flask 2.x, SQLAlchemy, JWT (PyJWT), PostgreSQL, Gunicorn, Nginx, Let's Encrypt

---

## File Structure

**New files to create:**
- `frontend/auth.js` — Authentication UI and token management
- `frontend/pages/login.html` — Login/registration form page
- `docs/DEPLOYMENT_PRODUCTION.md` — Production deployment guide
- `.env.example` — Environment variables template

**Files to modify:**
- `app.py` — Add CORS, environment config, serve login.html
- `index.html` — Add auth check on page load, API integration
- `config.py` — Production database support

**Infrastructure setup (manual):**
- VPS with Ubuntu 20.04+, Python 3.8+, PostgreSQL
- Nginx reverse proxy configuration
- systemd service file for Gunicorn
- SSL certificate (Let's Encrypt)

---

## Implementation Tasks

### Task 1: Add Environment Configuration

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create environment template**

```bash
cat > /Library/WebServer/Documents/Bewerbungstracker/.env.example << 'EOF'
# Flask Configuration
FLASK_ENV=production
FLASK_APP=app.py

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://user:password@localhost/bewerbungstracker

# JWT Configuration (Generate a random 32+ char string)
JWT_SECRET_KEY=change-this-to-random-32-char-string-in-production

# IMAP Proxy
IMAP_PROXY_URL=http://127.0.0.1:8765

# Claude API (optional)
CLAUDE_API_KEY=sk-ant-...

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
EOF
```

- [ ] **Step 2: Verify file was created**

```bash
cat /Library/WebServer/Documents/Bewerbungstracker/.env.example
```

Expected: File shows all environment variables with descriptions

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs: add environment variables template for production deployment"
```

---

### Task 2: Update Flask App Configuration

**Files:**
- Modify: `app.py`
- Modify: `config.py`

- [ ] **Step 1: Update config.py to support PostgreSQL**

In config.py, update DATABASE_URL handling:

```python
SQLALCHEMY_DATABASE_URI = os.getenv(
    'DATABASE_URL',
    'sqlite:///bewerbungstracker.db' if os.getenv('FLASK_ENV') != 'production' else None
)

if os.getenv('FLASK_ENV') == 'production' and not SQLALCHEMY_DATABASE_URI:
    raise ValueError('DATABASE_URL must be set in production')
```

- [ ] **Step 2: Verify config changes**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
python3 -c "from config import Config; print(f'DB: {Config.SQLALCHEMY_DATABASE_URI}')"
```

Expected: Shows sqlite in development, requires DATABASE_URL in production

- [ ] **Step 3: Update app.py to add CORS headers**

Add this import to app.py:

```python
from flask_cors import CORS
```

After `app = Flask(...)` line, add:

```python
CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(','),
        "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

- [ ] **Step 4: Update app.py to load .env file**

Add this at the top of app.py:

```python
from dotenv import load_dotenv
load_dotenv()
```

- [ ] **Step 5: Commit config changes**

```bash
git add app.py config.py
git commit -m "feat: add CORS support and .env configuration loading for production"
```

---

### Task 3: Create Frontend Authentication Module

**Files:**
- Create: `frontend/auth.js`

- [ ] **Step 1: Create auth.js with token management**

```bash
cat > /Library/WebServer/Documents/Bewerbungstracker/frontend/auth.js << 'EOF'
// Authentication module - Token management and API calls

const Auth = (() => {
    const TOKEN_KEY = 'auth_token';
    const REFRESH_TOKEN_KEY = 'refresh_token';
    const API_BASE = window.location.origin + '/api';

    return {
        // Get current token
        getToken() {
            return localStorage.getItem(TOKEN_KEY);
        },

        // Check if user is authenticated
        isAuthenticated() {
            return !!this.getToken();
        },

        // Redirect to login if not authenticated
        requireAuth() {
            if (!this.isAuthenticated()) {
                window.location.href = '/pages/login.html';
            }
        },

        // Register user
        async register(email, password) {
            const res = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            return data;
        },

        // Login user
        async login(email, password) {
            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            // Store tokens
            localStorage.setItem(TOKEN_KEY, data.access_token);
            localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
            return data;
        },

        // Logout user
        logout() {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(REFRESH_TOKEN_KEY);
            window.location.href = '/pages/login.html';
        },

        // Refresh access token
        async refreshToken() {
            const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
            if (!refreshToken) throw new Error('No refresh token');

            const res = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            localStorage.setItem(TOKEN_KEY, data.access_token);
            return data.access_token;
        },

        // Authenticated fetch wrapper
        async fetch(endpoint, options = {}) {
            const token = this.getToken();
            const headers = {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            };

            let res = await fetch(endpoint, { ...options, headers });

            // Refresh token if 401
            if (res.status === 401) {
                const newToken = await this.refreshToken();
                headers['Authorization'] = `Bearer ${newToken}`;
                res = await fetch(endpoint, { ...options, headers });
            }

            return res;
        }
    };
})();
EOF
```

- [ ] **Step 2: Verify file exists**

```bash
wc -l /Library/WebServer/Documents/Bewerbungstracker/frontend/auth.js
```

Expected: Shows ~100 lines

- [ ] **Step 3: Commit**

```bash
git add frontend/auth.js
git commit -m "feat: add frontend authentication module with token management"
```

---

### Task 4: Create Login/Registration Page

**Files:**
- Create: `frontend/pages/login.html`

- [ ] **Step 1: Create login.html**

```bash
cat > /Library/WebServer/Documents/Bewerbungstracker/frontend/pages/login.html << 'EOF'
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bewerbungs-Tracker Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
            padding: 2rem;
        }
        h1 { text-align: center; margin-bottom: 2rem; color: #333; }
        .form-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: #555;
            font-weight: 600;
        }
        input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }
        .btn {
            width: 100%;
            padding: 0.75rem;
            border: none;
            border-radius: 4px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
            transition: 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
            margin-bottom: 1rem;
        }
        .btn-primary:hover { background: #5568d3; }
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        .btn-secondary:hover { background: #e0e0e0; }
        .tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .tab-btn {
            flex: 1;
            padding: 0.75rem;
            background: none;
            border: 2px solid #ddd;
            cursor: pointer;
            border-radius: 4px;
            font-weight: 600;
            color: #999;
            transition: 0.3s;
        }
        .tab-btn.active {
            color: #667eea;
            border-color: #667eea;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .error {
            color: #ef4444;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        .success {
            color: #10b981;
            font-size: 0.875rem;
            text-align: center;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>📋 Bewerbungs-Tracker</h1>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('login')">Login</button>
            <button class="tab-btn" onclick="switchTab('register')">Registrieren</button>
        </div>

        <div id="login" class="tab-content active">
            <form onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="login-email" required>
                </div>
                <div class="form-group">
                    <label>Passwort</label>
                    <input type="password" id="login-password" required>
                </div>
                <div id="login-error" class="error"></div>
                <button class="btn btn-primary" type="submit">Login</button>
            </form>
        </div>

        <div id="register" class="tab-content">
            <form onsubmit="handleRegister(event)">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="register-email" required>
                </div>
                <div class="form-group">
                    <label>Passwort</label>
                    <input type="password" id="register-password" required minlength="8">
                </div>
                <div class="form-group">
                    <label>Passwort wiederholen</label>
                    <input type="password" id="register-password-confirm" required minlength="8">
                </div>
                <div id="register-error" class="error"></div>
                <div id="register-success" class="success"></div>
                <button class="btn btn-primary" type="submit">Registrieren</button>
            </form>
        </div>
    </div>

    <script src="../auth.js"></script>
    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
        }

        async function handleLogin(e) {
            e.preventDefault();
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const errorEl = document.getElementById('login-error');

            try {
                await Auth.login(email, password);
                window.location.href = '/';
            } catch (err) {
                errorEl.textContent = err.message;
            }
        }

        async function handleRegister(e) {
            e.preventDefault();
            const email = document.getElementById('register-email').value;
            const password = document.getElementById('register-password').value;
            const confirm = document.getElementById('register-password-confirm').value;
            const errorEl = document.getElementById('register-error');
            const successEl = document.getElementById('register-success');

            if (password !== confirm) {
                errorEl.textContent = 'Passwörter stimmen nicht überein';
                return;
            }

            try {
                await Auth.register(email, password);
                successEl.textContent = '✅ Registrierung erfolgreich! Sie können sich jetzt anmelden.';
                document.getElementById('register-email').value = '';
                document.getElementById('register-password').value = '';
                document.getElementById('register-password-confirm').value = '';
            } catch (err) {
                errorEl.textContent = err.message;
            }
        }
    </script>
</body>
</html>
EOF
```

- [ ] **Step 2: Verify file exists**

```bash
ls -lh /Library/WebServer/Documents/Bewerbungstracker/frontend/pages/login.html
```

Expected: File exists with size ~4-5KB

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/login.html
git commit -m "feat: add login/registration page with auth UI"
```

---

### Task 5: Integrate Authentication into Main App

**Files:**
- Modify: `index.html`
- Modify: `app.py`

- [ ] **Step 1: Add auth check to index.html**

At the very beginning of the `<script>` section in index.html (after `<script>` tag), add:

```javascript
// Authentication check
Auth = window.Auth; // Make Auth available globally
Auth.requireAuth(); // Redirect to login if not authenticated

// Get current user
async function getCurrentUser() {
    const res = await Auth.fetch('/api/auth/me');
    if (!res.ok) {
        Auth.logout();
        return null;
    }
    return await res.json();
}

let currentUser = null;
getCurrentUser().then(user => {
    currentUser = user;
    console.log('Logged in as:', user.email);
});
```

- [ ] **Step 2: Add logout button to HTML header**

In the `<header>` section of index.html, add logout button before the closing header tag:

```html
<button class="btn btn-secondary btn-sm" onclick="Auth.logout()" style="margin-left: auto;">🚪 Logout</button>
```

- [ ] **Step 3: Update app.py to serve login.html**

Modify app.py to add route for login page:

```python
@app.route('/pages/login.html')
def login_page():
    return send_file('frontend/pages/login.html')
```

- [ ] **Step 4: Add script tags to index.html head**

Add these before closing `</head>` tag in index.html:

```html
<script src="/frontend/auth.js"></script>
```

- [ ] **Step 5: Update all API calls to use Auth.fetch**

In index.html, replace all `fetch()` calls with `Auth.fetch()`. For example:

Before:
```javascript
await apiFetch(`/api/applications`, { method: 'POST', body: JSON.stringify(app) })
```

After:
```javascript
await Auth.fetch(`/api/applications`, { method: 'POST', body: JSON.stringify(app) })
```

Search and replace in index.html: `apiFetch(` → `Auth.fetch(`

- [ ] **Step 6: Commit changes**

```bash
git add index.html app.py frontend/pages/login.html frontend/auth.js
git commit -m "feat: integrate JWT authentication into frontend with login page"
```

---

### Task 6: Setup Production Dependencies

**Files:**
- Create: `requirements-prod.txt`

- [ ] **Step 1: Create production requirements file**

```bash
cat > /Library/WebServer/Documents/Bewerbungstracker/requirements-prod.txt << 'EOF'
# Production dependencies
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-CORS==4.0.0
python-dotenv==1.0.0
PyJWT==2.8.0
cryptography==41.0.3
psycopg2-binary==2.9.7
gunicorn==21.2.0
requests==2.31.0
EOF
```

- [ ] **Step 2: Verify file**

```bash
cat /Library/WebServer/Documents/Bewerbungstracker/requirements-prod.txt
```

- [ ] **Step 3: Commit**

```bash
git add requirements-prod.txt
git commit -m "deps: add production requirements with PostgreSQL and Gunicorn"
```

---

### Task 7: Create Production Deployment Guide

**Files:**
- Create: `docs/DEPLOYMENT_PRODUCTION.md`

- [ ] **Step 1: Create deployment guide**

```bash
cat > /Library/WebServer/Documents/Bewerbungstracker/docs/DEPLOYMENT_PRODUCTION.md << 'EOF'
# Production Deployment Guide

## Prerequisites

- Ubuntu 20.04+ VPS (or equivalent Linux)
- Python 3.8+
- PostgreSQL 12+
- Nginx
- SSH access to server

## 1. Server Setup

```bash
# SSH into server
ssh user@bewerbungen.wolfinisoftware.de

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx certbot python3-certbot-nginx git

# Create app user
sudo useradd -m -s /bin/bash bewerbungen
sudo -u bewerbungen mkdir -p /home/bewerbungen/app
```

## 2. Clone and Setup App

```bash
sudo -u bewerbungen git clone <repo-url> /home/bewerbungen/app/bewerbungstracker
cd /home/bewerbungen/app/bewerbungstracker

# Create Python venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-prod.txt
```

## 3. Database Setup

```bash
sudo -u postgres psql << EOF
CREATE DATABASE bewerbungstracker;
CREATE USER bewerbungen_user WITH PASSWORD 'your-secure-password';
ALTER ROLE bewerbungen_user SET client_encoding TO 'utf8';
ALTER ROLE bewerbungen_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE bewerbungen_user SET default_transaction_deferrable TO on;
ALTER ROLE bewerbungen_user SET default_transaction_read_committed TO on;
GRANT ALL PRIVILEGES ON DATABASE bewerbungstracker TO bewerbungen_user;
EOF
```

## 4. Environment Configuration

```bash
# Create .env file
sudo -u bewerbungen cp .env.example .env
sudo -u bewerbungen nano .env

# Set these values:
# DATABASE_URL=postgresql://bewerbungen_user:password@localhost/bewerbungstracker
# JWT_SECRET_KEY=<generate-random-32-char-string>
# FLASK_ENV=production
```

## 5. Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/bewerbungstracker.service

# Paste this content:
[Unit]
Description=Bewerbungstracker Flask App
After=network.target postgresql.service

[Service]
User=bewerbungen
WorkingDirectory=/home/bewerbungen/app/bewerbungstracker
Environment="PATH=/home/bewerbungen/app/bewerbungstracker/venv/bin"
EnvironmentFile=/home/bewerbungen/app/bewerbungstracker/.env
ExecStart=/home/bewerbungen/app/bewerbungstracker/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 app:create_app()
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable bewerbungstracker
sudo systemctl start bewerbungstracker
sudo systemctl status bewerbungstracker
```

## 6. Nginx Configuration

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/bewerbungstracker

# Paste this content:
server {
    listen 80;
    server_name bewerbungen.wolfinisoftware.de;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/bewerbungstracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 7. SSL Certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d bewerbungen.wolfinisoftware.de
# Auto-renew is configured automatically
```

## 8. DNS Configuration

Point your domain registrar DNS records to:
- A record: `bewerbungen.wolfinisoftware.de` → your VPS IP address

## Monitoring

```bash
# Check service status
sudo systemctl status bewerbungstracker

# View logs
sudo journalctl -u bewerbungstracker -f

# Database backups
sudo -u postgres pg_dump bewerbungstracker > backup-$(date +%Y%m%d).sql
```

## Troubleshooting

- Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
- Check app logs: `sudo journalctl -u bewerbungstracker -n 100`
- Test app locally: `curl http://127.0.0.1:5000/`

EOF
```

- [ ] **Step 2: Verify guide**

```bash
wc -l /Library/WebServer/Documents/Bewerbungstracker/docs/DEPLOYMENT_PRODUCTION.md
```

Expected: ~150 lines

- [ ] **Step 3: Commit**

```bash
git add docs/DEPLOYMENT_PRODUCTION.md
git commit -m "docs: add comprehensive production deployment guide"
```

---

### Task 8: Final Testing and Verification

- [ ] **Step 1: Test local development**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker
export FLASK_ENV=development
python3 app.py
```

Expected: App runs on http://localhost:8080, redirects to login

- [ ] **Step 2: Test registration flow**

- Open http://localhost:8080 → redirects to login
- Register new user (test@example.com / password123)
- Login with credentials
- Dashboard loads with user data

- [ ] **Step 3: Test API endpoints**

```bash
# Get auth token
curl -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"password123"}'

# List applications (with token)
curl -H 'Authorization: Bearer <token>' \
  http://localhost:8080/api/applications
```

Expected: Token returned, applications list works

- [ ] **Step 4: Verify all files are in git**

```bash
git status
```

Expected: No untracked files, all changes committed

- [ ] **Step 5: Final commit**

```bash
git log --oneline -8
```

Expected: Should show ~8 new commits for this deployment

---

## Execution

Plan is complete and saved to `docs/superpowers/plans/2026-04-23-deploy-wolfinisoftware-multiuser.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch fresh subagent per task, review between tasks
**2. Inline Execution** - Execute all tasks in this session with checkpoints

**Which approach would you prefer?**