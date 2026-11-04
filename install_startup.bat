@echo off
title Open-Volume - Add to Windows Startup
echo ========================================================
echo   Adding Open-Volume to Windows Startup...
echo ========================================================
echo.

python startup_manager.py --enable

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Open-Volume will now start automatically when you log into Windows!
) else (
    echo.
    echo [ERROR] Failed to add Open-Volume to Windows Startup.
)

echo.
pause

