# Production Deployment Guide for Bewerbungstracker

A comprehensive step-by-step guide for deploying the Bewerbungstracker Flask application to a production Linux VPS.

**Target Deployment Environment:**
- Domain: `bewerbungen.wolfinisoftware.de`
- Server: Ubuntu 20.04+ LTS VPS
- Application User: `bewerbungen`
- Application Port: 5000 (internal)
- Public Ports: 80 (HTTP), 443 (HTTPS)

---

## Prerequisites

Before starting the deployment, ensure you have:

1. **VPS/Server:**
   - Ubuntu 20.04 or later (or compatible Linux distribution)
   - Minimum 1GB RAM (2GB+ recommended)
   - Minimum 10GB free disk space
   - Root or sudo access

2. **Required Software (will be installed in this guide):**
   - Python 3.8+
   - PostgreSQL 12+
   - Nginx
   - Certbot (for Let's Encrypt SSL)

3. **Access Requirements:**
   - SSH access to your VPS
   - Domain DNS management access (A record)
   - Email address for Let's Encrypt certificate renewal

4. **Source Code:**
   - Git repository access: https://github.com/haraldweiss/Bewerbungstracker
   - Git credentials configured on the VPS

---

## Step 1: Server Setup

### Update System Packages

Connect to your VPS via SSH and update all system packages:

```bash
ssh root@your-vps-ip
sudo apt-get update
sudo apt-get upgrade -y
```

### Install Dependencies

Install the required system packages:

```bash
sudo apt-get install -y \
    python3.8 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    curl \
    wget \
    htop \
    ufw
```

Verify installations:

```bash
python3 --version
psql --version
nginx -v
certbot --version
```

**Expected Output:**
```
Python 3.8.x (or later)
psql (PostgreSQL) 12.x (or later)
nginx/1.x.x
certbot 2.x.x
```

### Create Application User

Create a non-root user for running the application:

```bash
sudo useradd -m -s /bin/bash bewerbungen
sudo usermod -aG www-data bewerbungen
```

Create the application directory:

```bash
sudo mkdir -p /opt/bewerbungstracker
sudo chown -R bewerbungen:bewerbungen /opt/bewerbungstracker
sudo chmod -R 755 /opt/bewerbungstracker
```

### Configure Firewall

Enable Ubuntu Firewall (UFW) and allow SSH, HTTP, and HTTPS:

```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

**Expected Output:**
```
Status: active

     To                         Action      From
     --                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

---

## Step 2: Clone and Setup Application

### Clone the Repository

Switch to the application user and clone the repository:

```bash
sudo -u bewerbungen bash
cd /opt/bewerbungstracker
git clone https://github.com/haraldweiss/Bewerbungstracker.git .
```

If using SSH keys (recommended for automated deployments):

```bash
cd /opt/bewerbungstracker
git clone git@github.com:haraldweiss/Bewerbungstracker.git .
```

### Create Python Virtual Environment

```bash
cd /opt/bewerbungstracker
python3 -m venv venv
source venv/bin/activate
```

### Install Python Dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements-prod.txt
```

**Expected Output:**
```
Successfully installed Flask-2.3.3 Flask-CORS-4.0.0 ... gunicorn-21.2.0
```

Verify the installation:

```bash
pip list | grep -E "Flask|SQLAlchemy|gunicorn|psycopg2"
```

---

## Step 3: PostgreSQL Database Setup

### Create Database and User

Exit the `bewerbungen` user shell and switch to root:

```bash
exit
sudo su - postgres
```

Create a PostgreSQL database and user:

```bash
psql
CREATE DATABASE bewerbungstracker_prod;
CREATE USER bewerbungen_db WITH PASSWORD 'your-strong-password-here';
ALTER ROLE bewerbungen_db SET client_encoding TO 'utf8';
ALTER ROLE bewerbungen_db SET default_transaction_isolation TO 'read committed';
ALTER ROLE bewerbungen_db SET default_transaction_deferrable TO on;
ALTER ROLE bewerbungen_db SET default_time_zone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE bewerbungstracker_prod TO bewerbungen_db;
\q
exit
```

### Test Database Connection

Test the connection from the application user:

```bash
sudo -u bewerbungen bash
cd /opt/bewerbungstracker
source venv/bin/activate
psql postgresql://bewerbungen_db:your-strong-password-here@localhost:5432/bewerbungstracker_prod -c "SELECT 1"
```

**Expected Output:**
```
 ?column?
----------
        1
(1 row)
```

---

## Step 4: Environment Configuration

### Create .env File

Create the production environment file:

```bash
sudo -u bewerbungen bash
cd /opt/bewerbungstracker
cp .env.example .env
nano .env  # or use your preferred editor
```

### Configure Environment Variables

Edit `/opt/bewerbungstracker/.env` and set the following values:

```bash
# Flask Configuration
FLASK_ENV=production
FLASK_APP=app.py

# Database Configuration - REPLACE WITH YOUR PASSWORD
DATABASE_URL=postgresql://bewerbungen_db:your-strong-password-here@localhost:5432/bewerbungstracker_prod

# JWT Secret Key - GENERATE A NEW ONE
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-generated-secret-key-here

# Encryption Key - GENERATE A NEW ONE
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
ENCRYPTION_KEY=your-generated-encryption-key-here

# Database Encryption Key - GENERATE A NEW ONE
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
DATABASE_ENCRYPTION_KEY=your-generated-db-encryption-key-here

# IMAP Proxy Configuration
IMAP_PROXY_URL=http://127.0.0.1:8765

# Claude API Configuration (if using Claude integration)
CLAUDE_API_KEY=your-claude-api-key-here

# Port Configuration (behind reverse proxy, can remain unchanged)
PORT=5000

# Authentication Configuration
# Set to 'true' to require authentication
AUTH_REQUIRED=true

# CORS Configuration - IMPORTANT: Set this for your domain
CORS_ORIGINS=https://bewerbungen.wolfinisoftware.de,https://www.bewerbungen.wolfinisoftware.de
```

### Generate Secure Secret Keys

Generate cryptographically secure keys for production:

```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('DATABASE_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

Copy each generated value into your `.env` file.

### Set Proper Permissions

```bash
chmod 600 /opt/bewerbungstracker/.env
```

---

## Step 5: Database Initialization

### Run Database Migrations

Initialize the database with tables:

```bash
cd /opt/bewerbungstracker
source venv/bin/activate
python3 -c "from app import create_app, db; app = create_app(); 
with app.app_context(): 
    db.create_all(); 
    print('Database initialized successfully')"
```

Or, if using Alembic for migrations:

```bash
cd /opt/bewerbungstracker
source venv/bin/activate
alembic upgrade head
```

**Expected Output:**
```
Database initialized successfully
```

---

## Step 6: Systemd Service Setup

### Create Systemd Service File

Create a systemd service file for managing the application with Gunicorn:

```bash
sudo nano /etc/systemd/system/bewerbungstracker.service
```

Add the following content:

```ini
[Unit]
Description=Bewerbungstracker Flask Application
After=network.target postgresql.service

[Service]
Type=notify
User=bewerbungen
Group=www-data
WorkingDirectory=/opt/bewerbungstracker
Environment="PATH=/opt/bewerbungstracker/venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/bewerbungstracker/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind 127.0.0.1:5000 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    "app:create_app()"
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Configuration Explanation:**
- `workers=4`: Number of Gunicorn worker processes (adjust based on CPU cores)
- `bind=127.0.0.1:5000`: Listen only on localhost (Nginx handles external traffic)
- `timeout=60`: Worker timeout in seconds
- `StandardOutput=journal`: Log to systemd journal for easy viewing

### Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable bewerbungstracker.service
sudo systemctl start bewerbungstracker.service
```

### Check Service Status

```bash
sudo systemctl status bewerbungstracker.service
sudo journalctl -u bewerbungstracker.service -n 50 -f
```

**Expected Output:**
```
● bewerbungstracker.service - Bewerbungstracker Flask Application
     Loaded: loaded (/etc/systemd/system/bewerbungstracker.service; enabled; vendor preset: enabled)
     Active: active (running) since ...
```

---

## Step 7: Nginx Reverse Proxy Configuration

### Create Nginx Configuration

Create an Nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/bewerbungstracker
```

Add the following content:

```nginx
# Redirect HTTP to HTTPS (added after SSL setup)
server {
    listen 80;
    server_name bewerbungen.wolfinisoftware.de www.bewerbungen.wolfinisoftware.de;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server Block
server {
    listen 443 ssl http2;
    server_name bewerbungen.wolfinisoftware.de www.bewerbungen.wolfinisoftware.de;

    # SSL Certificates (will be created by Certbot)
    ssl_certificate /etc/letsencrypt/live/bewerbungen.wolfinisoftware.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bewerbungen.wolfinisoftware.de/privkey.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/bewerbungstracker_access.log;
    error_log /var/log/nginx/bewerbungstracker_error.log;

    # Client upload size limit
    client_max_body_size 10M;

    # Root location
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }

    # Static files (if served by Nginx instead of Flask)
    location /static/ {
        alias /opt/bewerbungstracker/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
```

### Enable the Configuration

```bash
sudo ln -s /etc/nginx/sites-available/bewerbungstracker /etc/nginx/sites-enabled/
sudo nginx -t
```

**Expected Output:**
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Start Nginx

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

---

## Step 8: SSL Certificate Setup (Let's Encrypt)

### Obtain SSL Certificate with Certbot

Before running Certbot, ensure your domain's A record points to your VPS IP address:

```bash
sudo certbot certonly --nginx \
    -d bewerbungen.wolfinisoftware.de \
    -d www.bewerbungen.wolfinisoftware.de \
    --email your-email@example.com \
    --agree-tos \
    --non-interactive
```

**Expected Output:**
```
Congratulations! Your certificate has been issued and saved at:
  /etc/letsencrypt/live/bewerbungen.wolfinisoftware.de/fullchain.pem
```

### Test SSL Configuration

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Verify Certificate

```bash
openssl s_client -connect bewerbungen.wolfinisoftware.de:443 -showcerts
```

### Automatic Certificate Renewal

Certbot automatically creates a renewal timer. Check the status:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## Step 9: DNS Configuration

### Update Domain A Record

In your domain registrar's DNS management panel, create or update the A record:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | bewerbungen.wolfinisoftware.de | `your-vps-ip-address` | 3600 |
| A | www.bewerbungen.wolfinisoftware.de | `your-vps-ip-address` | 3600 |

Verify DNS propagation:

```bash
nslookup bewerbungen.wolfinisoftware.de
dig bewerbungen.wolfinisoftware.de +short
```

**Expected Output:**
```
bewerbungen.wolfinisoftware.de. 300 IN A 123.45.67.89
```

---

## Step 10: Verification and Testing

### Test Application Access

Open your browser and navigate to:

```
https://bewerbungen.wolfinisoftware.de
```

You should see the Bewerbungstracker application loading. If you see an SSL warning, the certificate may not have fully propagated (wait a few minutes).

### Test API Endpoint

```bash
curl -i https://bewerbungen.wolfinisoftware.de/api/health
curl -i https://bewerbungen.wolfinisoftware.de/api/status
```

### Check Service Logs

```bash
sudo journalctl -u bewerbungstracker.service -n 20 -f
sudo tail -f /var/log/nginx/bewerbungstracker_error.log
sudo tail -f /var/log/nginx/bewerbungstracker_access.log
```

### Verify Database Connection

```bash
sudo -u bewerbungen bash
cd /opt/bewerbungstracker
source venv/bin/activate
python3 -c "from app import create_app, db; 
app = create_app(); 
with app.app_context(): 
    result = db.session.execute('SELECT 1').fetchone(); 
    print('Database connection successful:', result)"
```

---

## Monitoring & Maintenance

### Regular Health Checks

Create a health check script at `/opt/bewerbungstracker/scripts/health_check.sh`:

```bash
#!/bin/bash
# Health check for production monitoring

DOMAIN="bewerbungen.wolfinisoftware.de"
HEALTH_ENDPOINT="https://${DOMAIN}/api/health"

# Check HTTP status
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_ENDPOINT}")

if [ "$HTTP_CODE" = "200" ]; then
    echo "[OK] Application is healthy (HTTP ${HTTP_CODE})"
    exit 0
else
    echo "[ERROR] Application health check failed (HTTP ${HTTP_CODE})"
    exit 1
fi
```

Make it executable and add to crontab:

```bash
chmod +x /opt/bewerbungstracker/scripts/health_check.sh
sudo crontab -e
```

Add the following line to run health checks every 5 minutes:

```
*/5 * * * * /opt/bewerbungstracker/scripts/health_check.sh >> /var/log/bewerbungstracker_health.log 2>&1
```

### Service Management Commands

View service status:

```bash
sudo systemctl status bewerbungstracker.service
```

View recent logs:

```bash
sudo journalctl -u bewerbungstracker.service -n 100
```

Follow live logs:

```bash
sudo journalctl -u bewerbungstracker.service -f
```

Restart the service:

```bash
sudo systemctl restart bewerbungstracker.service
```

### Monitoring Nginx

Check Nginx status:

```bash
sudo systemctl status nginx
```

View access logs:

```bash
sudo tail -f /var/log/nginx/bewerbungstracker_access.log
```

View error logs:

```bash
sudo tail -f /var/log/nginx/bewerbungstracker_error.log
```

### System Resource Monitoring

Monitor system resources:

```bash
# Memory and CPU usage
free -h
top -b -n 1 | head -20

# Disk usage
df -h
du -sh /opt/bewerbungstracker

# Network connections
netstat -tulpn | grep LISTEN
```

### Database Backups

#### Create a Backup Script

Create `/opt/bewerbungstracker/scripts/backup_database.sh`:

```bash
#!/bin/bash
# PostgreSQL backup script

BACKUP_DIR="/opt/bewerbungstracker/backups"
BACKUP_FILE="$BACKUP_DIR/bewerbungstracker_$(date +%Y%m%d_%H%M%S).sql.gz"

mkdir -p "$BACKUP_DIR"

# Backup the database
sudo -u postgres pg_dump bewerbungstracker_prod | gzip > "$BACKUP_FILE"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

Make it executable and add to crontab:

```bash
chmod +x /opt/bewerbungstracker/scripts/backup_database.sh
sudo crontab -e
```

Add the following to run backups daily at 2 AM:

```
0 2 * * * /opt/bewerbungstracker/scripts/backup_database.sh >> /var/log/bewerbungstracker_backup.log 2>&1
```

#### Restore a Backup

```bash
# List available backups
ls -lh /opt/bewerbungstracker/backups/

# Restore a specific backup
zcat /opt/bewerbungstracker/backups/bewerbungstracker_20240423_020000.sql.gz | \
    sudo -u postgres psql bewerbungstracker_prod
```

---

## Troubleshooting

### Application Won't Start

Check systemd journal for errors:

```bash
sudo journalctl -u bewerbungstracker.service -n 50
```

Common issues:

1. **Database connection failed:**
   - Verify DATABASE_URL in `.env`
   - Check PostgreSQL is running: `sudo systemctl status postgresql`
   - Test connection: `psql $DATABASE_URL -c "SELECT 1"`

2. **Module import errors:**
   - Ensure all dependencies are installed: `pip install -r requirements-prod.txt`
   - Check Python version: `python3 --version` (should be 3.8+)

3. **Permission denied:**
   - Verify file ownership: `ls -la /opt/bewerbungstracker/`
   - Fix if needed: `sudo chown -R bewerbungen:bewerbungen /opt/bewerbungstracker`

### Nginx Returns 502 Bad Gateway

The Flask application is not responding to requests on 127.0.0.1:5000. Check:

```bash
# Is the service running?
sudo systemctl status bewerbungstracker.service

# Is Gunicorn listening on port 5000?
sudo netstat -tulpn | grep 5000

# Check Nginx error log
sudo tail -f /var/log/nginx/bewerbungstracker_error.log
```

### SSL Certificate Issues

Check certificate status:

```bash
sudo certbot certificates
sudo openssl x509 -in /etc/letsencrypt/live/bewerbungen.wolfinisoftware.de/fullchain.pem -text -noout | grep -A2 "Validity"
```

Manually renew certificate:

```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

### High Memory or CPU Usage

Check which process is consuming resources:

```bash
ps aux --sort=-%mem | head -10
ps aux --sort=-%cpu | head -10
```

If Gunicorn is using too much memory, adjust worker count in systemd service:

```bash
# Edit the service file
sudo nano /etc/systemd/system/bewerbungstracker.service

# Reduce --workers parameter, then reload
sudo systemctl daemon-reload
sudo systemctl restart bewerbungstracker.service
```

### Database Connection Pool Exhausted

If you see connection pool errors, adjust the connection pool settings in your application code or increase PostgreSQL max_connections:

```bash
sudo -u postgres psql -c "ALTER SYSTEM SET max_connections = 100;"
sudo systemctl restart postgresql
```

### Checking IMAP Proxy Connectivity

If email functionality is failing, verify IMAP proxy is running:

```bash
curl -i http://127.0.0.1:8765/health
```

If not running, start it separately or verify it's configured in your systemd services.

---

## Security Best Practices

1. **Keep packages updated:**
   ```bash
   sudo apt-get update
   sudo apt-get upgrade
   ```

2. **Use SSH key authentication:**
   - Disable password authentication in `/etc/ssh/sshd_config`
   - Set `PasswordAuthentication no`

3. **Secure environment variables:**
   - Never commit `.env` to Git
   - Restrict `.env` file permissions: `chmod 600 .env`
   - Use a secrets manager for sensitive data (e.g., Vault, AWS Secrets Manager)

4. **Enable automatic security updates:**
   ```bash
   sudo apt-get install unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```

5. **Monitor logs for suspicious activity:**
   ```bash
   sudo tail -f /var/log/auth.log
   sudo tail -f /var/log/nginx/bewerbungstracker_error.log
   ```

6. **Regular backups:**
   - Schedule automated database backups
   - Test restore procedures regularly
   - Store backups off-site or in cloud storage

---

## Performance Tuning

### Gunicorn Worker Configuration

Adjust worker count in `/etc/systemd/system/bewerbungstracker.service`:

**CPU-bound application:**
```
--workers $(python3 -c "import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)")
```

**I/O-bound application:**
```
--workers $(python3 -c "import multiprocessing; print(multiprocessing.cpu_count() * 4)")
```

### PostgreSQL Connection Pooling

For production with many concurrent connections, consider using PgBouncer:

```bash
sudo apt-get install pgbouncer
# Configure /etc/pgbouncer/pgbouncer.ini
# Set pool_mode = transaction for connection pooling
```

### Nginx Caching

Add to Nginx configuration for static assets:

```nginx
location /static/ {
    alias /opt/bewerbungstracker/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

---

## Rollback Procedure

If a deployment breaks the application, follow these steps:

1. **Identify the problematic commit:**
   ```bash
   cd /opt/bewerbungstracker
   git log --oneline -n 10
   ```

2. **Revert to previous version:**
   ```bash
   git checkout <previous-commit-hash>
   ```

3. **Restart the application:**
   ```bash
   sudo systemctl restart bewerbungstracker.service
   ```

4. **Verify application is working:**
   ```bash
   curl -i https://bewerbungen.wolfinisoftware.de/
   ```

---

## Additional Resources

- **Flask Documentation:** https://flask.palletsprojects.com/
- **Gunicorn Documentation:** https://gunicorn.org/
- **Nginx Documentation:** https://nginx.org/en/docs/
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **Let's Encrypt/Certbot:** https://certbot.eff.org/
- **Ubuntu Server Guide:** https://ubuntu.com/server/docs

---

## Support and Issues

For issues or questions:

1. Check logs: `sudo journalctl -u bewerbungstracker.service -f`
2. Review this guide's Troubleshooting section
3. Open an issue on GitHub: https://github.com/haraldweiss/Bewerbungstracker/issues

---

**Last Updated:** April 2026  
**Maintainer:** Harald Weiss  
**Version:** 1.0
