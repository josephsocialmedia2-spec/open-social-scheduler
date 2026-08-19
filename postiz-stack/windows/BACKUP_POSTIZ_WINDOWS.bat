@echo off
setlocal
title Open Social Scheduler - Backup Postiz
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BACKUP_POSTIZ_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo ERRORE durante il backup.
  pause
  exit /b 1
)
echo.
echo Backup completato.
pause
