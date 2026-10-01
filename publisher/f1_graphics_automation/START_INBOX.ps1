param(
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Server = Join-Path $Root 'publisher\manual_asset_inbox\server.py'
$Port = 8877
$LogDir = Join-Path $PSScriptRoot 'logs'
$StdOutLog = Join-Path $LogDir 'inbox-stdout.log'
$StdErrLog = Join-Path $LogDir 'inbox-stderr.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-Port {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(700)) { $client.Close(); return $false }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch { return $false }
}

function Get-F1Health {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 }
    catch { return $null }
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
    if (-not $pidToStop) { throw "Impossibile determinare il processo sulla porta $Port." }
    Stop-Process -Id $pidToStop -Force -ErrorAction Stop
    for ($i=0; $i -lt 20; $i++) {
        if (-not (Test-Port -Port $Port)) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "Il processo sulla porta $Port non si e arrestato."
}

if (Test-Port -Port $Port) {
    $health = Get-F1Health
    $isF1 = (
        $health -and
        $health.ok -eq $true -and
        $health.service -eq 'f1-manual-asset-inbox' -and
        $health.mode -eq 'manual-publish-only' -and
        $health.ai_image_generation -eq $false
    )
    if (-not $isF1) { throw 'La porta 8877 e occupata da un servizio diverso dal pubblicatore manuale F1.' }
    if (-not $Restart) {
        Write-Host 'F1 Pubblicatore Manuale gia attivo su http://127.0.0.1:8877/' -ForegroundColor Green
        exit 0
    }
    Write-Host 'Riavvio F1 Pubblicatore Manuale...' -ForegroundColor Yellow
    Stop-PortProcess -Port $Port
}

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { throw 'Python non trovato nel PATH.' }
$PythonExe = $PythonCmd.Source
if (-not (Test-Path $Server)) { throw "Server manuale F1 non trovato: $Server" }

$env:F1_INBOX_PORT = "$Port"
Remove-Item $StdOutLog,$StdErrLog -Force -ErrorAction SilentlyContinue
$Process = Start-Process -FilePath $PythonExe -ArgumentList @($Server) -WorkingDirectory $Root -RedirectStandardOutput $StdOutLog -RedirectStandardError $StdErrLog -WindowStyle Hidden -PassThru

for ($i = 0; $i -lt 40; $i++) {
    $health = Get-F1Health
    if (
        $health -and
        $health.ok -eq $true -and
        $health.service -eq 'f1-manual-asset-inbox' -and
        $health.mode -eq 'manual-publish-only' -and
        $health.ai_image_generation -eq $false
    ) {
        Write-Host 'F1 Pubblicatore Manuale avviato: http://127.0.0.1:8877/' -ForegroundColor Green
        Write-Host 'AI GRAFICA: DISABILITATA. PIXEL IN -> PIXEL OUT.' -ForegroundColor Cyan
        exit 0
    }
    if ($Process.HasExited) { break }
    Start-Sleep -Milliseconds 500
}

$details = ''
if (Test-Path $StdErrLog) { $details = (Get-Content $StdErrLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
if (-not $details -and (Test-Path $StdOutLog)) { $details = (Get-Content $StdOutLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine }
if (-not $details) { $details = 'Nessun dettaglio disponibile. Controllare publisher\f1_graphics_automation\logs.' }
throw ("F1 Pubblicatore Manuale non si e avviato sulla porta 8877." + [Environment]::NewLine + $details)
