@echo off
echo ========================================
echo  Zenith Cloud Laptop Daemon
echo ========================================
echo.
echo Loading .env from project root...
echo.

cd /d "%~dp0\.."

REM Check python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+.
    pause
    exit /b 1
)

REM Check .env
if not exist ".env" (
    echo [ERROR] .env not found in project root.
    pause
    exit /b 1
)

REM Check required vars
findstr /C:"ZENITH_CLOUD_URL" .env >nul 2>&1
if errorlevel 1 (
    echo [WARNING] ZENITH_CLOUD_URL not set in .env - daemon will connect to localhost!
)
findstr /C:"BRIDGE_PIN" .env >nul 2>&1
if errorlevel 1 (
    echo [WARNING] BRIDGE_PIN not set in .env
)

echo Starting laptop daemon...
echo.
python cloud/laptop_client.py
