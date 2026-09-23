@echo off
setlocal
title F1 AUTOMAZIONE - RISCARICA E PROVA
cd /d "%~dp0"

echo.
echo ============================================================
echo   F1 AUTOMAZIONE - RISCARICA PROGRAMMA E PROVA REALE
echo ============================================================
echo.
echo Il programma:
echo   - scarica da zero open-social-scheduler da GitHub
echo   - conserva la vecchia installazione come backup
echo   - verifica Git, Python e Chrome
echo   - installa le dipendenze F1
echo   - crea il pulsante "F1 - AVVIA ORA E PUBBLICA" sul Desktop
echo   - lancia subito una prova reale
echo.
echo Durante la prova NON usare mouse o tastiera.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0F1_AUTO_REINSTALL_TEST.ps1"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ============================================================
  echo PROCEDURA F1 TERMINATA SENZA ERRORI DEL PROGRAMMA
  echo ============================================================
) else (
  echo ============================================================
  echo PROCEDURA F1 INTERROTTA - CODICE %RC%
  echo Controlla la cartella %%USERPROFILE%%\F1_Automazione\logs
  echo ============================================================
)
echo.
pause
exit /b %RC%
