param(
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$Agent = Join-Path $RepoRoot "publisher\local_agent\f1_pc_agent.py"
$F1InformaAgent = Join-Path $RepoRoot "publisher\local_agent\f1_informa_autopilot.py"
if (-not (Test-Path $Agent)) { throw "Agent non trovato: $Agent" }
if (-not (Test-Path $F1InformaAgent)) { throw "F1 INFORMA Autopilot non trovato: $F1InformaAgent" }

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
if (-not $env:F1_BROWSER_ROOT) {
  [Environment]::SetEnvironmentVariable("F1_BROWSER_ROOT","C:\F1Social\BrowserProfiles","User")
  $env:F1_BROWSER_ROOT="C:\F1Social\BrowserProfiles"
}
if (-not $env:F1_CHATGPT_GOOGLE_EMAIL) {
  [Environment]::SetEnvironmentVariable("F1_CHATGPT_GOOGLE_EMAIL","joseph.socialmedia2@gmail.com","User")
  $env:F1_CHATGPT_GOOGLE_EMAIL="joseph.socialmedia2@gmail.com"
}

$ChromeCandidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$Chrome = $ChromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $Chrome) {
  throw "Google Chrome non trovato. F1 INFORMA usa la sessione Chrome locale gia autenticata."
}

python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
python $F1InformaAgent --self-test

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "FFmpeg non trovato: provo installazione con winget..." -ForegroundColor Yellow
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  } else {
    Write-Warning "winget non disponibile. L'import automatico funzionera; la registrazione video restera disattivata finche FFmpeg non sara installato."
  }
}

$Python=(Get-Command python).Source
$Trigger=New-ScheduledTaskTrigger -AtLogOn
$Settings=New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$TaskName="F1 Social Intelligence Local Agent"
$Action=New-ScheduledTaskAction -Execute $Python -Argument ('"' + $Agent + '"') -WorkingDirectory $RepoRoot
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "F1 Social Intelligence: cartelle cliente e upload automatico." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$F1InformaTask="F1 INFORMA ChatGPT Autopilot"
$F1InformaAction=New-ScheduledTaskAction -Execute $Python -Argument ('"' + $F1InformaAgent + '"') -WorkingDirectory $RepoRoot
Register-ScheduledTask -TaskName $F1InformaTask -Action $F1InformaAction -Trigger $Trigger -Settings $Settings -Description "F1 INFORMA: caption -> ChatGPT -> 10 grafiche -> Content Hub -> pubblicazione." -Force | Out-Null
Start-ScheduledTask -TaskName $F1InformaTask

Write-Host "F1 Social Intelligence Local Agent installato e avviato." -ForegroundColor Green
Write-Host "F1 INFORMA ChatGPT Autopilot installato e avviato." -ForegroundColor Green
Write-Host "Sessione ChatGPT attesa: joseph.socialmedia2@gmail.com" -ForegroundColor Cyan
Write-Host "Profili browser: C:\F1Social\BrowserProfiles" -ForegroundColor Cyan
Write-Host "Da questo momento i job F1 INFORMA vengono elaborati automaticamente." -ForegroundColor Cyan
