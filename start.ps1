# Bewerbungs-Tracker Start Script for Windows PowerShell
# Starts Web Server, IMAP Proxy, and Email Service

# Requires elevated privileges for some operations (optional)
# If needed, uncomment the line below:
# #Requires -RunAsAdministrator

# Set error action preference
$ErrorActionPreference = "Continue"

# Colors
$Colors = @{
    Red    = [System.ConsoleColor]::Red
    Green  = [System.ConsoleColor]::Green
    Yellow = [System.ConsoleColor]::Yellow
    Blue   = [System.ConsoleColor]::Blue
    White  = [System.ConsoleColor]::White
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )

    switch ($Type) {
        "Success" { Write-Host "✅ $Message" -ForegroundColor $Colors.Green }
        "Error" { Write-Host "❌ $Message" -ForegroundColor $Colors.Red }
        "Warning" { Write-Host "⚠️  $Message" -ForegroundColor $Colors.Yellow }
        "Info" { Write-Host "ℹ️  $Message" -ForegroundColor $Colors.Blue }
        default { Write-Host "→ $Message" -ForegroundColor $Colors.White }
    }
}

function Check-PortInUse {
    param([int]$Port)

    $connection = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

# Title
Write-Host ""
Write-Host "======================================================" -ForegroundColor $Colors.Green
Write-Host "  🚀 Bewerbungs-Tracker - Starting all services..." -ForegroundColor $Colors.Green
Write-Host "======================================================" -ForegroundColor $Colors.Green
Write-Host ""

# Check Python installation
Write-Status "Checking Python installation..." "Info"
try {
    $PythonVersion = python --version 2>&1
    Write-Status "$PythonVersion" "Success"
} catch {
    Write-Status "Python is not installed or not in PATH" "Error"
    Write-Status "Please install Python from https://www.python.org" "Info"
    Write-Status "Make sure to check 'Add Python to PATH' during installation" "Info"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Check required Python modules
Write-Status "Checking required Python modules..." "Info"
$ModuleCheck = python -c "import imaplib, smtplib, sqlite3, json, os; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Status "Missing required Python modules" "Error"
    Write-Status "Please run: pip install -r requirements.txt" "Info"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Status "All required modules available" "Success"
Write-Host ""

# Change to script directory
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptPath

# Check port availability
Write-Status "Checking port availability..." "Info"
$Ports = @(
    @{ Port = 8080; Name = "Web Server" },
    @{ Port = 8765; Name = "IMAP Proxy" },
    @{ Port = 8766; Name = "Email Service" },
    @{ Port = 8767; Name = "Data Service" }
)

foreach ($PortInfo in $Ports) {
    if (Check-PortInUse -Port $PortInfo.Port) {
        Write-Status "Port $($PortInfo.Port) ($($PortInfo.Name)) is already in use" "Warning"
    }
}
Write-Host ""

# Start Web Server
Write-Status "Starting Web Server (port 8080)..." "Info"
try {
    Start-Process -FilePath "python" `
                  -ArgumentList "-m http.server 8080 --directory ." `
                  -WindowStyle Normal `
                  -PassThru | Out-Null
    Start-Sleep -Seconds 1
    Write-Status "Web Server started" "Success"
} catch {
    Write-Status "Failed to start Web Server: $_" "Error"
}
Write-Host ""

# Start IMAP Proxy
if (Test-Path "imap_proxy.py") {
    Write-Status "Starting IMAP Proxy (port 8765)..." "Info"
    try {
        Start-Process -FilePath "python" `
                      -ArgumentList "imap_proxy.py" `
                      -WindowStyle Normal `
                      -PassThru | Out-Null
        Start-Sleep -Seconds 1
        Write-Status "IMAP Proxy started" "Success"
    } catch {
        Write-Status "Failed to start IMAP Proxy: $_" "Error"
    }
} else {
    Write-Status "imap_proxy.py not found, skipping IMAP Proxy" "Warning"
}
Write-Host ""

# Start Email Service
if (Test-Path "email_service.py") {
    Write-Status "Starting Email Service (port 8766)..." "Info"
    try {
        Start-Process -FilePath "python" `
                      -ArgumentList "email_service.py" `
                      -WindowStyle Normal `
                      -PassThru | Out-Null
        Start-Sleep -Seconds 1
        Write-Status "Email Service started" "Success"
    } catch {
        Write-Status "Failed to start Email Service: $_" "Error"
    }
} else {
    Write-Status "email_service.py not found, skipping Email Service" "Warning"
}
Write-Host ""

# Start Data Service
if (Test-Path "data_service.py") {
    Write-Status "Starting Data Service (port 8767)..." "Info"
    try {
        Start-Process -FilePath "python" `
                      -ArgumentList "data_service.py" `
                      -WindowStyle Normal `
                      -PassThru | Out-Null
        Start-Sleep -Seconds 1
        Write-Status "Data Service started" "Success"
    } catch {
        Write-Status "Failed to start Data Service: $_" "Error"
    }
} else {
    Write-Status "data_service.py not found, skipping Data Service" "Warning"
}
Write-Host ""

# Summary
Write-Host "======================================================" -ForegroundColor $Colors.Green
Write-Status "All services started successfully!" "Success"
Write-Host "======================================================" -ForegroundColor $Colors.Green
Write-Host ""

Write-Host "📍 Service URLs:" -ForegroundColor $Colors.Blue
Write-Host "   🌐 Web App:       http://localhost:8080" -ForegroundColor $Colors.White
Write-Host "   📧 IMAP Proxy:    http://localhost:8765" -ForegroundColor $Colors.White
Write-Host "   💌 Email Service: http://localhost:8766" -ForegroundColor $Colors.White
Write-Host "   💾 Data Service:  http://localhost:8767" -ForegroundColor $Colors.White
Write-Host ""

Write-Host "💡 Tips:" -ForegroundColor $Colors.Blue
Write-Host "   • Open http://localhost:8080 in your browser" -ForegroundColor $Colors.White
Write-Host "   • Configure Email Service with your SMTP/IMAP credentials" -ForegroundColor $Colors.White
Write-Host "   • Use Ctrl+C in each window to stop individual services" -ForegroundColor $Colors.White
Write-Host "   • Or close the command windows to stop everything" -ForegroundColor $Colors.White
Write-Host ""

Write-Status "Services are running. Press Ctrl+C to stop." "Info"
Read-Host "Press Enter to exit this window"
