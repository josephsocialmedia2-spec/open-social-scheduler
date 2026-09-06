param(
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Server = Join-Path $Root 'publisher\manual_asset_inbox\server.py'
$Port = 8877
$LogDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$StdOutLog = Join-Path $LogDir 'inbox-stdout.log'
$StdErrLog = Join-Path $LogDir 'inbox-stderr.log'

function Test-Port {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(700)) { $client.Close(); return $false }
        $client.EndConnect($async); $client.Close(); return $true
    } catch { return $false }
}

function Get-F1Health {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    } catch { return $null }
}

function Stop-PortProcess {
    param([int]$Port)
    $pidToStop = $null
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($conn) { $pidToStop = $conn.OwningProcess }
    } catch {
        try {
            $line = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING\s+(\d+)$" | Select-Object -First 1
            if ($line -and $line.Matches.Count) { $pidToStop = [int]$line.Matches[0].Groups[1].Value }
        } catch {}
    }
    if ($pidToStop) {
        Stop-Process -Id $pidToStop -Force -ErrorAction Stop
        for ($i=0; $i -lt 20; $i++) {
            if (-not (Test-Port -Port $Port)) { return }
            Start-Sleep -Milliseconds 250
        }
        throw "Il processo sulla porta $Port non si e arrestato."
    }
    throw "Impossibile determinare il processo in ascolto sulla porta $Port."
}

if (Test-Port -Port $Port) {
    $health = Get-F1Health
    $isF1 = ($health -and $health.ok -eq $true -and $health.service -eq 'f1-manual-asset-inbox')
    if (-not $isF1) {
        throw 'La porta 8877 e occupata da un altro programma. F1 Inbox non verra avviata sulla porta sbagliata.'
    }
    if (-not $Restart) {
        Write-Host 'F1 Inbox gia attiva su http://127.0.0.1:8877/' -ForegroundColor Green
        exit 0
    }
    Write-Host 'Riavvio F1 Inbox per caricare la versione aggiornata...' -ForegroundColor Yellow
    Stop-PortProcess -Port $Port
}

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { throw 'Python non trovato nel PATH.' }
$PythonExe = $PythonCmd.Source
if (-not (Test-Path $Server)) { throw "Server Inbox non trovato: $Server" }

$env:F1_INBOX_PORT = "$Port"
Remove-Item $StdOutLog,$StdErrLog -Force -ErrorAction SilentlyContinue
$Process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @('"' + $Server + '"') `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -WindowStyle Hidden `
    -PassThru

for ($i = 0; $i -lt 40; $i++) {
    $health = Get-F1Health
    if ($health -and $health.ok -eq $true -and $health.service -eq 'f1-manual-asset-inbox') {
        Write-Host 'F1 Inbox avviata: http://127.0.0.1:8877/' -ForegroundColor Green
        exit 0
    }
    if ($Process.HasExited) { break }
    Start-Sleep -Milliseconds 500
}

$details = ''
if (Test-Path $StdErrLog) { $details = (Get-Content $StdErrLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
if (-not $details -and (Test-Path $StdOutLog)) { $details = (Get-Content $StdOutLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
if (-not $details) { $details = 'Nessun dettaglio disponibile. Controllare publisher\f1_graphics_automation\logs.' }
throw "F1 Inbox non si e avviata sulla porta 8877.`n$details"
