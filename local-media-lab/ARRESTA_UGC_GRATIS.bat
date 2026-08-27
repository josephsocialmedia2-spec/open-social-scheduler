@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if not exist "ugc_server.pid" (
  echo Motore UGC non risulta in esecuzione.
  timeout /t 2 /nobreak >nul
  exit /b 0
)

set /p UGC_PID=<ugc_server.pid
if "%UGC_PID%"=="" goto :fine

echo Arresto motore UGC PID %UGC_PID%...
taskkill /PID %UGC_PID% /T /F >nul 2>&1

:fine
if exist "ugc_server.pid" del /q "ugc_server.pid" >nul 2>&1
echo Motore UGC arrestato.
timeout /t 2 /nobreak >nul
exit /b 0
