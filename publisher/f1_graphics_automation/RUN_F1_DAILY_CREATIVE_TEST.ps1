param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$QueryFile = Join-Path $Root 'publisher\chatgpt_query_runner\one_shot\f1_browser_creative_queries.json'
$StateFile = Join-Path $Root 'publisher\chatgpt_query_runner\f1_daily_test_state.local.json'
$LastRunFile = Join-Path $Root 'publisher\chatgpt_query_runner\f1_daily_test_last_run.local.json'
$LockFile = Join-Path $Root 'publisher\chatgpt_query_runner\f1_daily_test_runner.lock.json'
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$LogDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir ("f1-daily-creative-" + $Stamp + ".log")

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Write-Host $line
}

Set-Location $Root

if (Test-Path $LockFile) {
    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
        $started = [DateTimeOffset]::Parse([string]$lock.started_at)
        if ((([DateTimeOffset]::Now - $started).TotalMinutes) -lt 50) {
            Write-Log 'NOOP: one-shot F1 creative gia in esecuzione.'
            exit 0
        }
    } catch {}
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}

@{
    target = 'F1-SELLER-001-A'
    started_at = [DateTimeOffset]::Now.ToString('o')
} | ConvertTo-Json | Set-Content -Path $LockFile -Encoding UTF8

try {
    Write-Log 'RUN START - F1 DAILY CREATIVE ONE SHOT'

    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCmd) { throw 'Python non trovato nel PATH.' }
    $PythonExe = $PythonCmd.Source

    try {
        git fetch origin main 2>&1 | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -eq 0) {
            $dirty = git status --porcelain
            if (-not $dirty) { git pull --ff-only origin main 2>&1 | ForEach-Object { Write-Log $_ } }
        }
    } catch {
        Write-Log "Aggiornamento repository non riuscito: $($_.Exception.Message)"
    }

    if (-not (Test-Path $QueryFile)) { throw "Query file non trovato: $QueryFile" }

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
    $env:F1_STATE_FILE = $StateFile
    $env:F1_LAST_RUN_FILE = $LastRunFile

    & $StartInbox -Restart
    if ($LASTEXITCODE -ne 0) { throw 'F1 Inbox non disponibile.' }

    & $PythonExe -m publisher.chatgpt_query_runner.worker --batch-size 1 --query-file 'publisher/chatgpt_query_runner/one_shot/f1_browser_creative_queries.json'
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Log "RUN END - ciclo non completato, worker exit=$code"
        exit $code
    }

    Write-Log 'RUN END - worker completato.'
    exit 0
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}
