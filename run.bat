@echo off
title Open-Volume Audio Mixer
cd /d "%~dp0"

echo =======================================================
echo    Open-Volume : High-Performance Audio Layer 2 (Rust)
echo =======================================================
echo.
if exist "target\release\open-volume.exe" (
    echo Starting native Rust Open-Volume...
    start "" "target\release\open-volume.exe"
) else (
    echo Building and running native Rust Open-Volume...
    cargo run --release
)


