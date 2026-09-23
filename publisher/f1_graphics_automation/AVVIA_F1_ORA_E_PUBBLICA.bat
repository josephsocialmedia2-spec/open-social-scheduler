@echo off
setlocal
title F1 - AVVIA ORA E PUBBLICA
cd /d "%~dp0\..\.."

echo.
echo ============================================================
echo   F1 IMMOBILIARE - GENERA ORA + QA + BRAND + PUBBLICA
echo ============================================================
echo.
echo Questo comando:
echo   1. aggiorna il repository
echo   2. verifica/avvia runner e poller Windows
echo   3. avvia F1 Inbox
echo   4. usa free_browser_router
echo   5. genera QUANTO VALE CASA MIA - Variante A
echo   6. richiede ULTRAREALISM_PASS
echo   7. applica il brand F1
echo   8. invia alla pipeline di pubblicazione
echo   9. attende PUBLISHED_VERIFIED
echo.
echo IMPORTANTE: lascia aperta la sessione Windows.
echo Non usare mouse o tastiera durante la generazione/QA browser.
echo.

git fetch origin main
if errorlevel 1 (
  echo ERRORE: impossibile aggiornare da GitHub.
  pause
  exit /b 2
)

git status --porcelain > "%TEMP%\f1-git-status.txt"
for %%A in ("%TEMP%\f1-git-status.txt") do if %%~zA==0 (
  git pull --ff-only origin main
)

set "PYTHONPATH=%CD%"
set "F1_CREATIVE_BACKEND=free_browser_router"
set "F1_QUERY_BATCH_SIZE=1"
set "F1_MAX_ATTEMPTS=6"
set "F1_MAX_DOWNLOAD_ATTEMPTS=3"
set "F1_MAX_CHATGPT_TABS=1"
set "F1_GENERATION_TIMEOUT=240"
set "F1_GENERATION_START_TIMEOUT=60"
set "F1_PUBLISH_VERIFY_SECONDS=1800"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "publisher\f1_graphics_automation\RUN_F1_DAILY_CREATIVE_TEST.ps1"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ============================================================
  echo F1 COMPLETATO: pipeline terminata senza errore.
  echo Controlla lo stato finale PUBLISHED_VERIFIED nella coda F1.
  echo ============================================================
) else (
  echo ============================================================
  echo F1 NON COMPLETATO. Codice: %RC%
  echo Log: publisher\f1_graphics_automation\logs
  echo ============================================================
)
echo.
pause
exit /b %RC%
