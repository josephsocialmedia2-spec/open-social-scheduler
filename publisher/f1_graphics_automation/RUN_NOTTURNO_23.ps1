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
$PyOut = Join-Path $LogDir "worker-$Stamp-out.log"
$PyErr = Join-Path $LogDir "worker-$Stamp-err.log"

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

Write-Log 'Avvio sistema F1 Grafiche.'
Set-Location $Root

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    throw 'Python non trovato nel PATH.'
}
$PythonExe = $PythonCmd.Source

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
    python -m pip install -r publisher\chatgpt_query_runner\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze runner fallita.' }
    python -m pip install -r publisher\manual_asset_inbox\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze Inbox fallita.' }
}

Remove-Item $PyOut,$PyErr -Force -ErrorAction SilentlyContinue

if ($Test) {
    Write-Log 'Modalita TEST: una sola query.'
    $WorkerArgs = @($Worker, '--batch-size', '1')
} elseif ($Manual) {
    Write-Log 'Modalita MANUALE: batch da quattro query.'
    $WorkerArgs = @($Worker, '--batch-size', '4')
} else {
    Write-Log 'Modalita automatica 23:00: batch da quattro query.'
    $WorkerArgs = @($Worker, '--scheduled', '--batch-size', '4')
}

$QuotedArgs = $WorkerArgs | ForEach-Object {
    if ($_ -match '\s') { '"' + ($_ -replace '"','\"') + '"' } else { $_ }
}

$Process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList $QuotedArgs `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $PyOut `
    -RedirectStandardError $PyErr `
    -NoNewWindow `
    -Wait `
    -PassThru

Show-WorkerLogs
$WorkerExit = $Process.ExitCode

if ($WorkerExit -eq 0) {
    Write-Log 'Produzione completata. Schermata mattutina pronta.'
    exit 0
}

Write-Log "Produzione terminata con errore codice $WorkerExit."
Write-Host ''
Write-Host 'ERRORE COMPLETO DEL WORKER:' -ForegroundColor Yellow
if (Test-Path $PyErr) {
    Get-Content $PyErr -ErrorAction SilentlyContinue | Select-Object -Last 80 | ForEach-Object {
        Write-Host $_ -ForegroundColor Red
    }
}
Write-Host ''
Write-Host "Log: $Log" -ForegroundColor Yellow
Start-Process 'http://127.0.0.1:8877/ready'
exit $WorkerExit
