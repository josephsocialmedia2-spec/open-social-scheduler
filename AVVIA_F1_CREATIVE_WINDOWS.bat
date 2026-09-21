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
REM ------------------------------------------------------------
call :TRY_REPO "%~dp0."
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Documents\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Desktop\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\Downloads\open-social-scheduler"
if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler-f1"
if not defined REPO_ROOT (
  for /L %%N in (2,1,20) do (
    if not defined REPO_ROOT call :TRY_REPO "%USERPROFILE%\open-social-scheduler-f1-%%N"
  )
)

REM ------------------------------------------------------------
REM 2) Se non esiste una repo valida, clona in una directory libera.
REM La presenza di una cartella non-Git NON viene mai cancellata.
REM ------------------------------------------------------------
if not defined REPO_ROOT (
  call :CHOOSE_CLONE_TARGET
  echo Repository Git valida non trovata.
  echo Clonazione sicura in: !CLONE_TARGET!
  git clone "%REPO_URL%" "!CLONE_TARGET!" || (
    echo ERRORE: clonazione repository fallita.
    pause
    exit /b 11
  )
  set "REPO_ROOT=!CLONE_TARGET!"
)

echo.
echo === REPOSITORY TROVATO ===
echo REPO_ROOT=!REPO_ROOT!
git -C "!REPO_ROOT!" remote -v
git -C "!REPO_ROOT!" rev-parse HEAD
git -C "!REPO_ROOT!" status --short

REM ------------------------------------------------------------
REM 3) Aggiorna in modo sicuro. Mai reset --hard / clean / delete.
REM ------------------------------------------------------------
git -C "!REPO_ROOT!" fetch origin main || (
  echo ERRORE: git fetch origin main fallito.
  pause
  exit /b 12
)

set "DIRTY="
for /f "delims=" %%S in ('git -C "!REPO_ROOT!" status --porcelain 2^>nul') do set "DIRTY=1"

set "BEHIND=0"
for /f "delims=" %%B in ('git -C "!REPO_ROOT!" rev-list --count HEAD..origin/main 2^>nul') do set "BEHIND=%%B"

if defined DIRTY (
  echo Working tree con modifiche locali: non verranno cancellate.
  if not "!BEHIND!"=="0" (
    echo La copia locale e anche indietro rispetto a origin/main.
    echo Creo una working copy F1 separata e pulita per non toccare i dati locali.
    call :CLONE_FRESH_AND_SWITCH
  )
) else (
  git -C "!REPO_ROOT!" checkout main >nul 2>nul || (
    echo Impossibile fare checkout di main nella copia corrente.
    echo Creo una working copy F1 separata e pulita.
    call :CLONE_FRESH_AND_SWITCH
  )
  if not defined SWITCHED_FRESH (
    git -C "!REPO_ROOT!" pull --ff-only origin main || (
      echo Pull fast-forward non possibile. Creo una working copy F1 separata.
      call :CLONE_FRESH_AND_SWITCH
    )
  )
)

REM ------------------------------------------------------------
REM 4) Verifica che la working copy scelta contenga il codice richiesto.
REM ------------------------------------------------------------
call :CHECK_REQUIRED_FILES
if errorlevel 1 (
  echo La working copy scelta non contiene ancora tutti i file F1 richiesti.
  echo Creo una copia pulita separata senza eliminare nulla.
  call :CLONE_FRESH_AND_SWITCH
  call :CHECK_REQUIRED_FILES
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
