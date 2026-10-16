@echo off
setlocal enabledelayedexpansion

set PID_FILE=server.pid
set LOG_FILE=server.log

echo ========================================
echo Tuanxiao Credit System - Start Server
echo ========================================
echo.

REM Check if already running
if exist %PID_FILE% (
    set /p OLD_PID=<%PID_FILE%
    tasklist /FI "PID eq !OLD_PID!" 2>nul | find /I "python.exe" >nul
    if not errorlevel 1 (
        echo [ERROR] Server already running - PID: !OLD_PID!
        echo Run stop_server.bat first
        echo.
        pause
        exit /b 1
    )
    del /f /q %PID_FILE% >nul 2>&1
)

REM Clean old log file
if exist %LOG_FILE% (
    del /f /q %LOG_FILE% >nul 2>&1
    if exist %LOG_FILE% (
        echo [WARNING] Cannot delete old log file, it may be locked
        echo Will append to existing log
    )
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

REM Check Waitress
pip show waitress >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Waitress...
    pip install waitress
)

REM Start server
echo [INFO] Starting server...
set BACKGROUND_MODE=1
start "DeployServer" /B cmd /c "python deploy_server.py >> "%LOG_FILE%" 2>&1"
set START_PID=!ERRORLEVEL!

REM Wait
timeout /t 2 /nobreak >nul

REM Get PID
set SERVER_PID=
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /NH 2^>nul ^| findstr /R "python.exe"') do (
    set SERVER_PID=%%a
    goto :gotpid
)

:gotpid
if "!SERVER_PID!"=="" (
    echo [ERROR] Failed to start server
    echo Check server.log for details
    pause
    exit /b 1
)

REM Save PID
echo !SERVER_PID! > %PID_FILE%

echo.
echo ========================================
echo [SUCCESS] Server started
echo ========================================
echo.
echo PID: !SERVER_PID!
echo Log: %LOG_FILE%
echo.
echo Commands:
echo   status.bat  - Check status
echo   logs.bat    - View logs
echo   stop_server.bat - Stop server
echo.
echo Access: http://localhost:5000
echo.
