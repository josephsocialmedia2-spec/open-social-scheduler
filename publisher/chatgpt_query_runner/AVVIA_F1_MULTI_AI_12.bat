@echo off
setlocal
for %%I in ("%~dp0..\..") do set "REPO_ROOT=%%~fI"
if not exist "%REPO_ROOT%\publisher\chatgpt_query_runner\worker.py" (
  echo ERRORE: repository non trovato.
  pause
  exit /b 2
)
cd /d "%REPO_ROOT%"
set "PYTHONPATH=%REPO_ROOT%"
set F1_CREATIVE_BACKEND=free_browser_router
set F1_QUERY_BATCH_SIZE=12

echo ==================================================
echo F1 MULTI-AI FREE IMAGE ENGINE - 12 VARIANTI
echo 6 INTENT x A/B - ULTRAREALISM GATE OBBLIGATORIO
echo Provider: ChatGPT ^> Leonardo ^> Firefly
echo Nessuna OPENAI_API_KEY richiesta
echo ==================================================
echo.

py -3 -m publisher.chatgpt_query_runner.worker --fresh-run --batch-size 12 --query-file publisher/chatgpt_query_runner/f1_browser_creative_queries.json
set EXITCODE=%ERRORLEVEL%
echo.
if "%EXITCODE%"=="0" (
  echo BATCH COMPLETATO: 12 asset hanno superato acquisizione, Visual QA e brand layer.
) else (
  echo BATCH NON COMPLETATO. Controllare publisher\f1_graphics_automation\logs
  echo Nessun asset privo di ULTRAREALISM_PASS deve essere pubblicato.
)
pause
exit /b %EXITCODE%
