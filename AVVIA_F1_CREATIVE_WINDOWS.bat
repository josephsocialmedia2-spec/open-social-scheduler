@echo off
setlocal EnableExtensions EnableDelayedExpansion
title F1 ChatGPT Creative - Windows Bootstrap

set "REPO_URL=https://github.com/josephsocialmedia2-spec/open-social-scheduler.git"
set "EXPECTED_ORIGIN_1=https://github.com/josephsocialmedia2-spec/open-social-scheduler"
set "EXPECTED_ORIGIN_2=https://github.com/josephsocialmedia2-spec/open-social-scheduler.git"
set "REPO_ROOT="
set "TARGET=%USERPROFILE%\open-social-scheduler-f1"

echo === F1 CHATGPT CREATIVE WINDOWS BOOTSTRAP ===
echo BAT=%~f0

where git >nul 2>nul || (
  echo BLOCCO: Git for Windows non trovato.
  pause
  exit /b 10
)

REM ------------------------------------------------------------
REM 1) RIUSA SEMPRE UNA REPOSITORY ESISTENTE.
REM Non riclonare se una working copy valida e gia presente.
REM ------------------------------------------------------------
call :TRY_REPO "%USERPROFILE%\open-social-scheduler-f1"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Documents\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Desktop\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Downloads\open-social-scheduler"

if not defined REPO_ROOT (
  echo Nessuna working copy valida trovata.
  echo Eseguo UNA SOLA prima installazione in: %TARGET%
  if exist "%TARGET%" (
    echo BLOCCO: %TARGET% esiste ma non e il repository corretto.
    echo Non cancello nulla. Rinomina/sposta quella cartella e rilancia.
    pause
    exit /b 11
  )
  git clone "%REPO_URL%" "%TARGET%" || (
    echo ERRORE: clonazione iniziale fallita.
    pause
    exit /b 12
  )
  set "REPO_ROOT=%TARGET%"
)

echo.
echo === REPOSITORY RIUTILIZZATO ===
echo REPO_ROOT=!REPO_ROOT!
git -C "!REPO_ROOT!" remote -v

REM ------------------------------------------------------------
REM 2) NON fare pull/reset/clone della repo intera.
REM Aggiorna soltanto i file del motore F1 dal branch main.
REM ------------------------------------------------------------
git -C "!REPO_ROOT!" fetch origin main || (
  echo ERRORE: git fetch origin main fallito.
  pause
  exit /b 13
)

call :SYNC_ONE "publisher/chatgpt_query_runner/core.py"
if errorlevel 1 exit /b 14
call :SYNC_ONE "publisher/chatgpt_query_runner/ui_driver.py"
if errorlevel 1 exit /b 14
call :SYNC_ONE "publisher/chatgpt_query_runner/worker.py"
if errorlevel 1 exit /b 14
call :SYNC_ONE "publisher/chatgpt_query_runner/f1_browser_creative_queries.json"
if errorlevel 1 exit /b 14
call :SYNC_ONE "publisher/chatgpt_query_runner/requirements.txt"
if errorlevel 1 exit /b 14

call :CHECK_REQUIRED_FILES
if errorlevel 1 (
  echo ERRORE: file richiesti mancanti dopo la sincronizzazione.
  pause
  exit /b 15
)

cd /d "!REPO_ROOT!" || (
  echo ERRORE: impossibile entrare in !REPO_ROOT!
  pause
  exit /b 16
)

set "PYTHONPATH=!REPO_ROOT!"
set "F1_CREATIVE_BACKEND=chatgpt_browser"
set "F1_QUERY_BATCH_SIZE=1"\nset "F1_MAX_ATTEMPTS=1"

echo.
echo === AMBIENTE ===
echo CD=!CD!
echo PYTHONPATH=!PYTHONPATH!

REM ------------------------------------------------------------
REM 3) Python.
REM ------------------------------------------------------------
set "PY_CMD="
py -3.12 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.12"
if not defined PY_CMD (
  py -3.11 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
  py -3.13 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.13"
)
if not defined PY_CMD (
  py -3.14 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.14"
)
if not defined PY_CMD (
  py -3 -c "import sys" >nul 2>nul && set "PY_CMD=py -3"
)

if not defined PY_CMD (
  echo BLOCCO: Python 3 non trovato.
  pause
  exit /b 17
)

echo PYTHON=!PY_CMD!
!PY_CMD! --version

echo.
echo === DIPENDENZE ===
!PY_CMD! -m pip install -r publisher\chatgpt_query_runner\requirements.txt || (
  echo ERRORE: installazione dipendenze fallita.
  pause
  exit /b 18
)

echo.
echo === TEST IMPORT ===
!PY_CMD! -c "import publisher; print('PUBLISHER_OK=',publisher.__file__)" || (
  echo ERRORE: import publisher fallito.
  pause
  exit /b 19
)

!PY_CMD! -c "from publisher.chatgpt_query_runner import worker; print('WORKER_IMPORT_OK=',worker.__file__)" || (
  echo ERRORE: import worker fallito.
  pause
  exit /b 20
)

echo.
echo === PRODUZIONE GRAFICA: QUANTO VALE CASA MIA - A ===
!PY_CMD! -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 1 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set "EXITCODE=!ERRORLEVEL!"

echo.
if "!EXITCODE!"=="0" (
  echo GRAFICA ACQUISITA E SALVATA.
  echo Stato: publisher\chatgpt_query_runner\last_run.json
  echo Asset: publisher\final_assets\chatgpt_generated
) else (
  echo PRODUZIONE NON COMPLETATA. Exit code=!EXITCODE!
  echo Log: publisher\f1_graphics_automation\logs
)
pause
exit /b !EXITCODE!


:TRY_REPO
set "CAND=%~f1"
if not exist "!CAND!\.git" exit /b 0
set "ORIGIN="
for /f "delims=" %%R in ('git -C "!CAND!" remote get-url origin 2^>nul') do set "ORIGIN=%%R"
if /I "!ORIGIN!"=="%EXPECTED_ORIGIN_1%" set "REPO_ROOT=!CAND!"
if /I "!ORIGIN!"=="%EXPECTED_ORIGIN_2%" set "REPO_ROOT=!CAND!"
exit /b 0


:SYNC_ONE
set "SYNC_PATH=%~1"
set "LOCAL_PATH=!SYNC_PATH:/=\!"
git -C "!REPO_ROOT!" show "origin/main:!SYNC_PATH!" > "!REPO_ROOT!\!LOCAL_PATH!.tmp"
if errorlevel 1 (
  echo ERRORE: impossibile aggiornare !SYNC_PATH!
  del /q "!REPO_ROOT!\!LOCAL_PATH!.tmp" >nul 2>nul
  exit /b 1
)
move /Y "!REPO_ROOT!\!LOCAL_PATH!.tmp" "!REPO_ROOT!\!LOCAL_PATH!" >nul
echo Aggiornato: !SYNC_PATH!
exit /b 0


:CHECK_REQUIRED_FILES
if not exist "!REPO_ROOT!\publisher\__init__.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\worker.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\core.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\ui_driver.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\f1_browser_creative_queries.json" exit /b 1
exit /b 0
