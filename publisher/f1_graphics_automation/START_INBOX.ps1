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
        if (-not $async.AsyncWaitHandle.WaitOne(700)) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-F1Inbox {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        return ($health.ok -eq $true -and $health.service -eq 'f1-manual-asset-inbox')
    } catch {
        return $false
    }
}

if (Test-Port -Port $Port) {
    if (Test-F1Inbox) {
        Write-Host 'F1 Inbox gia attiva su http://127.0.0.1:8877/' -ForegroundColor Green
        exit 0
    }
    throw 'La porta 8877 e occupata da un altro programma. F1 Inbox non verra avviata sulla porta sbagliata.'
}

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    throw 'Python non trovato nel PATH.'
}
$PythonExe = $PythonCmd.Source

if (-not (Test-Path $Server)) {
    throw "Server Inbox non trovato: $Server"
}

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
    if (Test-F1Inbox) {
        Write-Host 'F1 Inbox avviata: http://127.0.0.1:8877/' -ForegroundColor Green
        exit 0
    }
    if ($Process.HasExited) {
        break
    }
    Start-Sleep -Milliseconds 500
}

$details = ''
if (Test-Path $StdErrLog) {
    $details = (Get-Content $StdErrLog -Tail 30 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
}
if (-not $details -and (Test-Path $StdOutLog)) {
    $details = (Get-Content $StdOutLog -Tail 30 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
}
if (-not $details) {
    $details = 'Nessun dettaglio disponibile. Controllare i log in publisher\f1_graphics_automation\logs.'
}

throw "F1 Inbox non si e avviata sulla porta 8877.`n$details"
