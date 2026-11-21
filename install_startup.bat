@echo off
title Open-Volume - Add to Windows Startup
cd /d "%~dp0"
echo ========================================================
echo   Adding Open-Volume to Windows Startup...
echo ========================================================
echo.

if exist "open-volume.exe" (
    schtasks /create /tn "OpenVolume" /tr "\"%~dp0open-volume.exe\"" /sc onlogon /rl highest /f
) else if exist "target\release\open-volume.exe" (
    schtasks /create /tn "OpenVolume" /tr "\"%~dp0target\release\open-volume.exe\"" /sc onlogon /rl highest /f
) else (
    python startup_manager.py --enable
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Open-Volume will now start automatically when you log into Windows!
) else (
    echo.
    echo [ERROR] Failed to add Open-Volume to Windows Startup.
)

echo.
timeout /t 3 >nul

