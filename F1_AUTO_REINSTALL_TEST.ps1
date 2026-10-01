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
    if ($x) { return $x.Source }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $p = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            if ($p -and (Test-Path $p)) { return $p }
        } catch {}
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
Log 'F1 - REINSTALLAZIONE PUBBLICATORE MANUALE' 'Cyan'
Log '============================================================' 'Cyan'
Log 'Nessun generatore grafico o browser AI verra installato.' 'Green'

if ($env:OS -ne 'Windows_NT') { throw 'Questo programma richiede Windows.' }

$Git = Find-Git
if (-not $Git) { Winget-Install 'Git.Git' 'Git'; $Git = Find-Git }
if (-not $Git) { throw 'Git non disponibile.' }

$Python = Find-Python
if (-not $Python) { Winget-Install 'Python.Python.3.12' 'Python 3.12'; $Python = Find-Python }
if (-not $Python) { throw 'Python non disponibile.' }

if (Test-Path $RepoDir) {
    $backup = Join-Path $InstallRoot ("open-social-scheduler-backup-" + $Stamp)
    Log "Sposto la precedente installazione in: $backup" 'Yellow'
    Move-Item $RepoDir $backup
}

Log 'Scarico open-social-scheduler / main...' 'Cyan'
& $Git clone --depth 1 --branch main $RepoUrl $RepoDir 2>&1 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $RepoDir '.git'))) { throw 'Download GitHub fallito.' }

Set-Location $RepoDir
$ManualRequirements = 'publisher\manual_asset_inbox\requirements.txt'
if (-not (Test-Path $ManualRequirements)) { throw "File dipendenze mancante: $ManualRequirements" }
& $Python -m pip install --disable-pip-version-check -r $ManualRequirements 2>&1 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0) { throw 'Dipendenze pannello manuale fallite.' }

$Installer = Join-Path $RepoDir 'publisher\f1_graphics_automation\INSTALLA_AUTOMAZIONE_23.ps1'
if (-not (Test-Path $Installer)) { throw 'Installer manuale F1 mancante.' }

Log 'Configuro F1 manual publish-only e rimuovo i task grafici legacy...' 'Cyan'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer -NonInteractive
if ($LASTEXITCODE -ne 0) { throw 'Configurazione pubblicatore manuale fallita.' }

$Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 5
if (-not $Health.ok -or $Health.mode -ne 'manual-publish-only' -or $Health.ai_image_generation -ne $false) {
    throw 'Verifica manual-publish-only fallita.'
}

[IO.File]::WriteAllText((Join-Path $InstallRoot 'F1_ULTIMA_INSTALLAZIONE.txt'),$RepoDir + [Environment]::NewLine,(New-Object Text.UTF8Encoding($false)))

Log 'INSTALLAZIONE COMPLETATA.' 'Green'
Log 'F1 crea 0 grafiche: usa soltanto file caricati dall operatore.' 'Green'
Log 'Pannello: http://127.0.0.1:8877/' 'Cyan'
Log 'PIXEL IN -> PIXEL OUT.' 'Cyan'

if (-not $SkipTest) {
    Start-Process 'http://127.0.0.1:8877/'
}
exit 0
