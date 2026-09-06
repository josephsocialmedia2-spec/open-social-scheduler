$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Server = Join-Path $Root 'publisher\manual_asset_inbox\server.py'
$Port = 8765

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

if (Test-Port -Port $Port) {
    exit 0
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python non trovato nel PATH.'
}

$env:F1_INBOX_PORT = "$Port"
Start-Process -FilePath 'python' -ArgumentList @($Server) -WorkingDirectory $Root -WindowStyle Hidden

for ($i = 0; $i -lt 30; $i++) {
    if (Test-Port -Port $Port) { exit 0 }
    Start-Sleep -Milliseconds 500
}

throw 'F1 Inbox non si è avviata sulla porta 8765.'
