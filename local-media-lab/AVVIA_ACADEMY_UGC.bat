@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title F1 Immobiliare Academy - AI UGC

if not exist ".venv_ugc\Scripts\python.exe" (
  echo Il motore UGC non e installato.
  echo Avvio INSTALLA_UGC_GRATIS.bat...
  call INSTALLA_UGC_GRATIS.bat
  if not exist ".venv_ugc\Scripts\python.exe" exit /b 1
)

if exist "ugc_server.pid" (
  set /p UGC_PID=<ugc_server.pid
  tasklist /FI "PID eq %UGC_PID%" 2>nul | find "%UGC_PID%" >nul
  if not errorlevel 1 (
    echo Arresto del precedente motore UGC...
    taskkill /PID %UGC_PID% /T /F >nul 2>&1
    timeout /t 1 /nobreak >nul
  )
  del /q "ugc_server.pid" >nul 2>&1
)

echo Avvio motore Academy sulla porta 8770...
echo - con GPU NVIDIA/MuseTalk: lip-sync UGC completo
echo - senza MuseTalk: presenter/B-roll + voce + sottotitoli
start "F1 Academy UGC Engine" /min ".venv_ugc\Scripts\python.exe" "ugc_training_server.py"

set READY=0
for /L %%I in (1,1,15) do (
  powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:8770/api/health; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 (
    set READY=1
    goto :ready
  )
  timeout /t 1 /nobreak >nul
)

:ready
if "%READY%"=="1" (
  start "" "http://127.0.0.1:8770/academy/"
  exit /b 0
)

echo.
echo ERRORE: il motore Academy non ha risposto sulla porta 8770.
echo Avvio diagnostica nel browser...
start "" "http://127.0.0.1:8770/api/health"
pause
exit /b 1
