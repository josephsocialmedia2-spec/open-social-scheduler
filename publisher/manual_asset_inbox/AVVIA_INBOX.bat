@echo off
setlocal
cd /d "%~dp0\..\.."
where python >nul 2>nul || (echo Python non trovato.& pause & exit /b 1)
python -m pip install -r publisher\manual_asset_inbox\requirements.txt
start "F1 Inbox" http://127.0.0.1:8765/
python publisher\manual_asset_inbox\server.py
