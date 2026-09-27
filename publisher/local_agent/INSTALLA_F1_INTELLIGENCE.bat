@echo off
setlocal
title F1 Social Intelligence - Installazione
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_F1_INTELLIGENCE_AGENT.ps1"
if errorlevel 1 (
  echo.
  echo Installazione non completata. Leggi il messaggio sopra.
  pause
  exit /b 1
)
echo.
echo F1 Social Intelligence e' attivo.
timeout /t 4 >nul
