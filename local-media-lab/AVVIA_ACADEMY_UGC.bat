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
timeout /t 3 /nobreak >nul

start "" "https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-academy/"
exit /b 0
