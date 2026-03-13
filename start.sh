#!/bin/bash

# Bewerbungs-Tracker Start Script for macOS and Linux
# Starts Web Server, IMAP Proxy, and Email Service

set -e

echo "🚀 Bewerbungs-Tracker - Starting all services..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python installation
echo -e "${BLUE}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3 from https://www.python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python 3 found: $PYTHON_VERSION${NC}"
echo ""

# Check required Python modules
echo -e "${BLUE}Checking required Python modules...${NC}"
python3 << 'EOF'
import sys
required_modules = ['imaplib', 'smtplib', 'sqlite3', 'json', 'os']
missing = []

for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)

if missing:
    print(f"❌ Missing modules: {', '.join(missing)}")
    sys.exit(1)
else:
    print("✅ All required modules available")
EOF
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if a port is in use
check_port() {
    if lsof -i :$1 > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill existing processes on ports if needed
kill_existing_process() {
    local port=$1
    local name=$2
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use ($name). Killing existing process...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Check if ports are available
echo -e "${BLUE}Checking port availability...${NC}"
PORTS=(8080 8765 8766 8767)
NAMES=("Web Server" "IMAP Proxy" "Email Service" "Data Service")

for i in "${!PORTS[@]}"; do
    if check_port ${PORTS[$i]}; then
        echo -e "${YELLOW}⚠️  Port ${PORTS[$i]} (${NAMES[$i]}) is already in use${NC}"
    fi
done
echo ""

# Start Web Server
echo -e "${BLUE}Starting Web Server (port 8080)...${NC}"
python3 -m http.server 8080 --directory . > /tmp/webserver.log 2>&1 &
WEB_PID=$!
echo -e "${GREEN}✅ Web Server started (PID: $WEB_PID)${NC}"

# Start IMAP Proxy
echo -e "${BLUE}Starting IMAP Proxy (port 8765)...${NC}"
if [ -f "imap_proxy.py" ]; then
    python3 imap_proxy.py > /tmp/imap_proxy.log 2>&1 &
    IMAP_PID=$!
    echo -e "${GREEN}✅ IMAP Proxy started (PID: $IMAP_PID)${NC}"
else
    echo -e "${YELLOW}⚠️  imap_proxy.py not found, skipping IMAP Proxy${NC}"
fi

# Start Email Service
echo -e "${BLUE}Starting Email Service (port 8766)...${NC}"
if [ -f "email_service.py" ]; then
    python3 email_service.py > /tmp/email_service.log 2>&1 &
    EMAIL_PID=$!
    echo -e "${GREEN}✅ Email Service started (PID: $EMAIL_PID)${NC}"
else
    echo -e "${YELLOW}⚠️  email_service.py not found, skipping Email Service${NC}"
fi

# Start Data Service
echo -e "${BLUE}Starting Data Service (port 8767)...${NC}"
if [ -f "data_service.py" ]; then
    python3 data_service.py > /tmp/data_service.log 2>&1 &
    DATA_PID=$!
    echo -e "${GREEN}✅ Data Service started (PID: $DATA_PID)${NC}"
else
    echo -e "${YELLOW}⚠️  data_service.py not found, skipping Data Service${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 Service URLs:${NC}"
echo "  🌐 Web App:       ${BLUE}http://localhost:8080${NC}"
echo "  📧 IMAP Proxy:    ${BLUE}http://localhost:8765${NC}"
echo "  💌 Email Service:  ${BLUE}http://localhost:8766${NC}"
echo "  💾 Data Service:   ${BLUE}http://localhost:8767${NC}"
echo ""
echo -e "${YELLOW}📝 Log files:${NC}"
echo "  Web Server: /tmp/webserver.log"
echo "  IMAP Proxy: /tmp/imap_proxy.log"
echo "  Email Service: /tmp/email_service.log"
echo "  Data Service: /tmp/data_service.log"
echo ""
echo -e "${YELLOW}🛑 To stop all services, run:${NC}"
echo "  kill $WEB_PID $IMAP_PID $EMAIL_PID $DATA_PID"
echo ""
echo -e "${BLUE}💡 Tips:${NC}"
echo "  • Open http://localhost:8080 in your browser"
echo "  • Configure Email Service with your SMTP/IMAP credentials"
echo "  • Check logs if services don't start"
echo "  • Press Ctrl+C to stop the services"
echo ""

# Wait for interruption
wait
