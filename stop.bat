@echo off
echo Stopping any running Open-Volume instances...
taskkill /f /im open-volume.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo Done.
timeout /t 2 >nul
