@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "postiz-stack\windows\postiz.env" (
  echo Configurazione mancante. Esegui prima INSTALLA_POSTIZ_WINDOWS.bat
  pause
  exit /b 1
)
set POSTIZ_STACK_DIR=%CD%\postiz-stack
docker compose --env-file "postiz-stack\windows\postiz.env" -f "postiz-stack\vendor\postiz-docker-compose\docker-compose.yaml" -f "postiz-stack\docker-compose.override.yml" up -d
start "" "http://localhost:4007"
