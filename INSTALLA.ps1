$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$parts = Get-ChildItem (Join-Path $root 'package') -Filter 'part_*.b64' | Sort-Object Name
if (!$parts -or $parts.Count -lt 1) { throw 'Pacchetto di installazione incompleto.' }
Write-Host 'Preparazione Open Social Scheduler...' -ForegroundColor Cyan
$base64 = ($parts | ForEach-Object { Get-Content $_.FullName -Raw }) -join ''
$zipPath = Join-Path $env:TEMP 'Open_Social_Scheduler_AUTO_INSTALLANTE_V4.zip'
[IO.File]::WriteAllBytes($zipPath, [Convert]::FromBase64String($base64))
$target = Join-Path $env:TEMP 'Open_Social_Scheduler_AUTO_INSTALLANTE_V4'
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath $target -Force
$inner = Join-Path $target 'open-social-scheduler-auto\INSTALLA.bat'
if (!(Test-Path $inner)) { throw 'INSTALLA.bat non trovato nel pacchetto.' }
Start-Process -FilePath $inner -WorkingDirectory (Split-Path $inner) -Wait
