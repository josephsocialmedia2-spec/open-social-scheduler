param(
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$NightScript = Join-Path $PSScriptRoot 'RUN_NOTTURNO_23.ps1'
$NewsScript = Join-Path $PSScriptRoot 'RUN_F1_NEWS_SLOT.ps1'
$InboxScript = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$EnsurePoller = Join-Path $PSScriptRoot 'ENSURE_F1_NEWS_POLLER.ps1'
$OpenBat = Join-Path $PSScriptRoot 'APRI_RACCOLTA_GRAFICHE.bat'
$ManualBat = Join-Path $PSScriptRoot 'AVVIA_F1_GRAFICHE_ORA.bat'
$Test1Bat = Join-Path $PSScriptRoot 'PROVA_ORA.bat'
$Test4Bat = Join-Path $PSScriptRoot 'PROVA_4_QUERY.bat'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host ''
Write-Host 'F1 IMMOBILIARE - INSTALLAZIONE AUTOPUBLISHER + F1 NEWS VALLE DI SUSA' -ForegroundColor Green
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python non trovato. Installa Python 3.12+ con Add Python to PATH.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git non trovato. Installa Git for Windows.' }
foreach ($required in @($NightScript,$NewsScript,$InboxScript,$EnsurePoller,$OpenBat,$ManualBat,$Test1Bat,$Test4Bat)) {
    if (-not (Test-Path $required)) { throw "File necessario non trovato: $required" }
}

Set-Location $Root
Write-Host 'Aggiornamento repository...'
$dirty = git status --porcelain
if (-not $dirty) {
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Aggiornamento Git fallito.' }
} else {
    Write-Host 'Repository con modifiche locali: aggiornamento Git saltato per sicurezza.' -ForegroundColor Yellow
}

Write-Host 'Installazione dipendenze Python...'
python -m pip install -r publisher\chatgpt_query_runner\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze runner fallita.' }
python -m pip install -r publisher\manual_asset_inbox\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze Raccolta fallita.' }

$PsExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$NightArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$NightScript`""
$InboxArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$InboxScript`""
$NewsArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$NewsScript`" -Slot auto"

$NightAction = New-ScheduledTaskAction -Execute $PsExe -Argument $NightArgs -WorkingDirectory $Root
$NightTrigger = New-ScheduledTaskTrigger -Daily -At 23:00
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$NightSettings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -MultipleInstances IgnoreNew

Write-Host 'Registrazione F1_Grafiche_23...'
Register-ScheduledTask `
    -TaskName 'F1_Grafiche_23' `
    -Description 'F1 Autopublisher: alle 23:00 recupera fino a 4 comunicati rimasti incompleti usando il Chrome normale dell utente.' `
    -Action $NightAction `
    -Trigger $NightTrigger `
    -Principal $Principal `
    -Settings $NightSettings `
    -Force | Out-Null

$NewsAction = New-ScheduledTaskAction -Execute $PsExe -Argument $NewsArgs -WorkingDirectory $Root
$NewsTriggers = @(
    (New-ScheduledTaskTrigger -Daily -At 11:30),
    (New-ScheduledTaskTrigger -Daily -At 19:30)
)
$NewsSettings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45) `
    -MultipleInstances IgnoreNew

Write-Host 'Registrazione F1_News_ValleSusa alle 11:30 e 19:30...'
Register-ScheduledTask `
    -TaskName 'F1_News_ValleSusa' `
    -Description 'F1 News Valle di Susa: GitHub prepara notizia/caption/prompt; il PC esegue il GPT browser, scarica, brandizza, pubblica e verifica.' `
    -Action $NewsAction `
    -Trigger $NewsTriggers `
    -Principal $Principal `
    -Settings $NewsSettings `
    -Force | Out-Null

$InboxAction = New-ScheduledTaskAction -Execute $PsExe -Argument $InboxArgs -WorkingDirectory $Root
$InboxTrigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$InboxSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName 'F1_Inbox_Logon' `
    -Description 'Mantiene disponibile F1 Autopublisher su 127.0.0.1:8877.' `
    -Action $InboxAction `
    -Trigger $InboxTrigger `
    -Principal $Principal `
    -Settings $InboxSettings `
    -Force | Out-Null

# Verifica effettiva del task notturno: esistenza, comando, working directory e orario.
$InstalledNight = Get-ScheduledTask -TaskName 'F1_Grafiche_23' -ErrorAction Stop
$InstalledAction = $InstalledNight.Actions | Select-Object -First 1
$InstalledTrigger = $InstalledNight.Triggers | Select-Object -First 1
if (-not $InstalledAction) { throw 'Task F1_Grafiche_23 creato senza Action.' }
if ($InstalledAction.Execute -ne $PsExe) { throw "Task 23:00: interprete errato: $($InstalledAction.Execute)" }
if ($InstalledAction.Arguments -notlike "*$NightScript*") { throw "Task 23:00: script errato: $($InstalledAction.Arguments)" }
if ($InstalledAction.WorkingDirectory -ne $Root) { throw "Task 23:00: working directory errata: $($InstalledAction.WorkingDirectory)" }
if (-not $InstalledTrigger) { throw 'Task F1_Grafiche_23 creato senza trigger.' }
$Boundary = [DateTime]::Parse($InstalledTrigger.StartBoundary)
if ($Boundary.Hour -ne 23 -or $Boundary.Minute -ne 0) { throw "Task F1_Grafiche_23 non impostato alle 23:00: $($InstalledTrigger.StartBoundary)" }
$TaskInfo = Get-ScheduledTaskInfo -TaskName 'F1_Grafiche_23' -ErrorAction Stop

