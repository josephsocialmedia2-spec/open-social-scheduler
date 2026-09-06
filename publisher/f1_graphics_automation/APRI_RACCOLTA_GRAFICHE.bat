@echo off
setlocal
cd /d "%~dp0\..\.."
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0START_INBOX.ps1"
start "F1 Raccolta Grafiche" http://127.0.0.1:8765/
