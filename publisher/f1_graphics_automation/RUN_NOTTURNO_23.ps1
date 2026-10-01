param(
    [switch]$Test,
    [switch]$Test4,
    [switch]$Manual
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
Set-Location $Root

Write-Host 'F1 MANUAL PUBLISH ONLY' -ForegroundColor Green
Write-Host 'Il vecchio ciclo grafico notturno e stato ritirato.' -ForegroundColor Yellow
Write-Host 'Nessuna AI, browser, prompt, render o rigenerazione verra avviata.' -ForegroundColor Cyan

& $StartInbox -Restart
if ($LASTEXITCODE -ne 0) { throw 'F1 Pubblicatore Manuale non disponibile.' }

$Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 4
if (-not $Health.ok -or $Health.mode -ne 'manual-publish-only' -or $Health.ai_image_generation -ne $false) {
    throw 'F1 Pubblicatore Manuale non in modalita manual-publish-only.'
}

Write-Host 'Apri http://127.0.0.1:8877/ e carica la grafica definitiva.' -ForegroundColor White
exit 0
