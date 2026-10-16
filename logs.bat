@echo off
setlocal enabledelayedexpansion

set LOG_FILE=server.log

if not exist %LOG_FILE% (
    echo Log file not found: %LOG_FILE%
    pause
    exit /b 1
)

echo ========================================
echo Tuanxiao Credit System - Server Logs
echo ========================================
echo.
echo Press Ctrl+C to exit
echo.

REM Continuously display logs (Windows equivalent of tail -f)
powershell -Command "Get-Content %LOG_FILE% -Wait"
