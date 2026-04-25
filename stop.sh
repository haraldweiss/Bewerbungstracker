#!/bin/bash

# Bewerbungs-Tracker Stop Script for macOS and Linux
# Cleanly stops all running services (Web Server, IMAP Proxy, Email Service, Data Service)

echo "🛑 Bewerbungs-Tracker - Stopping all services..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    if lsof -i :$1 > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port gracefully
kill_service() {
    local port=$1
    local name=$2
    local pids=""

    if check_port $port; then
        echo -e "${BLUE}Stopping $name (port $port)...${NC}"
        pids=$(lsof -ti:$port 2>/dev/null)

        if [ -n "$pids" ]; then
            # Try graceful shutdown first (SIGTERM)
            for pid in $pids; do
                kill -TERM $pid 2>/dev/null || true
            done

            # Wait a moment for graceful shutdown
            sleep 1

            # Force kill if still running (SIGKILL)
            for pid in $pids; do
                if kill -0 $pid 2>/dev/null; then
                    echo -e "${YELLOW}  Force killing PID $pid${NC}"
                    kill -9 $pid 2>/dev/null || true
                fi
            done

            echo -e "${GREEN}✅ $name stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  Port $port is in use but couldn't find PID${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  $name not running (port $port is free)${NC}"
    fi
}

echo ""

# Stop all services
kill_service 8080 "Web Server"
kill_service 8765 "IMAP Proxy"
kill_service 8766 "Email Service"

echo ""

# Verify all services are stopped
echo -e "${BLUE}Verifying all services are stopped...${NC}"
all_stopped=true

for port in 8080 8765 8766; do
    if check_port $port; then
        echo -e "${RED}❌ Port $port is still in use${NC}"
        all_stopped=false
    fi
done

echo ""

if [ "$all_stopped" = true ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ All services stopped successfully!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ Some services are still running${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Try manually:${NC}"
    echo "  ps aux | grep python3"
    echo "  kill <PID>"
fi

echo ""
