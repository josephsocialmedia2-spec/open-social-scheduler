param(
    [string]$RunnerToken = $env:GITHUB_RUNNER_TOKEN
)

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/josephsocialmedia2-spec/open-social-scheduler"
$Root = "C:\F1Social"
$RepoDir = Join-Path $Root "open-social-scheduler"
$VenvDir = Join-Path $Root "venv"
$RunnerDir = Join-Path $Root "actions-runner"
$BrowserRoot = Join-Path $Root "BrowserProfiles"

New-Item -ItemType Directory -Force -Path $Root,$RunnerDir,$BrowserRoot | Out-Null

function Ensure-Command {
    param([string]$Command,[string]$WingetId)
    if (Get-Command $Command -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$Command non trovato e winget non disponibile."
    }
    winget install --id $WingetId --exact --accept-package-agreements --accept-source-agreements
}

Ensure-Command "git" "Git.Git"
Ensure-Command "python" "Python.Python.3.12"

$ChromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$Chrome = $ChromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Chrome) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Google.Chrome --exact --accept-package-agreements --accept-source-agreements
        $Chrome = $ChromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
}
if (-not $Chrome) { throw "Google Chrome non trovato." }

if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
    git clone $RepoUrl $RepoDir
} else {
    git -C $RepoDir fetch origin
    git -C $RepoDir checkout main
    git -C $RepoDir pull --ff-only origin main
}

if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    python -m venv $VenvDir
}
$Python = Join-Path $VenvDir "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $RepoDir "publisher\cloud_publisher\requirements.txt")

if (-not (Test-Path (Join-Path $RunnerDir "run.cmd"))) {
    $release = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest"
    $version = $release.tag_name.TrimStart("v")
    $zip = Join-Path $env:TEMP "actions-runner-win-x64-$version.zip"
    Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v$version/actions-runner-win-x64-$version.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $RunnerDir -Force
}

if (-not (Test-Path (Join-Path $RunnerDir ".runner"))) {
    if ([string]::IsNullOrWhiteSpace($RunnerToken)) {
        Write-Host ""
        Write-Host "Dipendenze installate. Manca solo il token temporaneo del GitHub Runner." -ForegroundColor Yellow
        Write-Host "Apri:"
        Write-Host "https://github.com/josephsocialmedia2-spec/open-social-scheduler/settings/actions/runners/new"
        Write-Host ""
        Write-Host "Poi in PowerShell:"
        Write-Host '$env:GITHUB_RUNNER_TOKEN="TOKEN_TEMPORANEO"'
        Write-Host 'powershell -ExecutionPolicy Bypass -File .\scripts\install_f1_social_windows_runner.ps1'
        exit 10
    }

    Push-Location $RunnerDir
    try {
        & .\config.cmd --unattended --url $RepoUrl --token $RunnerToken --name "F1-Social-PC-$env:COMPUTERNAME" --labels "f1-social-browser,f1-social-local-pc" --work "_work" --replace
    } finally {
        Pop-Location
    }
}

$Launcher = Join-Path $Root "start-f1-social-runner.cmd"
@"
@echo off
set F1_BROWSER_ROOT=C:\F1Social\BrowserProfiles
set F1_BROWSER_CHANNEL=chrome
set F1_BROWSER_HEADLESS=true
cd /d C:\F1Social\actions-runner
call run.cmd
"@ | Set-Content -Path $Launcher -Encoding ASCII

$Startup = [Environment]::GetFolderPath("Startup")
$StartupLauncher = Join-Path $Startup "F1SocialRunner.cmd"
@"
@echo off
start "" /min cmd /c "C:\F1Social\start-f1-social-runner.cmd"
"@ | Set-Content -Path $StartupLauncher -Encoding ASCII

[Environment]::SetEnvironmentVariable("F1_BROWSER_ROOT",$BrowserRoot,"User")
[Environment]::SetEnvironmentVariable("F1_BROWSER_CHANNEL","chrome","User")
[Environment]::SetEnvironmentVariable("F1_BROWSER_HEADLESS","true","User")

Write-Host ""
Write-Host "F1 Social Windows Runner installato." -ForegroundColor Green
Write-Host "Profili Chrome: $BrowserRoot"
Write-Host "Runner: $RunnerDir"
Write-Host "Avvio automatico al login: $StartupLauncher"
Write-Host ""
Write-Host "Avvio immediato:"
Write-Host $Launcher
Write-Host ""
Write-Host "Configurazione account clienti:"
Write-Host "cd $RepoDir"
Write-Host '$env:SUPABASE_SERVICE_ROLE_KEY="<valore protetto>"'
Write-Host "& `"$Python`" scripts\f1_windows_prepare_clients.py"
