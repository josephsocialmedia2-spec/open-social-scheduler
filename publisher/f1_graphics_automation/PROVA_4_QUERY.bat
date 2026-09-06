@echo off
setlocal
title F1 GRAFICHE - PROVA 4 QUERY
cd /d "%~dp0\..\.."
echo.
echo ============================================================
echo   F1 GRAFICHE - PROVA REALE 4 QUERY
echo ============================================================
echo.
echo Non usare mouse o tastiera durante il test.
echo Il test termina con successo solo con 4 immagini rilevate e salvate.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_NOTTURNO_23.ps1" -Test4
if errorlevel 1 (
  echo.
  echo PROVA 4 QUERY NON SUPERATA.
  echo Controlla il messaggio e i log sopra.
  pause
  exit /b 1
)
echo.
echo PROVA 4 QUERY SUPERATA: 4/4 GRAFICHE VERIFICATE E SALVATE.
pause
