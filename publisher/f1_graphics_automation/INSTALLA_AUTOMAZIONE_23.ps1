param(
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$InboxScript = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$OpenBat = Join-Path $PSScriptRoot 'APRI_RACCOLTA_GRAFICHE.bat'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host ''
Write-Host 'F1 IMMOBILIARE - INSTALLAZIONE PUBBLICATORE MANUALE' -ForegroundColor Green
Write-Host 'Le grafiche vengono create dall operatore. Nessuna AI grafica verra avviata.' -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python non trovato.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git non trovato.' }
foreach ($required in @($InboxScript,$OpenBat)) {
    if (-not (Test-Path $required)) { throw "File necessario non trovato: $required" }
}

Set-Location $Root
$dirty = git status --porcelain
if (-not $dirty) {
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Aggiornamento Git fallito.' }
} else {
    Write-Host 'Repository con modifiche locali: aggiornamento Git saltato per sicurezza.' -ForegroundColor Yellow
}

python -m pip install -r publisher\manual_asset_inbox\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze pannello manuale fallita.' }

$LegacyTasks = @('F1_Grafiche_23','F1_News_ValleSusa','F1_News_GitHub_Poller')
foreach ($TaskName in $LegacyTasks) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Rimosso task legacy: $TaskName" -ForegroundColor Yellow
    }
}

$PsExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$InboxArgs = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $InboxScript + '"'
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$InboxAction = New-ScheduledTaskAction -Execute $PsExe -Argument $InboxArgs -WorkingDirectory $Root
$InboxTrigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$InboxSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'F1_Inbox_Logon' -Description 'Avvia soltanto il pannello F1 manual publish-only su 127.0.0.1:8877.' -Action $InboxAction -Trigger $InboxTrigger -Principal $Principal -Settings $InboxSettings -Force | Out-Null

& $InboxScript -Restart
if ($LASTEXITCODE -ne 0) { throw 'F1 Pubblicatore Manuale non avviato.' }

$Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 4
if (-not $Health.ok -or $Health.service -ne 'f1-manual-asset-inbox' -or $Health.mode -ne 'manual-publish-only' -or $Health.ai_image_generation -ne $false) {
    throw 'Health check F1 manual publish-only fallito.'
}

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shell = New-Object -ComObject WScript.Shell
foreach ($oldName in @('F1 AUTOPUBLISHER.lnk','F1 GRAFICHE.lnk','F1 - Raccolta Grafiche.lnk','F1 - Prova Automazione Grafiche.lnk','F1 - Prova 1 Query.lnk','F1 - Prova 4 Query.lnk','F1 PUBBLICA GRAFICHE.lnk')) {
    Remove-Item (Join-Path $Desktop $oldName) -Force -ErrorAction SilentlyContinue
}

$Link = $Shell.CreateShortcut((Join-Path $Desktop 'F1 PUBBLICA GRAFICHE.lnk'))
$Link.TargetPath = $OpenBat
$Link.WorkingDirectory = $Root
$Link.Description = 'Carica la grafica definitiva F1, inserisci caption/social/data e pubblica.'
$Link.IconLocation = "$env:SystemRoot\System32\shell32.dll,167"
$Link.Save()

if (-not (Test-Path (Join-Path $Desktop 'F1 PUBBLICA GRAFICHE.lnk'))) { throw 'Collegamento Desktop non creato.' }

Write-Host ''
Write-Host 'INSTALLAZIONE MANUALE VERIFICATA.' -ForegroundColor Green
Write-Host 'Task grafici/notizie AI legacy: RIMOSSI.' -ForegroundColor White
Write-Host 'Task mantenuto: F1_Inbox_Logon.' -ForegroundColor White
Write-Host 'Pannello: http://127.0.0.1:8877/' -ForegroundColor Cyan
Write-Host 'Regola: PIXEL IN -> PIXEL OUT.' -ForegroundColor Cyan
if (-not $NonInteractive) { Read-Host 'Premi INVIO per chiudere' | Out-Null }
