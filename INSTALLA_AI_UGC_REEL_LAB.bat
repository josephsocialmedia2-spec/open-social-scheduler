@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title AI UGC Reel Lab - Installazione

echo ============================================================
echo AI UGC REEL LAB - INSTALLAZIONE A DOPPIO CLIC
echo 100%% gratuito - elaborazione sul tuo PC
echo ============================================================
echo.

if exist "local-media-lab\INSTALLA_UGC_GRATIS.bat" (
  call "local-media-lab\INSTALLA_UGC_GRATIS.bat"
  exit /b %errorlevel%
)

echo Non trovo la cartella local-media-lab accanto a questo file.
echo Scarico il modulo UGC dal repository ufficiale del progetto...
set "DEST=%USERPROFILE%\AI_UGC_Reel_Lab"
if not exist "%DEST%" mkdir "%DEST%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$base='https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/local-media-lab/'; $dest='%DEST%'; $files=@('INSTALLA_UGC_GRATIS.bat','AVVIA_UGC_GRATIS.bat','ARRESTA_UGC_GRATIS.bat','ugc_server.py','ugc_tts.py'); foreach($f in $files){Write-Host ('Scarico '+$f); Invoke-WebRequest -UseBasicParsing -Uri ($base+$f) -OutFile (Join-Path $dest $f)}"
if errorlevel 1 (
  echo ERRORE durante il download dei file UGC.
  pause
  exit /b 1
)

cd /d "%DEST%"
call INSTALLA_UGC_GRATIS.bat
exit /b %errorlevel%
