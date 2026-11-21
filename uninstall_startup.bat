@echo off
title Open-Volume - Remove from Windows Startup
cd /d "%~dp0"
echo ========================================================
echo   Removing Open-Volume from Windows Startup...
echo ========================================================
echo.

schtasks /delete /tn "OpenVolume" /f >nul 2>&1
if exist "startup_manager.py" (
    python startup_manager.py --disable >nul 2>&1
)

echo.
echo [SUCCESS] Open-Volume has been removed from Windows Startup.
echo.
timeout /t 3 >nul

