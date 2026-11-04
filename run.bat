@echo off
title Mountain Everest Numpad Audio Layer 2
cd /d "%~dp0"

echo =======================================================
echo    Mountain Everest 60 - Numpad Audio Layer 2
echo =======================================================
echo.
echo Starting Numpad Audio Layer controller...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)

