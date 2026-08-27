@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Avvio AI UGC Reel Lab

if not exist ".venv_ugc\Scripts\python.exe" (
  echo Il motore UGC non e installato.
  echo Avvio INSTALLA_UGC_GRATIS.bat...
  call INSTALLA_UGC_GRATIS.bat
  if not exist ".venv_ugc\Scripts\python.exe" exit /b 1
)

if exist "ugc_server.pid" (
  set /p UGC_PID=<ugc_server.pid
  tasklist /FI "PID eq %UGC_PID%" 2>nul | find "%UGC_PID%" >nul
  if not errorlevel 1 goto :apri
)

echo Avvio motore UGC locale sulla porta 8770...
start "AI UGC Engine" /min ".venv_ugc\Scripts\python.exe" "ugc_server.py"
timeout /t 3 /nobreak >nul

:apri
start "" "https://josephsocialmedia2-spec.github.io/open-social-scheduler/ugc-reel-lab.html?v=local-free-v2"
exit /b 0
