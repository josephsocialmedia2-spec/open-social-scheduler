@echo off
setlocal EnableExtensions
chcp 65001 >nul
title F1 Immobiliare Academy - Smartphone

set "DEST=%USERPROFILE%\F1_Immobiliare_Academy"
set "LAB=%DEST%\local-media-lab"
set "ACADEMY=%DEST%\f1-academy"
if not exist "%LAB%" mkdir "%LAB%"
if not exist "%ACADEMY%" mkdir "%ACADEMY%"

echo ============================================================
echo F1 IMMOBILIARE ACADEMY - SMARTPHONE
 echo PC = MOTORE VIDEO / TELEFONO = INTERFACCIA
 echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $repo='https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/'; $lab='%LAB%'; $academy='%ACADEMY%'; $labFiles=@('INSTALLA_UGC_GRATIS.bat','AVVIA_ACADEMY_SMARTPHONE.bat','AVVIA_ACADEMY_UGC.bat','ARRESTA_UGC_GRATIS.bat','ugc_server.py','ugc_training_server.py','ugc_tts.py'); foreach($f in $labFiles){Write-Host ('Scarico local-media-lab/'+$f); Invoke-WebRequest -UseBasicParsing -Uri ($repo+'local-media-lab/'+$f) -OutFile (Join-Path $lab $f)}; $academyFiles=@('index.html','styles.css','app.js','lessons.js'); foreach($f in $academyFiles){Write-Host ('Scarico f1-academy/'+$f); Invoke-WebRequest -UseBasicParsing -Uri ($repo+'f1-academy/'+$f) -OutFile (Join-Path $academy $f)}"
if errorlevel 1 (
 echo Download non riuscito. Controlla Internet e riprova.
 pause
 exit /b 1
)

cd /d "%LAB%"
if not exist ".venv_ugc\Scripts\python.exe" call INSTALLA_UGC_GRATIS.bat
if not exist ".venv_ugc\Scripts\python.exe" exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $m=$ws.CreateShortcut((Join-Path $desktop 'F1 Academy Smartphone.lnk')); $m.TargetPath='%LAB%\AVVIA_ACADEMY_SMARTPHONE.bat'; $m.WorkingDirectory='%LAB%'; $m.Description='F1 Academy su smartphone nella rete Wi-Fi'; $m.Save()" >nul 2>&1

call AVVIA_ACADEMY_SMARTPHONE.bat
exit /b %errorlevel%