$InstalledNews = Get-ScheduledTask -TaskName 'F1_News_ValleSusa' -ErrorAction Stop
$NewsActionInstalled = $InstalledNews.Actions | Select-Object -First 1
if (-not $NewsActionInstalled) { throw 'Task F1_News_ValleSusa creato senza Action.' }
if ($NewsActionInstalled.Arguments -notlike "*$NewsScript*") { throw "Task F1_News_ValleSusa: script errato: $($NewsActionInstalled.Arguments)" }
if ($NewsActionInstalled.WorkingDirectory -ne $Root) { throw "Task F1_News_ValleSusa: working directory errata: $($NewsActionInstalled.WorkingDirectory)" }
$NewsHours = @($InstalledNews.Triggers | ForEach-Object { ([DateTime]::Parse($_.StartBoundary)).ToString('HH:mm') })
if ($NewsHours -notcontains '11:30' -or $NewsHours -notcontains '19:30') {
    throw "Task F1_News_ValleSusa non configurato nei due slot richiesti: $($NewsHours -join ', ')"
}
$NewsTaskInfo = Get-ScheduledTaskInfo -TaskName 'F1_News_ValleSusa' -ErrorAction Stop

& $EnsurePoller
$InstalledPoller = Get-ScheduledTask -TaskName 'F1_News_GitHub_Poller' -ErrorAction Stop
if (-not $InstalledPoller) { throw 'Task F1_News_GitHub_Poller non verificabile.' }

$InstalledInbox = Get-ScheduledTask -TaskName 'F1_Inbox_Logon' -ErrorAction Stop
if (-not $InstalledInbox) { throw 'Task F1_Inbox_Logon non verificabile.' }

# Ricarica il server locale con il codice appena aggiornato.
& $InboxScript -Restart
if ($LASTEXITCODE -ne 0) { throw 'F1 Raccolta non avviata.' }
$Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 4
if (-not $Health.ok -or $Health.service -ne 'f1-manual-asset-inbox') { throw 'Health check F1 Raccolta fallito.' }

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shell = New-Object -ComObject WScript.Shell
foreach ($oldName in @('F1 AUTOPUBLISHER.lnk','F1 GRAFICHE.lnk','F1 - Raccolta Grafiche.lnk','F1 - Prova Automazione Grafiche.lnk','F1 - Prova 1 Query.lnk','F1 - Prova 4 Query.lnk')) {
    Remove-Item (Join-Path $Desktop $oldName) -Force -ErrorAction SilentlyContinue
}

function New-F1Shortcut {
    param([string]$Name,[string]$Target,[string]$Description,[string]$Icon='')
    $Link = $Shell.CreateShortcut((Join-Path $Desktop $Name))
    $Link.TargetPath = $Target
    $Link.WorkingDirectory = $Root
    $Link.Description = $Description
    if ($Icon) { $Link.IconLocation = $Icon }
    $Link.Save()
    if (-not (Test-Path (Join-Path $Desktop $Name))) { throw "Collegamento Desktop non creato: $Name" }
}

New-F1Shortcut -Name 'F1 AUTOPUBLISHER.lnk' -Target $OpenBat -Description 'Inserisci il comunicato: F1 gestisce grafica, pubblicazione e verifica' -Icon "$env:SystemRoot\System32\shell32.dll,167"

Write-Host ''
Write-Host 'INSTALLAZIONE VERIFICATA.' -ForegroundColor Green
Write-Host 'Desktop: F1 AUTOPUBLISHER' -ForegroundColor White
Write-Host 'I launcher di test restano disponibili nella cartella tecnica, non sul Desktop.' -ForegroundColor DarkGray
Write-Host 'F1_Grafiche_23: ogni giorno alle 23:00 recupera comunicati incompleti, sessione Windows interattiva' -ForegroundColor White
Write-Host 'F1_News_ValleSusa: GitHub controlla la coda; alle 11:30 e 19:30 il PC esegue il GPT browser e pubblica.' -ForegroundColor White
Write-Host "Prossima esecuzione recovery 23:00: $($TaskInfo.NextRunTime)" -ForegroundColor Cyan
Write-Host "Prossima esecuzione F1 News: $($NewsTaskInfo.NextRunTime)" -ForegroundColor Cyan
Write-Host 'Autopublisher: http://127.0.0.1:8877/' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Il browser usato dal worker è il Chrome normale. Non viene creato alcun profilo Chrome dedicato.' -ForegroundColor Yellow
Write-Host ''
if (-not $NonInteractive) { Read-Host 'Premi INVIO per chiudere' | Out-Null }
