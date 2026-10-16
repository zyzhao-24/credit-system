@echo off
setlocal enabledelayedexpansion

set PID_FILE=server.pid

echo ========================================
echo Tuanxiao Credit System - Server Status
echo ========================================
echo.

if not exist %PID_FILE% (
    echo Status: [NOT RUNNING]
    echo.
    pause
    exit /b 0
)

set /p SERVER_PID=<%PID_FILE%

tasklist /FI "PID eq %SERVER_PID%" 2>nul | find /I /N "python.exe">nul
if errorlevel 1 (
    echo Status: [NOT RUNNING] (process not found)
    echo PID file exists but process is stopped
    echo.
) else (
    echo Status: [RUNNING]
    echo PID: %SERVER_PID%
    echo Log file: server.log
    echo.
    echo View logs: logs.bat
    echo Stop server: stop_server.bat
    echo.
)

pause
