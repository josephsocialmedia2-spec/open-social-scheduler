$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StackRoot = Join-Path $RepoRoot 'postiz-stack'
$Vendor = Join-Path $StackRoot 'vendor'
$ComposeRepo = Join-Path $Vendor 'postiz-docker-compose'
$ComposeFile = Join-Path $ComposeRepo 'docker-compose.yaml'
$OverrideFile = Join-Path $StackRoot 'docker-compose.override.yml'
$EnvFile = Join-Path $PSScriptRoot 'postiz.env'
$BaseUrl = 'http://localhost:4007'

Write-Host '=== OPEN SOCIAL SCHEDULER / POSTIZ - WINDOWS ==='

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

New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
if (-not (Test-Path (Join-Path $ComposeRepo '.git'))) {
    Write-Host 'Clone Docker Compose ufficiale Postiz ...'
    git clone --depth 1 https://github.com/gitroomhq/postiz-docker-compose.git $ComposeRepo
} else {
    Write-Host 'Aggiorno Docker Compose ufficiale Postiz ...'
    git -C $ComposeRepo pull --ff-only
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

$env:POSTIZ_STACK_DIR = $StackRoot
Write-Host 'Avvio Postiz ...'
docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile up -d

docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile ps
Write-Host ''
Write-Host 'POSTIZ LOCALE: http://localhost:4007'
Write-Host 'Il dominio pubblico verra configurato in seguito con Cloudflare Tunnel.'
