param(
    [string]$Destination = '',
    [switch]$SkipDockerImages
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StackRoot = Join-Path $RepoRoot 'postiz-stack'
$Vendor = Join-Path $StackRoot 'vendor'
$SourceRepo = Join-Path $Vendor 'postiz-app'
$ComposeRepo = Join-Path $Vendor 'postiz-docker-compose'
$ComposeFile = Join-Path $ComposeRepo 'docker-compose.yaml'
$OverrideFile = Join-Path $StackRoot 'docker-compose.override.yml'
$EnvFile = Join-Path $PSScriptRoot 'postiz.env'

function Find-BackupRoot {
    param([string]$Explicit)
    if ($Explicit) {
        return $Explicit
    }
    if ($env:OPEN_SOCIAL_BACKUP_DIR) {
        return $env:OPEN_SOCIAL_BACKUP_DIR
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE 'Google Drive\Il mio Drive'),
        (Join-Path $env:USERPROFILE 'Google Drive\My Drive')
    )

    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        $candidates += (Join-Path $drive.Root 'Il mio Drive')
        $candidates += (Join-Path $drive.Root 'My Drive')
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Join-Path $candidate 'Open Social Scheduler Backups\Postiz')
        }
    }

    return (Join-Path $StackRoot 'offline-backups')
}

foreach ($cmd in @('git','docker')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd non trovato."
    }
}
if (-not (docker info 2>$null)) {
    throw 'Docker Desktop non e attivo.'
}

$BackupRoot = Find-BackupRoot -Explicit $Destination
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = Join-Path $BackupRoot $Stamp
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Host "Backup Postiz: $BackupDir"

# 1) Source-code snapshots: independent git bundles.
if (Test-Path (Join-Path $SourceRepo '.git')) {
    & git -C $SourceRepo bundle create (Join-Path $BackupDir 'postiz-app.bundle') --all
}
if (Test-Path (Join-Path $ComposeRepo '.git')) {
    & git -C $ComposeRepo bundle create (Join-Path $BackupDir 'postiz-docker-compose.bundle') --all
}

# 2) Runtime configuration. Secrets are encrypted with Windows DPAPI for the current user.
if (Test-Path $EnvFile) {
    $plain = Get-Content -Raw $EnvFile
    $secure = ConvertTo-SecureString $plain -AsPlainText -Force
    $cipher = ConvertFrom-SecureString $secure
    Set-Content -Encoding UTF8 -Path (Join-Path $BackupDir 'postiz.env.dpapi') -Value $cipher
}
Copy-Item $OverrideFile (Join-Path $BackupDir 'docker-compose.override.yml') -Force
if (Test-Path $ComposeFile) {
    Copy-Item $ComposeFile (Join-Path $BackupDir 'docker-compose.yaml') -Force
}

# 3) Databases and media. Dumps are restorable into a clean host.
if ((docker ps --format '{{.Names}}') -contains 'postiz-postgres') {
    & docker exec postiz-postgres pg_dump --clean --if-exists --create -U postiz-user -d postiz-db-local | Set-Content -Encoding UTF8 (Join-Path $BackupDir 'postiz-db.sql')
}
if ((docker ps --format '{{.Names}}') -contains 'temporal-postgresql') {
    & docker exec temporal-postgresql pg_dumpall --clean --if-exists -U temporal | Set-Content -Encoding UTF8 (Join-Path $BackupDir 'temporal-db.sql')
}
if ((docker ps --format '{{.Names}}') -contains 'postiz-redis') {
    & docker exec postiz-redis redis-cli SAVE | Out-Null
    & docker cp 'postiz-redis:/data/dump.rdb' (Join-Path $BackupDir 'redis-dump.rdb') | Out-Null
}
if ((docker ps --format '{{.Names}}') -contains 'postiz') {
    New-Item -ItemType Directory -Force -Path (Join-Path $BackupDir 'postiz-files') | Out-Null
    try { & docker cp 'postiz:/uploads' (Join-Path $BackupDir 'postiz-files\uploads') | Out-Null } catch { Write-Warning 'Backup /uploads non disponibile.' }
    try { & docker cp 'postiz:/config' (Join-Path $BackupDir 'postiz-files\config') | Out-Null } catch { Write-Warning 'Backup /config non disponibile.' }
}

# 4) Save every Docker image required by the current compose stack.
$images = @()
if ((Test-Path $ComposeFile) -and (Test-Path $EnvFile)) {
    $images = @(& docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile config --images 2>$null) | Where-Object { $_ } | Sort-Object -Unique
}
if (-not $SkipDockerImages -and $images.Count -gt 0) {
    & docker save -o (Join-Path $BackupDir 'docker-images.tar') @images
}

$sourceCommit = if (Test-Path (Join-Path $SourceRepo '.git')) { (& git -C $SourceRepo rev-parse HEAD).Trim() } else { $null }
$composeCommit = if (Test-Path (Join-Path $ComposeRepo '.git')) { (& git -C $ComposeRepo rev-parse HEAD).Trim() } else { $null }
$manifest = [ordered]@{
    created_at = (Get-Date).ToString('o')
    computer = $env:COMPUTERNAME
    user = $env:USERNAME
    postiz_version = 'v2.22.1'
    postiz_source_commit = $sourceCommit
    compose_commit = $composeCommit
    docker_images = $images
    contains_docker_images = (-not $SkipDockerImages -and (Test-Path (Join-Path $BackupDir 'docker-images.tar')))
    contains_postiz_db = (Test-Path (Join-Path $BackupDir 'postiz-db.sql'))
    contains_temporal_db = (Test-Path (Join-Path $BackupDir 'temporal-db.sql'))
    env_encryption = 'Windows DPAPI current-user'
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $BackupDir 'manifest.json')

# Pointer used by the installer/restore scripts.
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
Set-Content -Encoding UTF8 -Path (Join-Path $BackupRoot 'LATEST.txt') -Value $BackupDir

Write-Host ''
Write-Host 'BACKUP COMPLETATO.'
Write-Host "Cartella: $BackupDir"
Write-Host 'Questo snapshot consente di ripristinare Postiz anche se repository o immagini upstream non fossero piu disponibili.'
