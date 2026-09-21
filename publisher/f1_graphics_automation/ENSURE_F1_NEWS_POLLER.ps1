param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Poller = Join-Path $PSScriptRoot 'RUN_F1_NEWS_POLLER.ps1'
$TaskName = 'F1_News_GitHub_Poller'
$PsExe = (Get-Command powershell.exe -ErrorAction Stop).Source
$UserId = "$env:USERDOMAIN\$env:USERNAME"

$Action = New-ScheduledTaskAction -Execute $PsExe -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"" + $Poller + "`"") -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Description 'GitHub controls F1 News queue; this interactive poller starts ChatGPT browser jobs automatically during the publication windows.' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null

Write-Host "$TaskName ready."
