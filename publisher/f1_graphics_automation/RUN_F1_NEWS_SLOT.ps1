param(
    [ValidateSet('auto','midday','evening','immediate')]
    [string]$Slot = 'auto'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StartInbox = Join-Path $PSScriptRoot 'START_INBOX.ps1'
Set-Location $Root

Write-Host "F1 MANUAL PUBLISH ONLY - News slot $Slot archiviato." -ForegroundColor Green
Write-Host 'Le notizie non possono piu generare automaticamente una grafica F1.' -ForegroundColor Yellow
& $StartInbox
if ($LASTEXITCODE -ne 0) { throw 'F1 Pubblicatore Manuale non disponibile.' }
exit 0
