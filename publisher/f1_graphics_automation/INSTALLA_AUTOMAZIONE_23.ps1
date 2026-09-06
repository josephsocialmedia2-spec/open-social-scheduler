$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$NightScript = Join-Path $PSScriptRoot 'RUN_NOTTURNO_23.ps1'
$InboxScript = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$OpenBat = Join-Path $PSScriptRoot 'APRI_RACCOLTA_GRAFICHE.bat'
$TestBat = Join-Path $PSScriptRoot 'PROVA_ORA.bat'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host ''
Write-Host 'F1 IMMOBILIARE - INSTALLAZIONE AUTOMAZIONE GRAFICHE ORE 23:00' -ForegroundColor Green
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python non trovato. Installa Python 3.12+ e seleziona Add Python to PATH.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git non trovato. Installa Git for Windows.'
}

Set-Location $Root
Write-Host 'Installazione dipendenze Python...'
python -m pip install -r publisher\chatgpt_query_runner\requirements.txt
python -m pip install -r publisher\manual_asset_inbox\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze fallita.' }

$PsExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$NightArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$NightScript`""
$InboxArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$InboxScript`""

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

Register-ScheduledTask `
    -TaskName 'F1_Grafiche_23' `
    -Description 'Alle 23:00 apre Chrome, Generatore Grafica F1, invia le query una alla volta e prepara la schermata mattutina.' `
    -Action $NightAction `
    -Trigger $NightTrigger `
    -Principal $Principal `
    -Settings $NightSettings `
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
    -Description 'Mantiene disponibile la pagina locale F1 Raccolta Grafiche.' `
    -Action $InboxAction `
    -Trigger $InboxTrigger `
    -Principal $Principal `
    -Settings $InboxSettings `
    -Force | Out-Null

# Avvia subito la Inbox.
& $InboxScript

# Collegamenti sul desktop.
$Desktop = [Environment]::GetFolderPath('Desktop')
$Shell = New-Object -ComObject WScript.Shell

$Shortcut = $Shell.CreateShortcut((Join-Path $Desktop 'F1 - Raccolta Grafiche.lnk'))
$Shortcut.TargetPath = $OpenBat
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = 'Apri F1 Raccolta Grafiche'
$Shortcut.Save()

$TestShortcut = $Shell.CreateShortcut((Join-Path $Desktop 'F1 - Prova Automazione Grafiche.lnk'))
$TestShortcut.TargetPath = $TestBat
$TestShortcut.WorkingDirectory = $Root
$TestShortcut.Description = 'Esegue una query di prova immediata'
$TestShortcut.Save()

Write-Host ''
Write-Host 'INSTALLAZIONE COMPLETATA.' -ForegroundColor Green
Write-Host 'Attività: F1_Grafiche_23 -> ogni giorno alle 23:00' -ForegroundColor White
Write-Host 'Attività: F1_Inbox_Logon -> avvio della pagina locale a ogni accesso Windows' -ForegroundColor White
Write-Host 'Pagina raccolta: http://127.0.0.1:8765/' -ForegroundColor Cyan
Write-Host 'Schermata mattutina: http://127.0.0.1:8765/ready' -ForegroundColor Cyan
Write-Host ''
Write-Host 'REQUISITO: Windows deve avere una sessione utente aperta. Il PC può essere in sospensione: WakeToRun è attivo.' -ForegroundColor Yellow
Write-Host 'Per usare il profilo Chrome già autenticato, alle 23:00 Chrome non deve bloccare lo stesso profilo usato dall automazione.' -ForegroundColor Yellow
Write-Host ''
Read-Host 'Premi INVIO per chiudere'
