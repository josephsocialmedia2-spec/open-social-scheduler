@echo off
setlocal
title F1 - INSTALLA PUBBLICATORE MANUALE
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo ============================================================
echo   F1 IMMOBILIARE - PUBBLICAZIONE MANUALE
echo ============================================================
echo.
echo Il programma:
echo   - scarica open-social-scheduler da GitHub
echo   - installa solo il pannello di caricamento manuale
echo   - rimuove i vecchi task di generazione grafica
echo   - crea il collegamento F1 PUBBLICA GRAFICHE
echo   - verifica che AI grafica sia disabilitata
echo.
echo NON vengono installati o avviati generatori ChatGPT, Leonardo o Firefly.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0F1_AUTO_REINSTALL_TEST.ps1"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo F1 PUBBLICATORE MANUALE INSTALLATO E VERIFICATO.
) else (
  echo PROCEDURA F1 INTERROTTA - CODICE %RC%
  echo Controlla la cartella %%USERPROFILE%%\F1_Automazione\logs
)
echo.
pause
exit /b %RC%
