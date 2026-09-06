@echo off
setlocal
title F1 GRAFICHE - Produzione completa
cd /d "%~dp0\..\.."
echo.
echo ===============================================
echo   F1 GRAFICHE - AVVIO PRODUZIONE COMPLETA
echo ===============================================
echo.
echo Avvio Chrome, Generatore Grafica F1 e 4 query.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_NOTTURNO_23.ps1" -Manual
if errorlevel 1 (
  echo.
  echo PRODUZIONE NON COMPLETATA.
  echo Controlla il messaggio sopra.
  pause
  exit /b 1
)
echo.
echo PRODUZIONE COMPLETATA.
pause
