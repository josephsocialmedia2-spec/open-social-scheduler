param(
    [ValidateSet('auto','midday','evening','immediate')]
    [string]$Slot = 'auto'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$NewsBuilder = Join-Path $Root 'publisher\news\f1_valle_susa_news.py'
$Worker = Join-Path $Root 'publisher\chatgpt_query_runner\worker.py'
$QueryFile = Join-Path $Root 'publisher\news\f1_news_current.local.json'
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$LogDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "f1-news-$Slot-$Stamp.log"
$PyOut = Join-Path $LogDir "f1-news-worker-$Stamp-out.log"
$PyErr = Join-Path $LogDir "f1-news-worker-$Stamp-err.log"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Write-Host $line
}

function Show-WorkerLogs {
    if (Test-Path $PyOut) {
        Get-Content $PyOut -ErrorAction SilentlyContinue | ForEach-Object {
            Add-Content -Path $Log -Value $_ -Encoding UTF8
            Write-Host $_
        }
    }
    if (Test-Path $PyErr) {
        Get-Content $PyErr -ErrorAction SilentlyContinue | ForEach-Object {
            Add-Content -Path $Log -Value $_ -Encoding UTF8
            Write-Host $_ -ForegroundColor Red
        }
    }
}

Set-Location $Root
Write-Log "RUN START - F1 NEWS VALLE DI SUSA slot=$Slot"

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { throw 'Python non trovato nel PATH.' }
$PythonExe = $PythonCmd.Source

try {
    $dirty = git status --porcelain
    if (-not $dirty) {
        git pull --ff-only origin main 2>&1 | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -ne 0) { throw 'git pull fallito' }
    } else {
        Write-Log 'Repository con modifiche locali: uso la versione presente senza sovrascriverla.'
    }
} catch {
    Write-Log "Aggiornamento Git non riuscito: $($_.Exception.Message)"
}

$env:PYTHONPATH = $Root
$env:F1_CREATIVE_BACKEND = 'chatgpt_browser'
$env:F1_QUERY_BATCH_SIZE = '1'
$env:F1_MAX_ATTEMPTS = '1'
$env:F1_MAX_DOWNLOAD_ATTEMPTS = '3'
$env:F1_MAX_CHATGPT_TABS = '1'
$env:F1_FORCE_COORDINATE_COMPOSER = '1'
$env:F1_GENERATION_TIMEOUT = '180'
$env:F1_GENERATION_START_TIMEOUT = '45'
$env:F1_PUBLISH_VERIFY_SECONDS = '1800'
$env:F1_INBOX_PORT = '8877'

python -c "import pyautogui, pyperclip, pygetwindow, uiautomation, flask, requests, PIL, tzdata" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Log 'Installazione dipendenze mancanti.'
    python -m pip install -r publisher\chatgpt_query_runner\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze browser fallita.' }
    python -m pip install -r publisher\manual_asset_inbox\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze inbox fallita.' }
    python -m pip install -r publisher\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze publisher fallita.' }
}

Remove-Item $QueryFile -Force -ErrorAction SilentlyContinue
& $PythonExe $NewsBuilder --slot $Slot --write-query-file $QueryFile 2>&1 | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { throw "Preparazione F1 News fallita. Codice: $LASTEXITCODE" }
if (-not (Test-Path $QueryFile)) {
    Write-Log 'NOOP: nessuna notizia immobiliare nuova da pubblicare.'
    exit 0
}

try {
    & $StartInbox -Restart
    Write-Log 'F1 Inbox locale pronta.'
} catch {
    Write-Log "ERRORE F1 Inbox: $($_.Exception.Message)"
    throw
}

Remove-Item $PyOut,$PyErr -Force -ErrorAction SilentlyContinue

$WorkerArgs = @(
    '-m',
    'publisher.chatgpt_query_runner.worker',
    '--batch-size','1',
    '--query-file','publisher/news/f1_news_current.local.json'
)

$Process = Start-Process -FilePath $PythonExe -ArgumentList $WorkerArgs -WorkingDirectory $Root -RedirectStandardOutput $PyOut -RedirectStandardError $PyErr -NoNewWindow -Wait -PassThru

Show-WorkerLogs
$WorkerExit = $Process.ExitCode

if ($WorkerExit -eq 0) {
    Write-Log 'RUN END - F1 News completata dal GPT browser fino alla verifica disponibile.'
    exit 0
}

Write-Log "RUN END - F1 News non completata, codice worker $WorkerExit."
Write-Host ''
Write-Host 'ULTIMO OUTPUT WORKER:' -ForegroundColor Yellow
if (Test-Path $PyErr) {
    Get-Content $PyErr -ErrorAction SilentlyContinue | Select-Object -Last 100 | ForEach-Object {
        Write-Host $_ -ForegroundColor Red
    }
}
Write-Host "Log: $Log" -ForegroundColor Yellow
exit $WorkerExit
