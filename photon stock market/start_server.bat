@echo off
title Photon — Real-time WebSocket Stock Ticker
cd /d "%~dp0"

echo ============================================================
echo   Photon — Real-time WebSocket Stock Ticker
echo ============================================================
echo.
echo [*] Launching server and opening web browser...
echo [*] Local URL: http://127.0.0.1:8000
echo.

:: Check if virtual environment exists; create if missing
if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Setting up .venv...
    python -m venv .venv
    echo [*] Installing dependencies from requirements.txt...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

:: Open the web browser after a 2-second delay in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"

:: Start the Photon application server
.venv\Scripts\python.exe run.py

echo.
echo Server stopped.
pause
