$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StackRoot = Join-Path $RepoRoot 'postiz-stack'
$Vendor = Join-Path $StackRoot 'vendor'
$SourceRepo = Join-Path $Vendor 'postiz-app'
$ComposeRepo = Join-Path $Vendor 'postiz-docker-compose'
$ComposeFile = Join-Path $ComposeRepo 'docker-compose.yaml'
$OverrideFile = Join-Path $StackRoot 'docker-compose.override.yml'
$EnvFile = Join-Path $PSScriptRoot 'postiz.env'
$BackupScript = Join-Path $PSScriptRoot 'BACKUP_POSTIZ_WINDOWS.ps1'
$BaseUrl = 'http://localhost:4007'
$PostizVersion = 'v2.22.1'
$ComposeCommit = 'dd4969e5e694cd009619a0d53cff14c21104580b'

Write-Host '=== OPEN SOCIAL SCHEDULER / POSTIZ - WINDOWS ==='
Write-Host 'Modalita: SELF-HOSTED + RECOVERY LOCALE'

foreach ($cmd in @('git','docker')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd non trovato. Usa OPEN_SOCIAL_SCHEDULER_AUTO_INSTALL.bat oppure installa il requisito e rilancia."
    }
}

if (-not (docker info 2>$null)) {
    $DockerCandidates = @(
        (Join-Path $Env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
        (Join-Path $Env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
    )
    $DockerDesktop = $DockerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($DockerDesktop) {
        Write-Host 'Apro Docker Desktop. Quando compare Engine running, rilancia INSTALLA_POSTIZ_WINDOWS.bat.'
        Start-Process $DockerDesktop
    }
    throw 'Docker Desktop non e ancora attivo.'
}

function Get-LatestBackup {
    $roots = @()
    if ($env:OPEN_SOCIAL_BACKUP_DIR) { $roots += $env:OPEN_SOCIAL_BACKUP_DIR }
    $roots += (Join-Path $StackRoot 'offline-backups')
    $roots += (Join-Path $env:USERPROFILE 'Google Drive\Il mio Drive\Open Social Scheduler Backups\Postiz')
    $roots += (Join-Path $env:USERPROFILE 'Google Drive\My Drive\Open Social Scheduler Backups\Postiz')
    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        $roots += (Join-Path $drive.Root 'Il mio Drive\Open Social Scheduler Backups\Postiz')
        $roots += (Join-Path $drive.Root 'My Drive\Open Social Scheduler Backups\Postiz')
    }
    foreach ($root in $roots | Select-Object -Unique) {
        if (-not $root -or -not (Test-Path $root)) { continue }
        $pointer = Join-Path $root 'LATEST.txt'
        if (Test-Path $pointer) {
            $candidate = (Get-Content -Raw $pointer).Trim()
            if ($candidate -and (Test-Path $candidate)) { return $candidate }
        }
        $candidate = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
        if ($candidate) { return $candidate }
    }
    return $null
}

$LatestBackup = Get-LatestBackup
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

# 1) Compose: prefer our own offline bundle. Only use upstream on first install if no backup exists.
if (-not (Test-Path (Join-Path $ComposeRepo '.git'))) {
    $composeBundle = if ($LatestBackup) { Join-Path $LatestBackup 'postiz-docker-compose.bundle' } else { $null }
    if ($composeBundle -and (Test-Path $composeBundle)) {
        Write-Host 'Ripristino Docker Compose Postiz dalla NOSTRA copia offline ...'
        git clone $composeBundle $ComposeRepo
    } else {
        Write-Host 'Prima installazione: clono Docker Compose ufficiale Postiz ...'
        git clone https://github.com/gitroomhq/postiz-docker-compose.git $ComposeRepo
        git -C $ComposeRepo checkout --detach $ComposeCommit
    }
} else {
    Write-Host 'Uso Docker Compose Postiz gia salvato localmente. Nessun pull automatico.'
}

# 2) Source code: keep a pinned independent local copy for audit/recovery/development.
if (-not (Test-Path (Join-Path $SourceRepo '.git'))) {
    $sourceBundle = if ($LatestBackup) { Join-Path $LatestBackup 'postiz-app.bundle' } else { $null }
    if ($sourceBundle -and (Test-Path $sourceBundle)) {
        Write-Host 'Ripristino sorgente Postiz dalla NOSTRA copia offline ...'
        git clone $sourceBundle $SourceRepo
    } else {
        Write-Host "Prima installazione: salvo sorgente Postiz $PostizVersion ..."
        git clone --depth 1 --branch $PostizVersion https://github.com/gitroomhq/postiz-app.git $SourceRepo
    }
} else {
    Write-Host 'Uso sorgente Postiz gia salvato localmente. Nessun aggiornamento automatico.'
}

if (-not (Test-Path $ComposeFile)) {
    throw "Compose Postiz non trovato: $ComposeFile"
}

if (-not (Test-Path $EnvFile)) {
    $JwtBytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($JwtBytes)
    $Jwt = [Convert]::ToHexString($JwtBytes).ToLowerInvariant()
    @"
POSTIZ_DOMAIN=localhost
POSTIZ_IMAGE=ghcr.io/gitroomhq/postiz-app:v2.22.1
MAIN_URL=$BaseUrl
FRONTEND_URL=$BaseUrl
NEXT_PUBLIC_BACKEND_URL=$BaseUrl/api
JWT_SECRET=$Jwt
DISABLE_REGISTRATION=false
API_LIMIT=100
STORAGE_PROVIDER=local
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
INSTAGRAM_APP_ID=
INSTAGRAM_APP_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
TIKTOK_CLIENT_ID=
TIKTOK_CLIENT_SECRET=
PINTEREST_CLIENT_ID=
PINTEREST_CLIENT_SECRET=
OPENAI_API_KEY=
"@ | Set-Content -Encoding UTF8 $EnvFile
    Write-Host "Creato $EnvFile"
} else {
    Write-Host "Uso configurazione esistente $EnvFile"
}

# If the image disappeared upstream but we already have our recovery archive, load it first.
$imageExists = $false
try {
    $imageExists = [bool](docker image inspect 'ghcr.io/gitroomhq/postiz-app:v2.22.1' 2>$null)
} catch { $imageExists = $false }
if (-not $imageExists -and $LatestBackup) {
    $imagesTar = Join-Path $LatestBackup 'docker-images.tar'
    if (Test-Path $imagesTar) {
        Write-Host 'Carico le immagini Docker dalla NOSTRA copia offline ...'
        docker load -i $imagesTar
    }
}

$env:POSTIZ_STACK_DIR = $StackRoot
Write-Host 'Avvio Postiz ...'
docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile up -d

docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile ps
Write-Host ''
Write-Host 'POSTIZ LOCALE: http://localhost:4007'
Write-Host 'Il dominio pubblico verra configurato in seguito con Cloudflare Tunnel.'

# Create one complete recovery snapshot immediately after a successful installation.
if (Test-Path $BackupScript) {
    Write-Host ''
    Write-Host 'Creo la copia di sicurezza indipendente da Postiz/GitHub ...'
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BackupScript
    } catch {
        Write-Warning "Postiz e avviato, ma il backup iniziale non e riuscito: $($_.Exception.Message)"
    }
}

Write-Host ''
Write-Host 'INSTALLAZIONE COMPLETATA: il runtime resta locale e non esegue aggiornamenti automatici dall upstream.'
