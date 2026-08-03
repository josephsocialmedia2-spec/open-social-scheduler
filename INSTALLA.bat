@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALLA_V42.ps1"
if errorlevel 1 (
  echo.
  echo INSTALLAZIONE NON COMPLETATA.
  pause
  exit /b 1
)
endlocal
