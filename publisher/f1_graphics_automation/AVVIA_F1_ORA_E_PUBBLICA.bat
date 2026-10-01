@echo off
setlocal
title F1 - PUBBLICA ORA
cd /d "%~dp0\..\.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_INBOX.ps1" -Restart
if errorlevel 1 (
  echo F1 Pubblicatore Manuale non disponibile.
  pause
  exit /b 1
)
start "F1 PUBBLICA GRAFICHE" http://127.0.0.1:8877/
echo.
echo F1 MANUAL PUBLISH ONLY
echo Nessuna grafica viene generata o modificata automaticamente.
echo Carica la grafica definitiva nel pannello aperto.
echo.
exit /b 0
