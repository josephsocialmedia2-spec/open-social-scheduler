$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$parts = Get-ChildItem (Join-Path $root 'package') -Filter 'part_*.b64' | Sort-Object Name
if (!$parts -or $parts.Count -ne 5) { throw 'Pacchetto di installazione incompleto. Devono essere presenti 5 parti.' }
Write-Host 'Preparazione Open Social Scheduler - Google Drive senza API...' -ForegroundColor Cyan
$base64 = ($parts | ForEach-Object { Get-Content $_.FullName -Raw }) -join ''
$zipPath = Join-Path $env:TEMP 'Open_Social_Scheduler_Google_Drive_SENZA_API.zip'
[IO.File]::WriteAllBytes($zipPath, [Convert]::FromBase64String($base64))
$target = Join-Path $env:TEMP 'Open_Social_Scheduler_Google_Drive_SENZA_API'
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath $target -Force
$inner = Join-Path $target 'Open_Social_Scheduler_Google_Drive_SENZA_API\INSTALLA.bat'
if (!(Test-Path $inner)) { throw 'INSTALLA.bat non trovato nel pacchetto.' }
Start-Process -FilePath $inner -WorkingDirectory (Split-Path $inner) -Wait
