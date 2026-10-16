@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Tuanxiao Credit System - Force Cleanup
echo ========================================
echo.
echo This will:
echo - Stop ONLY this project's server process (PID from server.pid)
echo - Remove server.pid file
echo - Remove server.log file
echo.
echo It no longer kills unrelated python.exe processes.
echo.

choice /C YN /M "Are you sure you want to continue"
if errorlevel 2 goto :cancel
if errorlevel 1 goto :cleanup

:cleanup
echo.
if exist server.pid (
    set /p SERVER_PID=<server.pid
    echo [INFO] Stopping server process - PID: !SERVER_PID!
    taskkill /PID !SERVER_PID! /F >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Process !SERVER_PID! not found or already stopped
    ) else (
        echo [SUCCESS] Server process stopped
        timeout /t 2 /nobreak >nul
    )
    del /f /q server.pid >nul 2>&1
    echo [SUCCESS] PID file removed
) else (
    echo [INFO] PID file not found - server is not running via the scripts
)

echo [INFO] Removing log file...
if exist server.log (
    del /f /q server.log >nul 2>&1
    if exist server.log (
        echo [WARNING] Log file is locked, will be cleaned on next start
    ) else (
        echo [SUCCESS] Log file removed
    )
) else (
    echo [INFO] Log file not found
)

echo.
echo [SUCCESS] Cleanup completed
echo.
pause
exit /b 0

:cancel
echo.
echo [INFO] Cleanup cancelled
echo.
pause
exit /b 0
