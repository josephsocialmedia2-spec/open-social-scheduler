param(
    [switch]$Test,
    [switch]$Manual
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Worker = Join-Path $Root 'publisher\chatgpt_query_runner\worker.py'
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$LogDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "f1-grafiche-$Stamp.log"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Write-Host $line
}

function Write-NativeOutput {
    process {
        $line = [string]$_
        Add-Content -Path $Log -Value $line -Encoding UTF8
        Write-Host $line
    }
}

Write-Log 'Avvio sistema F1 Grafiche.'
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python non trovato nel PATH.'
}

$env:F1_QUERY_BATCH_SIZE = '4'
$env:F1_INBOX_PORT = '8877'

try {
    & $StartInbox
    Write-Log 'Inbox locale disponibile su http://127.0.0.1:8877/.'
} catch {
    Write-Log "ERRORE Inbox: $($_.Exception.Message)"
    throw
}

try {
    $dirty = git status --porcelain
    if (-not $dirty) {
        git pull --ff-only origin main 2>&1 | ForEach-Object { Write-Log $_ }
    } else {
        Write-Log 'Repository con modifiche locali: salto git pull per non sovrascrivere dati.'
    }
} catch {
    Write-Log "Git pull non riuscito, continuo con la versione locale: $($_.Exception.Message)"
}

$depsOk = $true
python -c "import selenium, flask, tzdata" 2>$null
if ($LASTEXITCODE -ne 0) { $depsOk = $false }
if (-not $depsOk) {
    Write-Log 'Installazione dipendenze Python mancanti.'
    python -m pip install -r publisher\chatgpt_query_runner\requirements.txt 2>&1 | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze runner fallita.' }
    python -m pip install -r publisher\manual_asset_inbox\requirements.txt 2>&1 | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze Inbox fallita.' }
}

if ($Test) {
    Write-Log 'Modalita TEST: una sola query.'
    & python $Worker --batch-size 1 2>&1 | Write-NativeOutput
} elseif ($Manual) {
    Write-Log 'Modalita MANUALE: quattro query subito.'
    & python $Worker --batch-size 4 2>&1 | Write-NativeOutput
} else {
    Write-Log 'Modalita automatica 23:00: batch da quattro query.'
    & python $Worker --scheduled --batch-size 4 2>&1 | Write-NativeOutput
}
$WorkerExit = $LASTEXITCODE

if ($WorkerExit -eq 0) {
    Write-Log 'Produzione completata. Schermata mattutina pronta.'
} else {
    Write-Log "Produzione terminata con errore codice $WorkerExit."
    Start-Process 'http://127.0.0.1:8877/ready'
    exit $WorkerExit
}

exit 0
