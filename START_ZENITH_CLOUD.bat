@echo off
title ZENITH Cloud Link
cd /d "%~dp0"
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="ZENITH_CLOUD_URL" set "ZENITH_CLOUD_URL=%%b"
    if /i "%%a"=="BRIDGE_PIN" set "BRIDGE_PIN=%%b"
  )
)
if "%ZENITH_CLOUD_URL%"=="" set /p ZENITH_CLOUD_URL="Cloud URL (wss://zenith-cloud-brain.onrender.com/ws): "
if "%BRIDGE_PIN%"=="" set /p BRIDGE_PIN="BRIDGE PIN: "
echo Starting Zenith Cloud Link -^> %ZENITH_CLOUD_URL%
python cloud\laptop_client.py
pause
