$ErrorActionPreference = 'SilentlyContinue'

# Open Social Scheduler - Monday launcher
# Runs at Windows logon, but opens the planning tabs only once per Monday.

$today = Get-Date
if ($today.DayOfWeek -ne [System.DayOfWeek]::Monday) {
    exit 0
}

$stateDir = Join-Path $env:LOCALAPPDATA 'OpenSocialScheduler'
$stateFile = Join-Path $stateDir 'last_monday_opened.txt'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$todayKey = $today.ToString('yyyy-MM-dd')
if (Test-Path $stateFile) {
    $last = (Get-Content $stateFile -Raw).Trim()
    if ($last -eq $todayKey) {
        exit 0
    }
}

$urls = @(
    'https://josephsocialmedia2-spec.github.io/open-social-scheduler/monday-control.html',
    'https://social.realmediapro.it',
    'https://business.facebook.com/latest/home',
    'https://www.tiktok.com/tiktokstudio',
    'https://studio.youtube.com',
    'https://www.linkedin.com/company/',
    'https://www.pinterest.com/business/hub/'
)

foreach ($url in $urls) {
    Start-Process $url
    Start-Sleep -Milliseconds 500
}

Set-Content -Path $stateFile -Value $todayKey -Encoding UTF8
