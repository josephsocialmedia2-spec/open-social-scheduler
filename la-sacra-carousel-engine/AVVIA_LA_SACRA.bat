@echo off
setlocal
cd /d %~dp0
where python >nul 2>&1
if errorlevel 1 (
  echo Python non trovato. Installa Python 3.11 o superiore e riprova.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
start "" http://127.0.0.1:5055
python app.py
