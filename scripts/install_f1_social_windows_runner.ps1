param(
    [string]$RunnerToken = $env:GITHUB_RUNNER_TOKEN
)

$ErrorActionPreference = "Stop"

$RepoFullName = "josephsocialmedia2-spec/open-social-scheduler"
$RepoUrl = "https://github.com/$RepoFullName"
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
Ensure-Command "gh" "GitHub.cli"

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
        gh auth status -h github.com *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Autorizza GitHub una sola volta nel browser..." -ForegroundColor Yellow
            gh auth login -h github.com -p https -w
            if ($LASTEXITCODE -ne 0) {
                throw "Autorizzazione GitHub non completata."
            }
        }

        $RunnerToken = gh api -X POST "repos/$RepoFullName/actions/runners/registration-token" --jq ".token"
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RunnerToken)) {
            throw "Impossibile ottenere automaticamente il token temporaneo del runner."
        }
    }

    Push-Location $RunnerDir
    try {
        & .\config.cmd --unattended --url $RepoUrl --token $RunnerToken --name "F1-Social-PC-$env:COMPUTERNAME" --labels "f1-social-browser,f1-social-local-pc" --work "_work" --replace
        if ($LASTEXITCODE -ne 0) {
            throw "Configurazione GitHub Runner non riuscita."
        }
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

if (-not (Get-Process -Name "Runner.Listener" -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $Launcher -WorkingDirectory $Root -WindowStyle Minimized
    Start-Sleep -Seconds 5
}

gh auth status -h github.com *> $null
if ($LASTEXITCODE -eq 0) {
    gh variable set F1_BROWSER_FALLBACK_ENABLED --body "true" -R $RepoFullName
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Runner pronto, ma non sono riuscito ad attivare automaticamente F1_BROWSER_FALLBACK_ENABLED."
    }

    $secretNames = gh secret list -R $RepoFullName --json name --jq ".[].name"
    if ($secretNames -contains "SUPABASE_SERVICE_ROLE_KEY") {
        gh workflow run f1-social-local-profile-setup.yml -R $RepoFullName -f timeout_per_client=600
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Configurazione profili clienti avviata: compariranno le finestre Chrome dei social non configurati." -ForegroundColor Green
        } else {
            Write-Warning "Runner installato, ma il workflow di configurazione profili non e' stato avviato automaticamente."
        }
    } else {
        Write-Warning "Manca il repository secret SUPABASE_SERVICE_ROLE_KEY. Impostalo in GitHub Actions Secrets prima del workflow di configurazione profili."
    }
}

Write-Host ""
Write-Host "F1 Social Windows Runner installato e avviato." -ForegroundColor Green
Write-Host "Profili Chrome separati: $BrowserRoot"
Write-Host "Avvio automatico al login Windows: $StartupLauncher"
Write-Host "Il PC puo' ora eseguire la pubblicazione browser per i social non configurati."
