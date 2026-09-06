$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$NightScript = Join-Path $PSScriptRoot 'RUN_NOTTURNO_23.ps1'
$InboxScript = Join-Path $PSScriptRoot 'START_INBOX.ps1'
$OpenBat = Join-Path $PSScriptRoot 'APRI_RACCOLTA_GRAFICHE.bat'
$ManualBat = Join-Path $PSScriptRoot 'AVVIA_F1_GRAFICHE_ORA.bat'
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
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze runner fallita.' }
python -m pip install -r publisher\manual_asset_inbox\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze Inbox fallita.' }

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
    -Description 'Mantiene disponibile la pagina locale F1 Raccolta Grafiche sulla porta 8877.' `
    -Action $InboxAction `
    -Trigger $InboxTrigger `
    -Principal $Principal `
    -Settings $InboxSettings `
    -Force | Out-Null

& $InboxScript
if ($LASTEXITCODE -ne 0) { throw 'F1 Inbox non avviata.' }

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shell = New-Object -ComObject WScript.Shell

# Elimina i vecchi collegamenti che potevano puntare solo alla Inbox.
Remove-Item (Join-Path $Desktop 'F1 GRAFICHE.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Desktop 'F1 - Raccolta Grafiche.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Desktop 'F1 - Prova Automazione Grafiche.lnk') -Force -ErrorAction SilentlyContinue

# Icona principale: avvia davvero Chrome + GPT + 4 query.
$MainShortcut = $Shell.CreateShortcut((Join-Path $Desktop 'F1 GRAFICHE.lnk'))
$MainShortcut.TargetPath = $ManualBat
$MainShortcut.WorkingDirectory = $Root
$MainShortcut.Description = 'Avvia produzione F1: Chrome, GPT e 4 query'
$MainShortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,167"
$MainShortcut.Save()

# Icona secondaria: solo caricamento immagini.
$InboxShortcut = $Shell.CreateShortcut((Join-Path $Desktop 'F1 - Raccolta Grafiche.lnk'))
$InboxShortcut.TargetPath = $OpenBat
$InboxShortcut.WorkingDirectory = $Root
$InboxShortcut.Description = 'Apri F1 Raccolta Grafiche'
$InboxShortcut.Save()

# Test singola query.
$TestShortcut = $Shell.CreateShortcut((Join-Path $Desktop 'F1 - Prova 1 Query.lnk'))
$TestShortcut.TargetPath = $TestBat
$TestShortcut.WorkingDirectory = $Root
$TestShortcut.Description = 'Esegue una query di prova immediata'
$TestShortcut.Save()

Write-Host ''
Write-Host 'INSTALLAZIONE COMPLETATA.' -ForegroundColor Green
Write-Host 'F1 GRAFICHE -> avvia subito Chrome + GPT + 4 query' -ForegroundColor White
Write-Host 'F1 - Raccolta Grafiche -> apre solo la pagina di caricamento' -ForegroundColor White
Write-Host 'F1_Grafiche_23 -> partenza automatica ogni giorno alle 23:00' -ForegroundColor White
Write-Host 'Pagina raccolta: http://127.0.0.1:8877/' -ForegroundColor Cyan
Write-Host 'Schermata mattutina: http://127.0.0.1:8877/ready' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Per usare il profilo Chrome già autenticato, Chrome deve essere chiuso quando parte Selenium.' -ForegroundColor Yellow
Write-Host ''
Read-Host 'Premi INVIO per chiudere'
