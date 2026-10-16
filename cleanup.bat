@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Tuanxiao Credit System - Force Cleanup
echo ========================================
echo.
echo This will:
echo - Kill all python.exe processes
echo - Remove server.pid file
echo - Remove server.log file
echo.

choice /C YN /M "Are you sure you want to continue"
if errorlevel 2 goto :cancel
if errorlevel 1 goto :cleanup

:cleanup
echo.
echo [INFO] Killing all python.exe processes...
taskkill /F /IM python.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] No python.exe processes found
) else (
    echo [SUCCESS] Python processes killed
    REM Wait for processes to fully terminate
    timeout /t 2 /nobreak >nul
)

echo [INFO] Removing PID file...
if exist server.pid (
    del /f /q server.pid >nul 2>&1
    echo [SUCCESS] PID file removed
) else (
    echo [INFO] PID file not found
)

echo [INFO] Removing log file...
if exist server.log (
    REM Try to delete, if fails, file might be locked
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
