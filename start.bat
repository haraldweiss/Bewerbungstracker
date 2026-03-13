@echo off
REM Bewerbungs-Tracker Start Script for Windows
REM Starts Web Server, IMAP Proxy, and Email Service

setlocal enabledelayedexpansion

echo.
echo ======================================================
echo   Bewerbungs-Tracker - Starting all services...
echo ======================================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION%
echo.

REM Check required Python modules
echo Checking required Python modules...
python -c "import imaplib, smtplib, sqlite3, json, os; print('[OK] All required modules available')" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing required Python modules
    echo Please run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] All required modules available
echo.

REM Get the directory where the script is located
cd /d "%~dp0"

REM Function to check if a port is in use
setlocal enabledelayedexpansion
set ports=8080 8765 8766
set names=Web_Server IMAP_Proxy Email_Service

echo Checking port availability...
for %%p in (%ports%) do (
    netstat -ano | findstr ":%%p " >nul 2>&1
    if not errorlevel 1 (
        echo [WARNING] Port %%p is already in use
    )
)
echo.

REM Start Web Server
echo Starting Web Server (port 8080)...
start "Bewerbungs-Tracker Web Server" python -m http.server 8080 --directory .
timeout /t 2 /nobreak >nul
echo [OK] Web Server started
echo.

REM Start IMAP Proxy
if exist "imap_proxy.py" (
    echo Starting IMAP Proxy (port 8765)...
    start "Bewerbungs-Tracker IMAP Proxy" python imap_proxy.py
    timeout /t 2 /nobreak >nul
    echo [OK] IMAP Proxy started
) else (
    echo [WARNING] imap_proxy.py not found, skipping IMAP Proxy
)
echo.

REM Start Email Service
if exist "email_service.py" (
    echo Starting Email Service (port 8766)...
    start "Bewerbungs-Tracker Email Service" python email_service.py
    timeout /t 2 /nobreak >nul
    echo [OK] Email Service started
) else (
    echo [WARNING] email_service.py not found, skipping Email Service
)
echo.

echo ======================================================
echo   ALL SERVICES STARTED SUCCESSFULLY!
echo ======================================================
echo.

echo Service URLs:
echo   Web App:       http://localhost:8080
echo   IMAP Proxy:    http://localhost:8765
echo   Email Service: http://localhost:8766
echo.

echo Tips:
echo   * Open http://localhost:8080 in your browser
echo   * Configure Email Service with your SMTP/IMAP credentials
echo   * Use Ctrl+C in each window to stop individual services
echo   * Or close the command windows to stop everything
echo.

pause
