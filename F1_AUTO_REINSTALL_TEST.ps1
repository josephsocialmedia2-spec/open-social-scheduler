param([switch]$SkipTest)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$RepoUrl = 'https://github.com/josephsocialmedia2-spec/open-social-scheduler.git'
$InstallRoot = Join-Path $env:USERPROFILE 'F1_Automazione'
$RepoDir = Join-Path $InstallRoot 'open-social-scheduler'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogRoot = Join-Path $InstallRoot 'logs'
$MainLog = Join-Path $LogRoot ("install-" + $Stamp + ".log")

New-Item -ItemType Directory -Force -Path $InstallRoot,$LogRoot | Out-Null

function Log([string]$Message,[string]$Color='Gray') {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $MainLog -Value $line -Encoding UTF8
    Write-Host $line -ForegroundColor $Color
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}

function Find-Git {
    $x = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($x) { return $x.Source }
    foreach ($p in @('C:\Program Files\Git\cmd\git.exe','C:\Program Files (x86)\Git\cmd\git.exe')) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Find-Python {
    $x = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($x) {
        try { & $x.Source --version *> $null; if ($LASTEXITCODE -eq 0) { return $x.Source } } catch {}
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $p = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            if ($p -and (Test-Path $p)) { return $p }
        } catch {}
    }
    $files = @()
    $files += Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe') -ErrorAction SilentlyContinue
    $files += Get-ChildItem 'C:\Program Files\Python*\python.exe' -ErrorAction SilentlyContinue
    $hit = $files | Sort-Object FullName -Descending | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    return $null
}

function Find-Chrome {
    $x = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($x) { return $x.Source }
    foreach ($p in @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

function Winget-Install([string]$Id,[string]$Label) {
    $w = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $w) { throw "$Label manca e winget non e disponibile." }
    Log "Installazione automatica $Label..." 'Yellow'
    & $w.Source install --id $Id --exact --silent --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installazione $Label fallita: exit=$LASTEXITCODE" }
    Refresh-Path
}

Log '============================================================' 'Cyan'
Log 'F1 AUTOMAZIONE - REINSTALLAZIONE PULITA + PROVA REALE' 'Cyan'
Log '============================================================' 'Cyan'

if ($env:OS -ne 'Windows_NT') { throw 'Questo programma richiede Windows.' }
if ($env:SESSIONNAME -eq 'Services') { throw 'Aprire una normale sessione desktop Windows e rilanciare.' }
Log "PC=$env:COMPUTERNAME USER=$env:USERNAME SESSION=$env:SESSIONNAME"

$Git = Find-Git
if (-not $Git) { Winget-Install 'Git.Git' 'Git'; $Git = Find-Git }
if (-not $Git) { throw 'Git non disponibile.' }
Log "Git OK: $Git" 'Green'

$Python = Find-Python
if (-not $Python) { Winget-Install 'Python.Python.3.12' 'Python 3.12'; $Python = Find-Python }
if (-not $Python) { throw 'Python non disponibile.' }
Log "Python OK: $Python" 'Green'

$Chrome = Find-Chrome
if (-not $Chrome) { Winget-Install 'Google.Chrome' 'Google Chrome'; $Chrome = Find-Chrome }
if (-not $Chrome) { throw 'Google Chrome non disponibile.' }
Log "Chrome OK: $Chrome" 'Green'

if (Test-Path $RepoDir) {
    $backup = Join-Path $InstallRoot ("open-social-scheduler-backup-" + $Stamp)
    Log "Sposto la precedente installazione in: $backup" 'Yellow'
    Move-Item $RepoDir $backup
}

Log 'Scarico da zero open-social-scheduler / main...' 'Cyan'
& $Git clone --depth 1 --branch main $RepoUrl $RepoDir 2>&1 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $RepoDir '.git'))) { throw 'Download GitHub fallito.' }

Set-Location $RepoDir
Log 'Installazione dipendenze Python...' 'Cyan'
foreach ($req in @(
    'publisher\chatgpt_query_runner\requirements.txt',
    'publisher\manual_asset_inbox\requirements.txt',
    'publisher\requirements.txt'
)) {
    if (-not (Test-Path $req)) { throw "File dipendenze mancante: $req" }
    & $Python -m pip install --disable-pip-version-check -r $req 2>&1 | ForEach-Object { Log "$_" }
    if ($LASTEXITCODE -ne 0) { throw "Dipendenze fallite: $req" }
}

& $Python -c "import pyautogui,pyperclip,pygetwindow,uiautomation,PIL,flask,requests,qrcode; print('F1_PYTHON_DEPS_OK')" 2>&1 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0) { throw 'Controllo moduli Python fallito.' }

Remove-Item (Join-Path $RepoDir 'publisher\chatgpt_query_runner\f1_daily_test_runner.lock.json') -Force -ErrorAction SilentlyContinue

$Desktop = [Environment]::GetFolderPath('Desktop')
$DeskBat = Join-Path $Desktop 'F1 - AVVIA ORA E PUBBLICA.bat'
$Target = Join-Path $RepoDir 'publisher\f1_graphics_automation\AVVIA_F1_ORA_E_PUBBLICA.bat'
$txt = "@echo off`r`ncd /d `"$RepoDir`"`r`ncall `"$Target`"`r`n"
[IO.File]::WriteAllText($DeskBat,$txt,(New-Object Text.UTF8Encoding($false)))
Log "Creato pulsante Desktop: $DeskBat" 'Green'

[IO.File]::WriteAllText((Join-Path $InstallRoot 'F1_ULTIMA_INSTALLAZIONE.txt'),$RepoDir + [Environment]::NewLine,(New-Object Text.UTF8Encoding($false)))

if ($SkipTest) {
    Log 'Installazione completata. Test saltato.' 'Green'
    exit 0
}

$TestScript = Join-Path $RepoDir 'publisher\f1_graphics_automation\RUN_F1_DAILY_CREATIVE_TEST.ps1'
if (-not (Test-Path $TestScript)) { throw 'RUN_F1_DAILY_CREATIVE_TEST.ps1 mancante.' }

Log 'PROVA REALE: GENERAZIONE -> QA -> BRAND -> PUBBLICAZIONE -> VERIFICA' 'Magenta'
Log 'Non usare mouse o tastiera mentre il browser automatico lavora.' 'Yellow'

$TestOut = Join-Path $LogRoot ("test-" + $Stamp + "-stdout.log")
$TestErr = Join-Path $LogRoot ("test-" + $Stamp + "-stderr.log")
$p = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $TestScript + '"')) -WorkingDirectory $RepoDir -Wait -PassThru -NoNewWindow -RedirectStandardOutput $TestOut -RedirectStandardError $TestErr

if (Test-Path $TestOut) { Get-Content $TestOut | ForEach-Object { Log "$_" } }
if (Test-Path $TestErr) { Get-Content $TestErr | ForEach-Object { Log "ERR $_" 'Red' } }

if ($p.ExitCode -ne 0) {
    Log "PROVA NON COMPLETATA. exit=$($p.ExitCode)" 'Red'
    Log "Log: $LogRoot" 'Yellow'
    Start-Process explorer.exe $LogRoot
    exit $p.ExitCode
}

Log 'PROVA TERMINATA SENZA ERRORI DEL WORKER.' 'Green'
Log 'Il ciclo deve risultare PUBLISHED_VERIFIED per essere considerato pubblicato.' 'Green'
Log "Installazione attiva: $RepoDir" 'Green'
exit 0
