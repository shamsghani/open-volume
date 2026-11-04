@echo off
cd /d "%~dp0"
echo ========================================================
echo   Open-Volume: Creating Desktop Shortcut
echo ========================================================
python startup_manager.py --desktop
echo.
echo Desktop shortcut created! You can now launch Open-Volume
echo directly from your Desktop with 0 background console windows.
echo ========================================================
timeout /t 3 >nul

