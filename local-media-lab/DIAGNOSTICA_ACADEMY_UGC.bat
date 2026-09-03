@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Diagnostica F1 Academy UGC

set "OUT=%~dp0DIAGNOSTICA_ACADEMY_UGC.txt"
>"%OUT%" echo F1 IMMOBILIARE ACADEMY - DIAGNOSTICA UGC
>>"%OUT%" echo Data: %date% %time%
>>"%OUT%" echo ============================================================

if exist ".venv_ugc\Scripts\python.exe" (
  >>"%OUT%" echo [OK] Python/venv voce presente
) else (
  >>"%OUT%" echo [ERRORE] .venv_ugc mancante - eseguire INSTALLA_UGC_GRATIS.bat
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  >>"%OUT%" echo [ERRORE] FFmpeg non trovato nel PATH
) else (
  >>"%OUT%" echo [OK] FFmpeg disponibile
  for /f "delims=" %%F in ('where ffmpeg') do >>"%OUT%" echo      %%F
)

where nvidia-smi >nul 2>&1
if errorlevel 1 (
  >>"%OUT%" echo [INFO] GPU NVIDIA non rilevata - verra usata modalita continuita senza lip-sync
) else (
  >>"%OUT%" echo [OK] GPU NVIDIA rilevata
)

if exist "ugc_training_server.py" (
  >>"%OUT%" echo [OK] ugc_training_server.py presente
) else (
  >>"%OUT%" echo [ERRORE] ugc_training_server.py mancante
)

if exist "..\f1-academy\index.html" (
  >>"%OUT%" echo [OK] Academy locale presente
) else (
  >>"%OUT%" echo [ERRORE] cartella ..\f1-academy mancante
)

powershell -NoProfile -Command "try { $r=Invoke-RestMethod -TimeoutSec 2 http://127.0.0.1:8770/api/health; $r ^| ConvertTo-Json -Compress; exit 0 } catch { Write-Output ('SERVER_ERROR: '+$_.Exception.Message); exit 1 }" >>"%OUT%" 2>&1
if errorlevel 1 (
  >>"%OUT%" echo [ERRORE] Server locale 8770 non raggiungibile - eseguire AVVIA_ACADEMY_UGC.bat
) else (
  >>"%OUT%" echo [OK] Server locale 8770 raggiungibile
)

>>"%OUT%" echo ============================================================
>>"%OUT%" echo Se il video fallisce dopo l'avvio, aprire Academy locale e copiare il messaggio rosso mostrato nel job.

start "" notepad "%OUT%"
exit /b 0
