# Photon — One-Click Startup Script (PowerShell)
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Photon — Real-time WebSocket Stock Ticker" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] Launching server and opening web browser..." -ForegroundColor Yellow
Write-Host "[*] URL: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""

# Ensure virtual environment exists
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[!] Setting up Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

# Open web browser after 2 seconds in a background job
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

# Start the application server
.\.venv\Scripts\python.exe run.py
