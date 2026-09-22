@echo off
setlocal
REM Resolve repository root from this BAT: publisher\chatgpt_query_runner -> repo root
for %%I in ("%~dp0..\..") do set "REPO_ROOT=%%~fI"
if not exist "%REPO_ROOT%\publisher\chatgpt_query_runner\worker.py" (
  echo ERRORE: repository non trovato. Questo BAT deve restare dentro publisher\chatgpt_query_runner.
  echo Percorso calcolato: %REPO_ROOT%
  pause
  exit /b 2
)
cd /d "%REPO_ROOT%"
set "PYTHONPATH=%REPO_ROOT%"
set F1_CREATIVE_BACKEND=free_browser_router
set F1_QUERY_BATCH_SIZE=1
echo F1 MULTI-AI FREE ULTRAREAL CREATIVE - TEST E2E
echo Repository: %REPO_ROOT%
echo Primo test: QUANTO VALE CASA MIA - variante A
py -3 -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 1 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set EXITCODE=%ERRORLEVEL%
echo.
if "%EXITCODE%"=="0" (
  echo TEST COMPLETATO: controllare last_run.json e asset acquisito.
) else (
  echo TEST NON COMPLETATO. Consultare publisher\f1_graphics_automation\logs
)
pause
exit /b %EXITCODE%
