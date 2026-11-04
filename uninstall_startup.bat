@echo off
title Open-Volume - Remove from Windows Startup
echo ========================================================
echo   Removing Open-Volume from Windows Startup...
echo ========================================================
echo.

python startup_manager.py --disable

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Open-Volume has been removed from Windows Startup.
) else (
    echo.
    echo [ERROR] Failed to remove Open-Volume from Windows Startup.
)

echo.
pause

