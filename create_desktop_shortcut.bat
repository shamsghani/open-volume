@echo off
cd /d "%~dp0"
echo ========================================================
echo   Open-Volume: Creating Desktop Shortcut
echo ========================================================
echo.

set "TARGET_EXE=%~dp0open-volume.exe"
if not exist "%TARGET_EXE%" set "TARGET_EXE=%~dp0target\release\open-volume.exe"

if exist "%TARGET_EXE%" (
    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $d = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut((Join-Path $d 'Open Volume.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%~dp0'; $ico = '%~dp0assets\icon.ico'; if (Test-Path $ico) { $s.IconLocation = $ico }; $s.Save()"
    echo [SUCCESS] Desktop shortcut created!
) else (
    python startup_manager.py --desktop
)

echo.
timeout /t 3 >nul

