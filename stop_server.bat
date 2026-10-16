@echo off
setlocal enabledelayedexpansion

set PID_FILE=server.pid

echo ========================================
echo Tuanxiao Credit System - Stop Server
echo ========================================
echo.

REM Check if PID file exists
if not exist %PID_FILE% (
    echo [INFO] Server is not running - PID file not found
    echo.
    pause
    exit /b 0
)

REM Read PID
set /p SERVER_PID=<%PID_FILE%

echo [INFO] Found PID: !SERVER_PID!

REM Check if process exists
tasklist /FI "PID eq !SERVER_PID!" 2>nul | find /I /N "python.exe">nul
if errorlevel 1 (
    echo [INFO] Server is not running - process not found
    echo [INFO] Cleaning up PID file...
    del /f /q %PID_FILE% >nul 2>&1
    echo.
    pause
    exit /b 0
)

REM Stop server
echo [INFO] Stopping server - PID: !SERVER_PID!
taskkill /PID !SERVER_PID! /F >nul 2>&1

if errorlevel 1 (
    echo [ERROR] Failed to stop server
    echo.
    pause
    exit /b 1
) else (
    echo [SUCCESS] Server stopped successfully
    del /f /q %PID_FILE% >nul 2>&1
    echo [INFO] PID file cleaned up
)

echo.
pause
