@echo off
setlocal
title Open Social Scheduler - Ripristino Postiz
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESTORE_POSTIZ_WINDOWS.ps1" -RestoreSecrets
if errorlevel 1 (
  echo.
  echo ERRORE durante il ripristino.
  pause
  exit /b 1
)
echo.
echo Ripristino completato.
pause
