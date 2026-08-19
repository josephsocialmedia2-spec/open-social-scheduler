$ErrorActionPreference = 'Stop'

$TaskName = 'Open Social Scheduler - Backup Postiz'
$BackupScript = Join-Path $PSScriptRoot 'BACKUP_POSTIZ_WINDOWS.ps1'

if (-not (Test-Path $BackupScript)) {
    throw "Script backup non trovato: $BackupScript"
}

$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$BackupScript`" -SkipDockerImages"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Backup giornaliero dati Postiz/Open Social Scheduler. Le immagini Docker sono gia conservate nel backup completo iniziale.' -Force | Out-Null

Write-Host "Backup automatico attivato: ogni giorno alle 03:00."
Write-Host "Task Scheduler: $TaskName"
