@echo off
setlocal EnableExtensions
chcp 65001 >nul
title F1 Immobiliare Academy - Installazione Video UGC

set "HERE=%~dp0"

if exist "%HERE%local-media-lab\INSTALLA_UGC_GRATIS.bat" if exist "%HERE%f1-academy\index.html" (
  echo Repository F1 rilevato.
  call "%HERE%local-media-lab\INSTALLA_UGC_GRATIS.bat"
  if errorlevel 1 exit /b 1
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut((Join-Path $desktop 'F1 Immobiliare Academy.lnk')); $s.TargetPath='%HERE%local-media-lab\AVVIA_ACADEMY_UGC.bat'; $s.WorkingDirectory='%HERE%local-media-lab'; $s.Description='F1 Immobiliare Academy con video UGC locale'; $s.Save()" >nul 2>&1
  call "%HERE%local-media-lab\AVVIA_ACADEMY_UGC.bat"
  exit /b %errorlevel%
)

set "DEST=%USERPROFILE%\F1_Immobiliare_Academy"
set "LAB=%DEST%\local-media-lab"
set "ACADEMY=%DEST%\f1-academy"
if not exist "%LAB%" mkdir "%LAB%"
if not exist "%ACADEMY%" mkdir "%ACADEMY%"

echo ============================================================
echo F1 IMMOBILIARE ACADEMY - DOWNLOAD ULTIMA VERSIONE
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $repo='https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/'; $lab='%LAB%'; $academy='%ACADEMY%'; $labFiles=@('INSTALLA_UGC_GRATIS.bat','AVVIA_UGC_GRATIS.bat','AVVIA_ACADEMY_UGC.bat','ARRESTA_UGC_GRATIS.bat','DIAGNOSTICA_ACADEMY_UGC.bat','ugc_server.py','ugc_training_server.py','ugc_tts.py'); foreach($f in $labFiles){Write-Host ('Scarico local-media-lab/'+$f); Invoke-WebRequest -UseBasicParsing -Uri ($repo+'local-media-lab/'+$f) -OutFile (Join-Path $lab $f)}; $academyFiles=@('index.html','styles.css','app.js','lessons.js'); foreach($f in $academyFiles){Write-Host ('Scarico f1-academy/'+$f); Invoke-WebRequest -UseBasicParsing -Uri ($repo+'f1-academy/'+$f) -OutFile (Join-Path $academy $f)}"
if errorlevel 1 (
  echo ERRORE: download file Academy non riuscito.
  pause
  exit /b 1
)

cd /d "%LAB%"
call INSTALLA_UGC_GRATIS.bat
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut((Join-Path $desktop 'F1 Immobiliare Academy.lnk')); $s.TargetPath='%LAB%\AVVIA_ACADEMY_UGC.bat'; $s.WorkingDirectory='%LAB%'; $s.Description='F1 Immobiliare Academy con video UGC locale'; $s.Save(); $d=$ws.CreateShortcut((Join-Path $desktop 'Diagnostica F1 Academy UGC.lnk')); $d.TargetPath='%LAB%\DIAGNOSTICA_ACADEMY_UGC.bat'; $d.WorkingDirectory='%LAB%'; $d.Description='Diagnostica video UGC F1 Academy'; $d.Save()" >nul 2>&1

echo.
echo INSTALLAZIONE COMPLETATA.
echo Da ora usa l'icona Desktop: F1 Immobiliare Academy
call AVVIA_ACADEMY_UGC.bat
exit /b %errorlevel%
