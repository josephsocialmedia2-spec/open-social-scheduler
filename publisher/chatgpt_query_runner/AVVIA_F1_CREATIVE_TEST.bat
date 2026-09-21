@echo off
setlocal
cd /d "%~dp0\..\.."
set F1_CREATIVE_BACKEND=chatgpt_browser
set F1_QUERY_BATCH_SIZE=1
echo F1 CHATGPT BROWSER CREATIVE - TEST E2E
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
