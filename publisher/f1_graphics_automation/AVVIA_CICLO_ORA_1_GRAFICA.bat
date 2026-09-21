@echo off
setlocal EnableExtensions EnableDelayedExpansion
title F1 CREATIVE - CICLO ORA 1 GRAFICA

set "ROOT=%USERPROFILE%\open-social-scheduler-f1"
if not exist "%ROOT%\publisher\chatgpt_query_runner\worker.py" set "ROOT=%USERPROFILE%\open-social-scheduler"

if not exist "%ROOT%\publisher\chatgpt_query_runner\worker.py" (
  echo ERRORE: repository F1 non trovato.
  echo Atteso in:
  echo   %USERPROFILE%\open-social-scheduler-f1
  echo oppure
  echo   %USERPROFILE%\open-social-scheduler
  pause
  exit /b 2
)

cd /d "%ROOT%"

echo === F1 CICLO GRAFICO ORA ===
echo Repository: %ROOT%

git fetch origin main
if errorlevel 1 (
  echo ERRORE: git fetch fallito.
  pause
  exit /b 3
)

for %%F in (
  publisher/chatgpt_query_runner/core.py
  publisher/chatgpt_query_runner/ui_driver.py
  publisher/chatgpt_query_runner/worker.py
  publisher/chatgpt_query_runner/f1_browser_creative_queries.json
  publisher/chatgpt_query_runner/requirements.txt
) do (
  git show origin/main:%%F > "%%F.tmp"
  if errorlevel 1 (
    echo ERRORE aggiornamento %%F
    pause
    exit /b 4
  )
  move /Y "%%F.tmp" "%%F" >nul
)

set "PYTHONPATH=%ROOT%"
set "F1_CREATIVE_BACKEND=chatgpt_browser"
set "F1_QUERY_BATCH_SIZE=1"
set "F1_MAX_ATTEMPTS=1"
set "F1_MAX_DOWNLOAD_ATTEMPTS=3"
set "F1_MAX_CHATGPT_TABS=1"\nset "F1_FORCE_COORDINATE_COMPOSER=1"

set "PY_CMD="
py -3.12 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.12"
if not defined PY_CMD set "PY_CMD=py -3"

%PY_CMD% -m pip install -r publisher\chatgpt_query_runner\requirements.txt
if errorlevel 1 (
  echo ERRORE: dipendenze Python.
  pause
  exit /b 5
)

echo.
echo Avvio 1 sola grafica: QUANTO VALE CASA MIA - Variante A
echo NON usare mouse o tastiera finche il ciclo non termina.
echo.

%PY_CMD% -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 1 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo CICLO COMPLETATO: immagine acquisita e salvata.
  echo Cartella: %ROOT%\publisher\final_assets\chatgpt_generated
) else (
  echo CICLO NON COMPLETATO. Codice: %RC%
  echo Log: %ROOT%\publisher\f1_graphics_automation\logs
)

pause
exit /b %RC%
