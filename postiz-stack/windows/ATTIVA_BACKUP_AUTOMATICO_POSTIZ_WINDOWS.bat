@echo off
setlocal
title Open Social Scheduler - Backup automatico Postiz
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATTIVA_BACKUP_AUTOMATICO_POSTIZ_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo ERRORE durante la configurazione del backup automatico.
  pause
  exit /b 1
)
echo.
echo Backup automatico attivato.
pause
