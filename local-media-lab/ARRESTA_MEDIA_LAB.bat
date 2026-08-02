@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if not exist "media_lab.pid" (
  echo Nessun Media Lab locale risulta avviato.
  pause
  exit /b 0
)

set /p PID=<media_lab.pid
if "%PID%"=="" (
  echo File PID non valido.
  pause
  exit /b 1
)

taskkill /PID %PID% /F >nul 2>&1
if %errorlevel%==0 (
  echo Media Lab arrestato.
  del /q media_lab.pid >nul 2>&1
) else (
  echo Processo non trovato o gia chiuso.
  del /q media_lab.pid >nul 2>&1
)
pause
