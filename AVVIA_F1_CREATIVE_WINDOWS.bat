@echo off
setlocal EnableExtensions EnableDelayedExpansion
title F1 ChatGPT Creative - Windows Bootstrap

set "REPO_URL=https://github.com/josephsocialmedia2-spec/open-social-scheduler.git"
set "EXPECTED_ORIGIN_1=https://github.com/josephsocialmedia2-spec/open-social-scheduler"
set "EXPECTED_ORIGIN_2=https://github.com/josephsocialmedia2-spec/open-social-scheduler.git"
set "TARGET=%USERPROFILE%\open-social-scheduler"
set "REPO_ROOT="

echo === F1 CHATGPT CREATIVE WINDOWS BOOTSTRAP ===
echo BAT=%~f0
echo BAT_DIR=%~dp0

where git >nul 2>nul || (
  echo BLOCCO: Git for Windows non trovato.
  echo Installa Git for Windows e rilancia questo file.
  pause
  exit /b 10
)

REM ------------------------------------------------------------
REM 1) Cerca una working copy Git valida gia presente.
REM Preferisci la working copy F1 gia creata: NON clonare di nuovo.
REM ------------------------------------------------------------
call :TRY_REPO "%USERPROFILE%\open-social-scheduler-f1"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Documents\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Desktop\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Downloads\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%~dp0."
if not defined REPO_ROOT (
  for /L %%N in (2,1,20) do (
    if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler-f1-%%N"
  )
)

REM ------------------------------------------------------------
REM 2) Clona SOLO se non esiste alcuna repository valida.
REM ------------------------------------------------------------
if not defined REPO_ROOT (
  call :CHOOSE_CLONE_TARGET
  echo Nessuna repository Git valida trovata. Prima installazione in: !CLONE_TARGET!
  git clone "%REPO_URL%" "!CLONE_TARGET!" || (
    echo ERRORE: clonazione repository fallita.
    pause
    exit /b 11
  )
  set "REPO_ROOT=!CLONE_TARGET!"
)

echo.
echo === REPOSITORY RIUTILIZZATO ===
echo REPO_ROOT=!REPO_ROOT!
git -C "!REPO_ROOT!" remote -v
git -C "!REPO_ROOT!" rev-parse HEAD
git -C "!REPO_ROOT!" status --short

REM ------------------------------------------------------------
REM 3) Aggiorna SOLO i file del motore F1 senza riclonare e senza
REM toccare gli altri file locali dell'utente.
REM ------------------------------------------------------------
git -C "!REPO_ROOT!" fetch origin main || (
  echo ERRORE: git fetch origin main fallito.
  pause
  exit /b 12
)

call :SYNC_ONE "publisher/chatgpt_query_runner/core.py"
call :SYNC_ONE "publisher/chatgpt_query_runner/ui_driver.py"
call :SYNC_ONE "publisher/chatgpt_query_runner/worker.py"
call :SYNC_ONE "publisher/chatgpt_query_runner/f1_browser_creative_queries.json"
call :SYNC_ONE "publisher/chatgpt_query_runner/requirements.txt"

REM ------------------------------------------------------------
REM 4) Verifica che la working copy scelta contenga il codice richiesto.
REM ------------------------------------------------------------
call :CHECK_REQUIRED_FILES
if errorlevel 1 (
  echo La working copy scelta non contiene ancora tutti i file F1 richiesti.
  echo Creo una copia pulita separata senza eliminare nulla.
  call :SYNC_ONE
set "SYNC_PATH=%~1"
for %%D in ("!REPO_ROOT!\%~dp1.") do if not exist "%%~fD" mkdir "%%~fD" >nul 2>nul
git -C "!REPO_ROOT!" show "origin/main:%SYNC_PATH%" > "!REPO_ROOT!\%SYNC_PATH:/=\%.tmp" || (
  echo ERRORE: impossibile aggiornare %SYNC_PATH% da origin/main.
  del /q "!REPO_ROOT!\%SYNC_PATH:/=\%.tmp" >nul 2>nul
  exit /b 1
)
move /Y "!REPO_ROOT!\%SYNC_PATH:/=\%.tmp" "!REPO_ROOT!\%SYNC_PATH:/=\%" >nul
echo Aggiornato: %SYNC_PATH%
exit /b 0


:CHECK_REQUIRED_FILES
  if errorlevel 1 (
    echo ERRORE: anche la copia fresca non contiene i file richiesti.
    pause
    exit /b 13
  )
)

