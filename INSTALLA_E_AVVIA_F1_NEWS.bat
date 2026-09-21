@echo off
setlocal EnableExtensions
title F1 NEWS VALLE DI SUSA - INSTALLA E AVVIA

set "ROOT=%USERPROFILE%\open-social-scheduler-f1"
if not exist "%ROOT%\.git" set "ROOT=%USERPROFILE%\open-social-scheduler"

if not exist "%ROOT%\.git" (
  echo ERRORE: repository F1 non trovato.
  echo Atteso in %USERPROFILE%\open-social-scheduler-f1 oppure %USERPROFILE%\open-social-scheduler
  pause
  exit /b 2
)

cd /d "%ROOT%"
echo === AGGIORNAMENTO F1 NEWS ===
git pull --ff-only origin main
if errorlevel 1 (
  echo ERRORE: impossibile aggiornare il repository.
  pause
  exit /b 3
)

echo === INSTALLAZIONE TASK 11:30 / 19:30 ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "publisher\f1_graphics_automation\INSTALLA_AUTOMAZIONE_23.ps1"
if errorlevel 1 (
  echo ERRORE: installazione automazione F1 News fallita.
  pause
  exit /b 4
)

echo === TEST REALE F1 NEWS ORA ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "publisher\f1_graphics_automation\RUN_F1_NEWS_SLOT.ps1" -Slot immediate
set "RC=%ERRORLEVEL%"

if "%RC%"=="0" (
  echo.
  echo F1 NEWS: ciclo locale terminato senza errori.
) else (
  echo.
  echo F1 NEWS: ciclo non completato. Codice %RC%.
  echo Controlla publisher\f1_graphics_automation\logs
)
pause
exit /b %RC%
