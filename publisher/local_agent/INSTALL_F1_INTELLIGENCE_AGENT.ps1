param(
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$Agent = Join-Path $RepoRoot "publisher\local_agent\f1_pc_agent.py"
if (-not (Test-Path $Agent)) { throw "Agent non trovato: $Agent" }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python non trovato. Installa Python 3.12 e riesegui questo script."
}
if (-not $env:SUPABASE_SERVICE_ROLE_KEY) {
  throw "SUPABASE_SERVICE_ROLE_KEY non configurata nelle variabili ambiente dell'operatore. Non viene salvata nel repository."
}
if (-not $env:SUPABASE_URL) {
  [Environment]::SetEnvironmentVariable("SUPABASE_URL","https://nqnmlsmeiynxbdojeyjt.supabase.co","User")
  $env:SUPABASE_URL="https://nqnmlsmeiynxbdojeyjt.supabase.co"
}
if (-not $env:F1_LOCAL_ROOT) {
  [Environment]::SetEnvironmentVariable("F1_LOCAL_ROOT","C:\F1Social\Clients","User")
  $env:F1_LOCAL_ROOT="C:\F1Social\Clients"
}

python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "FFmpeg non trovato: provo installazione con winget..." -ForegroundColor Yellow
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  } else {
    Write-Warning "winget non disponibile. L'import automatico funzionerà; la registrazione video resterà disattivata finché FFmpeg non sarà installato."
  }
}

$TaskName="F1 Social Intelligence Local Agent"
$Python=(Get-Command python).Source
$Action=New-ScheduledTaskAction -Execute $Python -Argument ('"' + $Agent + '"') -WorkingDirectory $RepoRoot
$Trigger=New-ScheduledTaskTrigger -AtLogOn
$Settings=New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "F1 Social Intelligence: cartelle cliente, upload automatico e registrazione consensuale visibile." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "F1 Social Intelligence Local Agent installato e avviato." -ForegroundColor Green
Write-Host "Cartella centrale: C:\F1Social\Clients" -ForegroundColor Cyan
Write-Host "I clienti devono usare esclusivamente la propria cartella INBOX." -ForegroundColor Cyan
