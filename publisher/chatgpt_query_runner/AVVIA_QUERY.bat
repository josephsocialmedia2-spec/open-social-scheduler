@echo off
setlocal
cd /d "%~dp0\..\.."
where python >nul 2>nul || (echo Python non trovato.& pause & exit /b 1)
python -m pip install -r publisher\chatgpt_query_runner\requirements.txt
python publisher\chatgpt_query_runner\worker.py
pause
