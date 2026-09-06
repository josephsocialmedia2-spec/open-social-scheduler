param(
    [switch]$Test
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

Write-Log 'Avvio sistema F1 Grafiche.'
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python non trovato nel PATH.'
}

try {
    & $StartInbox
    Write-Log 'Inbox locale disponibile su http://127.0.0.1:8765/.'
} catch {
    Write-Log "ERRORE Inbox: $($_.Exception.Message)"
    throw
}

# Aggiorna il codice solo se il repository locale è pulito.
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

# Verifica dipendenze e le installa solo se mancano.
$depsOk = $true
try { python -c "import selenium, flask" | Out-Null } catch { $depsOk = $false }
if ($LASTEXITCODE -ne 0) { $depsOk = $false }
if (-not $depsOk) {
    Write-Log 'Installazione dipendenze Python mancanti.'
    python -m pip install -r publisher\chatgpt_query_runner\requirements.txt 2>&1 | ForEach-Object { Write-Log $_ }
    python -m pip install -r publisher\manual_asset_inbox\requirements.txt 2>&1 | ForEach-Object { Write-Log $_ }
}

$env:F1_QUERY_BATCH_SIZE = '4'
$env:F1_INBOX_PORT = '8765'

if ($Test) {
    Write-Log 'Modalità TEST: una sola query.'
    & python $Worker --batch-size 1 2>&1 | Tee-Object -FilePath $Log -Append
} else {
    Write-Log 'Modalità automatica 23:00: batch da quattro query.'
    & python $Worker --scheduled --batch-size 4 2>&1 | Tee-Object -FilePath $Log -Append
}
$WorkerExit = $LASTEXITCODE

if ($WorkerExit -eq 0) {
    Write-Log 'Produzione completata. Schermata mattutina pronta.'
} else {
    Write-Log "Produzione terminata con errore codice $WorkerExit."
    Start-Process 'http://127.0.0.1:8765/ready'
    exit $WorkerExit
}

exit 0
