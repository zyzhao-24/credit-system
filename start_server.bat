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
    tasklist /FI "PID eq !OLD_PID!" 2>nul | find /I "python" >nul
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

REM Check dependencies
pip show waitress flask flask-sqlalchemy flask-cors flask-migrate pyjwt cryptography python-dotenv openpyxl >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

REM SECRET_KEY is required in production mode
if "%SECRET_KEY%"=="" (
    echo [WARNING] SECRET_KEY is not set; deploy_server.py will refuse to start.
    echo           Set it first: set SECRET_KEY=^<random-long-string^>
    pause
    exit /b 1
)

REM Start server (deploy_server.py writes its own PID file)
echo [INFO] Starting server...
set BACKGROUND_MODE=1
start "DeployServer" /B cmd /c "python deploy_server.py >> "%LOG_FILE%" 2>&1"

REM Wait for the server process to write its PID
set SERVER_PID=
for /L %%i in (1,1,10) do (
    timeout /t 1 /nobreak >nul
    if exist %PID_FILE% (
        set /p SERVER_PID=<%PID_FILE%
        goto :gotpid
    )
)

:gotpid
if "!SERVER_PID!"=="" (
    echo [ERROR] Failed to start server
    echo Check server.log for details
    pause
    exit /b 1
)

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
echo Student: http://localhost:5000/login
echo Admin:   http://localhost:5000/admin/login
echo.
