@echo off
setlocal
title F1 GRAFICHE - PROVA 1 QUERY
cd /d "%~dp0\..\.."
echo.
echo ============================================================
echo   F1 GRAFICHE - PROVA REALE 1 QUERY
echo ============================================================
echo.
echo Non usare mouse o tastiera durante il test.
echo Il test termina con successo solo dopo:
echo prompt verificato, invio verificato, immagine rilevata e file salvato.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_NOTTURNO_23.ps1" -Test
if errorlevel 1 (
  echo.
  echo PROVA 1 QUERY NON SUPERATA.
  echo Controlla il messaggio e i log sopra.
  pause
  exit /b 1
)
echo.
echo PROVA 1 QUERY SUPERATA: GRAFICA VERIFICATA E SALVATA.
pause
