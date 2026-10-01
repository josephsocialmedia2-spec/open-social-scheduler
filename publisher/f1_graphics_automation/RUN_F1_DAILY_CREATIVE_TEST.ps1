param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
Set-Location $Root

Write-Host 'F1 MANUAL PUBLISH ONLY' -ForegroundColor Green
Write-Host 'Il test di generazione creativa e archiviato: nessuna immagine viene generata.' -ForegroundColor Yellow

& $StartInbox -Restart
if ($LASTEXITCODE -ne 0) { throw 'F1 Pubblicatore Manuale non disponibile.' }

$Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 4
if (-not $Health.ok -or $Health.mode -ne 'manual-publish-only' -or $Health.ai_image_generation -ne $false) {
    throw 'Contratto manual-publish-only non verificato.'
}

Write-Host 'MANUAL_PUBLISH_ONLY_OK - PIXEL IN -> PIXEL OUT' -ForegroundColor Cyan
exit 0
