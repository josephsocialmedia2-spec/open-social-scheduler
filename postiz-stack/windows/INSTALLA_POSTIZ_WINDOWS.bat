@echo off
setlocal
cd /d "%~dp0\..\.."
PowerShell -NoProfile -ExecutionPolicy Bypass -File "postiz-stack\windows\INSTALLA_POSTIZ_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo INSTALLAZIONE NON COMPLETATA. Leggi il messaggio sopra.
  pause
  exit /b 1
)
echo.
echo INSTALLAZIONE COMPLETATA.
pause