cd /d "!REPO_ROOT!" || (
  echo ERRORE: impossibile entrare in !REPO_ROOT!
  pause
  exit /b 14
)

set "PYTHONPATH=!REPO_ROOT!"
set "F1_CREATIVE_BACKEND=chatgpt_browser"
set "F1_QUERY_BATCH_SIZE=1"

echo.
echo === AMBIENTE ===
echo CD=!CD!
echo PYTHONPATH=!PYTHONPATH!

REM ------------------------------------------------------------
REM 5) Preferisci Python 3.12, poi 3.11/3.13/3.14, infine default py -3.
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
  echo BLOCCO: nessun Python 3 disponibile tramite Python Launcher.
  pause
  exit /b 15
)

echo PYTHON=!PY_CMD!
!PY_CMD! --version

echo.
echo === INSTALLAZIONE / VERIFICA DIPENDENZE ===
!PY_CMD! -m pip install -r publisher\chatgpt_query_runner\requirements.txt || (
  echo ERRORE: installazione dipendenze fallita.
  pause
  exit /b 16
)

echo.
echo === TEST IMPORT PUBLISHER ===
!PY_CMD! -c "import os,sys; print('CWD=',os.getcwd()); print('PYTHONPATH=',os.environ.get('PYTHONPATH')); import publisher; print('PUBLISHER_OK=',publisher.__file__)" || (
  echo ERRORE: import publisher fallito.
  pause
  exit /b 17
)

echo.
echo === TEST IMPORT WORKER ===
!PY_CMD! -c "from publisher.chatgpt_query_runner import worker; print('WORKER_IMPORT_OK=',worker.__file__)" || (
  echo ERRORE: import worker fallito.
  pause
  exit /b 18
)

echo.
echo === TEST CLI WORKER ===
!PY_CMD! -m publisher.chatgpt_query_runner.worker --help >nul || (
  echo ERRORE: worker --help fallito.
  pause
  exit /b 19
)

echo.
echo === TEST E2E: QUANTO VALE CASA MIA - VARIANTE A ===
!PY_CMD! -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 1 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set "EXITCODE=!ERRORLEVEL!"

echo.
if "!EXITCODE!"=="0" (
  echo TEST E2E COMPLETATO.
  echo Stato: publisher\chatgpt_query_runner\last_run.json
  echo Asset: publisher\final_assets\chatgpt_generated
) else (
  echo TEST E2E NON COMPLETATO. Exit code=!EXITCODE!
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


:CHOOSE_CLONE_TARGET
set "CLONE_TARGET=%TARGET%"
if not exist "!CLONE_TARGET!" exit /b 0
set "CLONE_TARGET=%USERPROFILE%\open-social-scheduler-f1"
if not exist "!CLONE_TARGET!" exit /b 0
for /L %%N in (2,1,50) do (
  if exist "!CLONE_TARGET!" (
    set "CLONE_TARGET=%USERPROFILE%\open-social-scheduler-f1-%%N"
  )
)
exit /b 0


:CLONE_FRESH_AND_SWITCH
call :CHOOSE_CLONE_TARGET
echo Clonazione working copy pulita in !CLONE_TARGET!
git clone "%REPO_URL%" "!CLONE_TARGET!" || (
  echo ERRORE: impossibile creare la working copy pulita.
  pause
  exit /b 21
)
set "REPO_ROOT=!CLONE_TARGET!"
set "SWITCHED_FRESH=1"
exit /b 0


:CHECK_REQUIRED_FILES
if not exist "!REPO_ROOT!\publisher\__init__.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\worker.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\core.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\ui_driver.py" exit /b 1
if not exist "!REPO_ROOT!\publisher\chatgpt_query_runner\f1_browser_creative_queries.json" exit /b 1
exit /b 0
