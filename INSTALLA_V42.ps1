$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$parts = Get-ChildItem (Join-Path $root 'package') -Filter 'part_*.b64' | Sort-Object Name
if (!$parts -or $parts.Count -lt 1) { throw 'Pacchetto di installazione incompleto.' }

Write-Host 'Preparazione Open Social Scheduler V4.2...' -ForegroundColor Cyan
$base64 = ($parts | ForEach-Object { Get-Content $_.FullName -Raw }) -join ''
$zipPath = Join-Path $env:TEMP 'Open_Social_Scheduler_AUTO_INSTALLANTE_V4_2.zip'
[IO.File]::WriteAllBytes($zipPath, [Convert]::FromBase64String($base64))

$target = Join-Path $env:TEMP 'Open_Social_Scheduler_AUTO_INSTALLANTE_V4_2'
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath $target -Force

$innerRoot = Join-Path $target 'open-social-scheduler-auto'
$innerScript = Join-Path $innerRoot 'INSTALLA_OPEN_SOCIAL_SCHEDULER.ps1'
$innerBat = Join-Path $innerRoot 'INSTALLA.bat'
if (!(Test-Path $innerBat)) { throw 'INSTALLA.bat non trovato nel pacchetto.' }

$oldBootstrapPath = Join-Path $root 'INSTALLA.ps1'
$oldBootstrap = [IO.File]::ReadAllText($oldBootstrapPath)
$match = [regex]::Match($oldBootstrap, "\$fixedInstallerBase64 = '([^']+)'")
if (!$match.Success) { throw 'Script interno corretto non trovato.' }

$innerText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($match.Groups[1].Value))
$oldCreate = "Run-Command `$clasp @('create-script', '--title', 'Open Social Scheduler CRM', '--type', 'webapp')"
$newCreate = "Run-Command `$clasp @('create-script', '--title', 'Open Social Scheduler CRM', '--type', 'standalone')"
$innerText = $innerText.Replace($oldCreate, $newCreate)

$needle = "  `$utf8NoBom = New-Object System.Text.UTF8Encoding(`$false)"
if ($innerText -notmatch 'scriptId mancante in \.clasp\.json') {
  $validation = @'
  if (!(Test-Path $claspConfigPath)) {
    throw 'Creazione progetto non riuscita: il file .clasp.json non e stato generato.'
  }

  try {
    $claspSettings = Get-Content $claspConfigPath -Raw | ConvertFrom-Json
  } catch {
    throw 'Il file .clasp.json creato da clasp non e valido.'
  }

  if (!$claspSettings.scriptId) {
    throw 'Creazione progetto non riuscita: scriptId mancante in .clasp.json.'
  }

  Write-Host ("Progetto creato. Script ID: " + $claspSettings.scriptId) -ForegroundColor Green

'@
  $innerText = $innerText.Replace($needle, $validation + $needle)
}

if ($innerText -match "'--type', 'webapp'") { throw 'Correzione del tipo progetto non applicata.' }
if ($innerText -notmatch "'--type', 'standalone'") { throw 'Tipo standalone non trovato nello script corretto.' }

[IO.File]::WriteAllText($innerScript, $innerText, [Text.Encoding]::ASCII)
$process = Start-Process -FilePath $innerBat -WorkingDirectory $innerRoot -Wait -PassThru
if ($process.ExitCode -ne 0) { exit $process.ExitCode }
