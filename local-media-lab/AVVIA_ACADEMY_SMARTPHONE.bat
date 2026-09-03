@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title F1 Immobiliare Academy - Smartphone

if not exist ".venv_ugc\Scripts\python.exe" (
  echo Il motore UGC non e installato.
  echo Avvio INSTALLA_UGC_GRATIS.bat...
  call INSTALLA_UGC_GRATIS.bat
  if not exist ".venv_ugc\Scripts\python.exe" exit /b 1
)

if exist "ugc_server.pid" (
  set /p UGC_PID=<ugc_server.pid
  tasklist /FI "PID eq !UGC_PID!" 2>nul | find "!UGC_PID!" >nul
  if not errorlevel 1 (
    taskkill /PID !UGC_PID! /T /F >nul 2>&1
    timeout /t 1 /nobreak >nul
  )
  del /q "ugc_server.pid" >nul 2>&1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ip=(Get-NetIPConfiguration ^| Where-Object {$_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up'} ^| ForEach-Object {$_.IPv4Address.IPAddress} ^| Select-Object -First 1); if($ip){$ip}"`) do set "LAN_IP=%%I"

if not defined LAN_IP (
  echo ERRORE: non trovo l'indirizzo IP del PC sulla rete locale.
  echo Verifica che il PC sia collegato al Wi-Fi o via Ethernet.
  pause
  exit /b 1
)

echo Avvio F1 Academy per PC + smartphone...
start "F1 Academy UGC Engine" /min ".venv_ugc\Scripts\python.exe" "ugc_training_server.py"
timeout /t 3 /nobreak >nul

set "PHONE_URL=http://%LAN_IP%:8770/academy/"
set "PC_URL=http://127.0.0.1:8770/academy/"

> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo F1 IMMOBILIARE ACADEMY
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo.
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo Smartphone sulla stessa rete Wi-Fi:
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo %PHONE_URL%
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo.
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo PC:
>> "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt" echo %PC_URL%

echo.
echo ============================================================
echo SMARTPHONE: %PHONE_URL%
echo PC:         %PC_URL%
echo ============================================================
echo.
echo IMPORTANTE:
echo - telefono e PC devono essere sulla stessa rete Wi-Fi/LAN;
echo - se Windows chiede accesso alla rete privata, consenti;
echo - se il firewall blocca la porta 8770, esegui questo file come amministratore.
echo.
start "" "%PC_URL%"
start notepad "%USERPROFILE%\Desktop\F1_ACADEMY_SMARTPHONE.txt"
pause
