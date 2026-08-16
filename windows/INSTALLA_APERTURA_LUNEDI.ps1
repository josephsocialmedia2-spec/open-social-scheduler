$ErrorActionPreference = 'Stop'

$installDir = Join-Path $env:LOCALAPPDATA 'OpenSocialScheduler'
$launcher = Join-Path $installDir 'APRI_PIANIFICAZIONE_LUNEDI.ps1'
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Open Social Scheduler - Lunedi.lnk'

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$sourceUrl = 'https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/windows/APRI_PIANIFICAZIONE_LUNEDI.ps1'
Invoke-WebRequest -Uri $sourceUrl -OutFile $launcher -UseBasicParsing

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = 'Apre automaticamente la pianificazione social il primo accesso del lunedi'
$shortcut.Save()

Write-Host ''
Write-Host 'INSTALLAZIONE COMPLETATA' -ForegroundColor Green
Write-Host 'Da ora il launcher parte con Windows.'
Write-Host 'Solo il lunedi, al primo accesso, apre automaticamente i pannelli social.'
Write-Host 'Negli altri giorni non apre nulla.'
Write-Host ''

# Test immediately only when today is Monday; otherwise open the control center once for setup verification.
if ((Get-Date).DayOfWeek -eq [System.DayOfWeek]::Monday) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher
} else {
    Start-Process 'https://josephsocialmedia2-spec.github.io/open-social-scheduler/monday-control.html'
}
