@echo off
setlocal EnableExtensions
title F1 ChatGPT Creative - Windows Bootstrap
set "REPO_URL=https://github.com/josephsocialmedia2-spec/open-social-scheduler.git"
set "TARGET=%USERPROFILE%\open-social-scheduler"

echo === F1 CHATGPT CREATIVE WINDOWS BOOTSTRAP ===
echo BAT=%~f0
echo BAT_DIR=%~dp0

REM 1) Prefer repository containing this BAT, if valid.
for %%I in ("%~dp0.") do set "HERE=%%~fI"
if exist "%HERE%\publisher\__init__.py" if exist "%HERE%\publisher\chatgpt_query_runner\worker.py" set "REPO_ROOT=%HERE%"

REM 2) Otherwise use canonical local clone.
if not defined REPO_ROOT if exist "%TARGET%\publisher\__init__.py" if exist "%TARGET%\publisher\chatgpt_query_runner\worker.py" set "REPO_ROOT=%TARGET%"

REM 3) Otherwise clone complete repository. A BAT downloaded alone is not enough.
if not defined REPO_ROOT (
  where git >nul 2>nul || (
    echo BLOCCO: Git non trovato. Installa Git for Windows e rilancia questo file.
    pause
    exit /b 10
  )
  echo Repository locale non trovato. Clonazione in %TARGET%
  git clone "%REPO_URL%" "%TARGET%" || (
    echo ERRORE: clonazione repository fallita.
    pause
    exit /b 11
  )
  set "REPO_ROOT=%TARGET%"
)

echo REPO_ROOT=%REPO_ROOT%
cd /d "%REPO_ROOT%" || exit /b 12
set "PYTHONPATH=%REPO_ROOT%"
set "F1_CREATIVE_BACKEND=chatgpt_browser"
set "F1_QUERY_BATCH_SIZE=1"
echo CD=%CD%
echo PYTHONPATH=%PYTHONPATH%

if not exist "publisher\__init__.py" (
  echo ERRORE: publisher\__init__.py non trovato.
  pause
  exit /b 13
)
if not exist "publisher\chatgpt_query_runner\worker.py" (
  echo ERRORE: worker.py non trovato.
  pause
  exit /b 14
)

where py
where python
py -3 --version || (
  echo BLOCCO: Python 3 non disponibile tramite py launcher.
  pause
  exit /b 15
)

echo === Installazione/verifica dipendenze ===
py -3 -m pip install -r publisher\chatgpt_query_runner\requirements.txt || (
  echo ERRORE: installazione dipendenze fallita.
  pause
  exit /b 16
)

echo === Test import publisher ===
py -3 -c "import os,sys; print('CWD=',os.getcwd()); print('PYTHONPATH=',os.environ.get('PYTHONPATH')); print('SYS.PATH=',sys.path); import publisher; print('PUBLISHER_OK=',publisher.__file__)" || (
  echo ERRORE: import publisher fallito.
  pause
  exit /b 17
)

echo === Test import worker ===
py -3 -c "from publisher.chatgpt_query_runner import worker; print('WORKER_IMPORT_OK=',worker.__file__)" || (
  echo ERRORE: import worker fallito.
  pause
  exit /b 18
)

echo === Test CLI worker ===
py -3 -m publisher.chatgpt_query_runner.worker --help >nul || (
  echo ERRORE: worker --help fallito.
  pause
  exit /b 19
)

echo === TEST E2E: QUANTO VALE CASA MIA - variante A ===
py -3 -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 1 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
  echo TEST E2E COMPLETATO. Verifica asset e last_run.json.
) else (
  echo TEST E2E NON COMPLETATO. Exit code=%EXITCODE%
  echo Log: publisher\f1_graphics_automation\logs
)
pause
exit /b %EXITCODE%
