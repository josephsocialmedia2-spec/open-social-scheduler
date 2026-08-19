param(
    [string]$Backup = '',
    [string]$BackupRoot = '',
    [switch]$RestoreSecrets
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
    if ($Explicit) { return $Explicit }
    if ($env:OPEN_SOCIAL_BACKUP_DIR) { return $env:OPEN_SOCIAL_BACKUP_DIR }

    $candidates = @(
        (Join-Path $env:USERPROFILE 'Google Drive\Il mio Drive\Open Social Scheduler Backups\Postiz'),
        (Join-Path $env:USERPROFILE 'Google Drive\My Drive\Open Social Scheduler Backups\Postiz'),
        (Join-Path $StackRoot 'offline-backups')
    )
    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        $candidates += (Join-Path $drive.Root 'Il mio Drive\Open Social Scheduler Backups\Postiz')
        $candidates += (Join-Path $drive.Root 'My Drive\Open Social Scheduler Backups\Postiz')
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    throw 'Nessuna cartella backup Postiz trovata.'
}

foreach ($cmd in @('git','docker')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd non trovato." }
}
if (-not (docker info 2>$null)) { throw 'Docker Desktop non e attivo.' }

if (-not $Backup) {
    $root = Find-BackupRoot -Explicit $BackupRoot
    $latestPointer = Join-Path $root 'LATEST.txt'
    if (Test-Path $latestPointer) {
        $Backup = (Get-Content -Raw $latestPointer).Trim()
    } else {
        $Backup = Get-ChildItem $root -Directory | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
}
if (-not $Backup -or -not (Test-Path $Backup)) { throw "Backup non trovato: $Backup" }

Write-Host "=== RIPRISTINO POSTIZ ==="
Write-Host "Snapshot: $Backup"
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

# Restore source repositories from our own offline bundles first.
$sourceBundle = Join-Path $Backup 'postiz-app.bundle'
$composeBundle = Join-Path $Backup 'postiz-docker-compose.bundle'
if (-not (Test-Path (Join-Path $SourceRepo '.git')) -and (Test-Path $sourceBundle)) {
    & git clone $sourceBundle $SourceRepo
}
if (-not (Test-Path (Join-Path $ComposeRepo '.git')) -and (Test-Path $composeBundle)) {
    & git clone $composeBundle $ComposeRepo
}

# Fallback compose file saved in the snapshot, even if the git bundle is unavailable.
if (-not (Test-Path $ComposeFile)) {
    $savedCompose = Join-Path $Backup 'docker-compose.yaml'
    if (-not (Test-Path $savedCompose)) { throw 'docker-compose.yaml non disponibile nel backup.' }
    New-Item -ItemType Directory -Force -Path $ComposeRepo | Out-Null
    Copy-Item $savedCompose $ComposeFile -Force
}

$imagesTar = Join-Path $Backup 'docker-images.tar'
if (Test-Path $imagesTar) {
    Write-Host 'Carico le immagini Docker dalla nostra copia offline ...'
    & docker load -i $imagesTar
}

# Restore encrypted env only on the same Windows user/machine unless explicitly requested.
$encryptedEnv = Join-Path $Backup 'postiz.env.dpapi'
if ($RestoreSecrets -and (Test-Path $encryptedEnv)) {
    try {
        $cipher = (Get-Content -Raw $encryptedEnv).Trim()
        $secure = ConvertTo-SecureString $cipher
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
        Set-Content -Encoding UTF8 -Path $EnvFile -Value $plain
        Write-Host 'Configurazione segreta ripristinata tramite Windows DPAPI.'
    } catch {
        Write-Warning 'Impossibile decifrare postiz.env.dpapi su questo utente/computer. Mantengo la configurazione esistente.'
    }
}
if (-not (Test-Path $EnvFile)) {
    throw 'postiz.env mancante. Se il backup proviene dallo stesso utente Windows rilancia con -RestoreSecrets.'
}

$env:POSTIZ_STACK_DIR = $StackRoot

# Start only infrastructure first, restore state, then start the application.
& docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile up -d postiz-postgres postiz-redis temporal-postgresql temporal-elasticsearch temporal
Start-Sleep -Seconds 5

$postizSql = Join-Path $Backup 'postiz-db.sql'
if (Test-Path $postizSql) {
    Write-Host 'Ripristino database Postiz ...'
    $cmd = "type `"$postizSql`" | docker exec -i postiz-postgres psql -U postiz-user -d postgres"
    cmd /c $cmd
}

$temporalSql = Join-Path $Backup 'temporal-db.sql'
if (Test-Path $temporalSql) {
    Write-Host 'Ripristino database Temporal ...'
    $cmd = "type `"$temporalSql`" | docker exec -i temporal-postgresql psql -U temporal -d postgres"
    cmd /c $cmd
}

$redisDump = Join-Path $Backup 'redis-dump.rdb'
if (Test-Path $redisDump) {
    & docker stop postiz-redis | Out-Null
    & docker cp $redisDump 'postiz-redis:/data/dump.rdb' | Out-Null
    & docker start postiz-redis | Out-Null
}

& docker compose --env-file $EnvFile -f $ComposeFile -f $OverrideFile up -d

$filesRoot = Join-Path $Backup 'postiz-files'
if ((Test-Path $filesRoot) -and ((docker ps --format '{{.Names}}') -contains 'postiz')) {
    if (Test-Path (Join-Path $filesRoot 'uploads')) {
        & docker cp (Join-Path $filesRoot 'uploads\.') 'postiz:/uploads/' | Out-Null
    }
    if (Test-Path (Join-Path $filesRoot 'config')) {
        & docker cp (Join-Path $filesRoot 'config\.') 'postiz:/config/' | Out-Null
    }
    & docker restart postiz | Out-Null
}

Write-Host ''
Write-Host 'RIPRISTINO COMPLETATO.'
Write-Host 'Postiz usa ora codice, dati e immagini conservati nella nostra copia di sicurezza.'
