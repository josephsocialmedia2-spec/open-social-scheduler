@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title Installazione AI UGC Reel Lab - 100%% locale e gratuito

echo ============================================================
echo AI UGC REEL LAB - INSTALLAZIONE GRATUITA
echo Ollama + Chatterbox Multilingual + MuseTalk 1.5 + FFmpeg
echo Nessuna API a pagamento. Nessun credito a consumo.
echo ============================================================
echo.

where winget >nul 2>&1
if errorlevel 1 (
  echo ERRORE: winget non trovato. Aggiorna "App Installer" dal Microsoft Store.
  pause
  exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
  echo [1/10] Installazione Git...
  winget install --id Git.Git --exact --accept-source-agreements --accept-package-agreements
) else (
  echo [1/10] Git gia disponibile.
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [2/10] Installazione FFmpeg...
  winget install --id Gyan.FFmpeg --exact --accept-source-agreements --accept-package-agreements
) else (
  echo [2/10] FFmpeg gia disponibile.
)

py -3.11 -V >nul 2>&1
if errorlevel 1 (
  echo [3/10] Installazione Python 3.11 per Chatterbox...
  winget install --id Python.Python.3.11 --exact --accept-source-agreements --accept-package-agreements
  echo.
  echo Python 3.11 e stato installato. Chiudi questa finestra e rilancia INSTALLA_UGC_GRATIS.bat.
  pause
  exit /b 0
) else (
  echo [3/10] Python 3.11 disponibile.
)

if not exist ".venv_ugc\Scripts\python.exe" (
  echo [4/10] Creo ambiente voce UGC...
  py -3.11 -m venv .venv_ugc
  if errorlevel 1 goto :errore
)
".venv_ugc\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :errore

echo [5/10] Installazione server locale e Chatterbox Multilingual...
".venv_ugc\Scripts\python.exe" -m pip install fastapi uvicorn[standard] python-multipart chatterbox-tts
if errorlevel 1 goto :errore

where ollama >nul 2>&1
if errorlevel 1 (
  echo [6/10] Installazione Ollama...
  winget install --id Ollama.Ollama --exact --accept-source-agreements --accept-package-agreements
  echo Ollama installato. Il modello per gli script verra scaricato al primo avvio utile.
) else (
  echo [6/10] Ollama gia disponibile.
  start "" /min ollama serve >nul 2>&1
  timeout /t 2 /nobreak >nul
  ollama pull llama3.2:3b
)

where nvidia-smi >nul 2>&1
if errorlevel 1 goto :senza_gpu

echo [7/10] GPU NVIDIA rilevata. Preparo MuseTalk 1.5...
py -3.10 -V >nul 2>&1
if errorlevel 1 (
  echo Installazione Python 3.10 per MuseTalk...
  winget install --id Python.Python.3.10 --exact --accept-source-agreements --accept-package-agreements
  echo.
  echo Python 3.10 e stato installato. Chiudi questa finestra e rilancia INSTALLA_UGC_GRATIS.bat.
  pause
  exit /b 0
)

if not exist "engines" mkdir "engines"
if not exist "engines\MuseTalk\.git" (
  git clone https://github.com/TMElyralab/MuseTalk.git "engines\MuseTalk"
  if errorlevel 1 goto :errore
) else (
  echo MuseTalk gia scaricato.
)

if not exist ".venv_musetalk\Scripts\python.exe" (
  py -3.10 -m venv .venv_musetalk
  if errorlevel 1 goto :errore
)
".venv_musetalk\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel

echo [8/10] Installazione PyTorch CUDA e dipendenze MuseTalk...
".venv_musetalk\Scripts\python.exe" -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 goto :errore
".venv_musetalk\Scripts\python.exe" -m pip install -r "engines\MuseTalk\requirements.txt"
if errorlevel 1 goto :errore
".venv_musetalk\Scripts\python.exe" -m pip install --no-cache-dir -U openmim
".venv_musetalk\Scripts\python.exe" -m mim install mmengine
".venv_musetalk\Scripts\python.exe" -m mim install "mmcv>=2.0.1"
".venv_musetalk\Scripts\python.exe" -m mim install "mmdet>=3.1.0"
".venv_musetalk\Scripts\python.exe" -m pip install --no-build-isolation chumpy
".venv_musetalk\Scripts\python.exe" -m mim install "mmpose>=1.1.0"
if errorlevel 1 goto :errore

echo [9/10] Download modelli gratuiti MuseTalk...
pushd "engines\MuseTalk"
call "..\..\.venv_musetalk\Scripts\activate.bat"
call download_weights.bat
popd
if errorlevel 1 (
  echo ATTENZIONE: download modelli incompleto. Puoi rilanciare questo installer: riprendera i file mancanti.
)
goto :finale

:senza_gpu
echo [7/10] Nessuna GPU NVIDIA rilevata.
echo La parte script e voce viene installata normalmente.
echo MuseTalk 1.5 richiede una GPU NVIDIA compatibile per una generazione pratica.
echo Non viene attivato alcun servizio a pagamento come fallback.
echo [8/10] MuseTalk saltato.
echo [9/10] Modelli MuseTalk saltati.

:finale
echo [10/10] Creo cartelle e collegamento Desktop...
if not exist "ugc_incoming" mkdir "ugc_incoming"
if not exist "ugc_elaborazioni" mkdir "ugc_elaborazioni"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut((Join-Path $desktop 'AI UGC Reel Lab.lnk')); $s.TargetPath=(Join-Path '%~dp0' 'AVVIA_UGC_GRATIS.bat'); $s.WorkingDirectory='%~dp0'; $s.Description='Generatore Reel UGC locale F1 Immobiliare e Real Media Pro'; $s.Save()" >nul 2>&1

echo.
echo ============================================================
echo INSTALLAZIONE COMPLETATA
echo Usa l'icona Desktop: AI UGC Reel Lab
echo.
echo IMPORTANTE PER RISULTATI NATURALI:
echo - modello: video verticale reale 10-30 sec, volto ben visibile
echo - voce: 8-20 sec di una donna italiana consenziente, senza musica
echo - B-roll: foto/video reali F1 o Real Media Pro
echo ============================================================
pause
exit /b 0

:errore
echo.
echo ============================================================
echo ERRORE INSTALLAZIONE UGC
echo Nessun servizio a pagamento e stato attivato.
echo Puoi rilanciare l'installer: i passaggi gia completati restano validi.
echo ============================================================
pause
exit /b 1
