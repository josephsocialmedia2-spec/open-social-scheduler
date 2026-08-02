@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Installazione Open Social Scheduler - Media Lab Locale

echo ============================================================
echo OPEN SOCIAL SCHEDULER - MEDIA LAB LOCALE
echo Installazione componenti sul computer
echo ============================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>&1
  if not %errorlevel%==0 (
    echo ERRORE: Python 3 non e installato o non e nel PATH.
    echo Installa Python 3 da python.org selezionando "Add Python to PATH".
    pause
    exit /b 1
  )
  set "PY_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/6] Creazione ambiente virtuale...
  %PY_CMD% -m venv .venv
  if not %errorlevel%==0 goto :errore
) else (
  echo [1/6] Ambiente virtuale gia presente.
)

echo [2/6] Aggiornamento strumenti Python...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if not %errorlevel%==0 goto :errore

echo [3/6] Installazione FastAPI, Whisper e componenti...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not %errorlevel%==0 goto :errore

echo [4/6] Preparazione modello Whisper Base...
".venv\Scripts\python.exe" -c "import whisper; whisper.load_model('base'); print('Modello Whisper Base pronto.')"
if not %errorlevel%==0 echo ATTENZIONE: il modello verra scaricato al primo utilizzo.

echo [5/6] Verifica FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel%==0 goto :ffmpeg_ok

echo FFmpeg non trovato nel PATH.
where winget >nul 2>&1
if not %errorlevel%==0 goto :ffmpeg_manuale

echo Installazione FFmpeg tramite Windows Package Manager...
winget install --id Gyan.FFmpeg --exact --accept-source-agreements --accept-package-agreements
if not %errorlevel%==0 goto :ffmpeg_manuale

echo.
echo FFmpeg installato. Potrebbe essere necessario chiudere e riaprire questa finestra.
goto :cartelle

:ffmpeg_manuale
echo.
echo ATTENZIONE: installa FFmpeg manualmente e aggiungilo al PATH,
echo oppure copia ffmpeg.exe nella cartella:
echo %~dp0ffmpeg\bin\
echo.

:ffmpeg_ok
echo FFmpeg disponibile.

:cartelle
echo [6/6] Preparazione cartelle locali...
if not exist "incoming" mkdir "incoming"
if not exist "elaborazioni" mkdir "elaborazioni"

echo.
echo ============================================================
echo INSTALLAZIONE COMPLETATA
echo Avvia il programma con AVVIA_MEDIA_LAB.bat
echo ============================================================
pause
exit /b 0

:errore
echo.
echo ERRORE DURANTE L'INSTALLAZIONE.
echo Controlla la connessione e riprova.
pause
exit /b 1
