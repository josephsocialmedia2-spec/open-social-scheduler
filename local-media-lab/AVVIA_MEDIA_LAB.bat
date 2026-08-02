@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Open Social Scheduler - Media Lab Locale

if not exist ".venv\Scripts\python.exe" (
  echo Il Media Lab non e ancora installato.
  echo Avvio INSTALLA_MEDIA_LAB.bat...
  call INSTALLA_MEDIA_LAB.bat
  if not exist ".venv\Scripts\python.exe" exit /b 1
)

echo Avvio motore locale su http://127.0.0.1:8765
echo Non chiudere questa finestra durante le elaborazioni.
echo.
".venv\Scripts\python.exe" server.py
