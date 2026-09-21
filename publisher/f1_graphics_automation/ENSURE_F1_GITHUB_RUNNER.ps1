param()

$ErrorActionPreference = 'Stop'
$TaskName = 'F1_GitHub_Runner'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$candidates = @(
    (Join-Path $env:USERPROFILE 'actions-runner'),
    'C:\actions-runner',
    'C:\github-runner',
    'C:\GitHubActionsRunner'
) | Select-Object -Unique

$runnerDir = $null
foreach ($dir in $candidates) {
    if ((Test-Path (Join-Path $dir 'run.cmd')) -and (Test-Path (Join-Path $dir '.runner'))) {
        $runnerDir = $dir
        break
    }
}

if (-not $runnerDir) {
    Write-Host 'NO_REGISTERED_LOCAL_RUNNER_FOUND'
    exit 2
}

$runCmd = Join-Path $runnerDir 'run.cmd'
$cmd = "$env:SystemRoot\System32\cmd.exe"
$args = "/c `"$runCmd`""
$action = New-ScheduledTaskAction -Execute $cmd -Argument $args -WorkingDirectory $runnerDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Description 'Keeps the registered GitHub Actions runner online in the interactive Windows session for F1 browser automation.' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

$listener = Get-Process -Name 'Runner.Listener' -ErrorAction SilentlyContinue
if (-not $listener) {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3
}

$listener = Get-Process -Name 'Runner.Listener' -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "RUNNER_READY dir=$runnerDir pid=$($listener.Id)"
    exit 0
}

Write-Host "RUNNER_CONFIGURED_BUT_NOT_STARTED dir=$runnerDir"
exit 3
