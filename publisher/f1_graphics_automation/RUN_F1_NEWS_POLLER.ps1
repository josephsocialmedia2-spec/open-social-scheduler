param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$QueueSnapshot = Join-Path $Root 'publisher\news\f1_news_browser_queue.runtime.local.json'
$CreativeControlSnapshot = Join-Path $Root 'publisher\chatgpt_query_runner\f1_daily_creative_control.runtime.local.json'
$FinalSnapshot = Join-Path $Root 'publisher\news\f1_news_final_queue.runtime.local.json'
$LockPath = Join-Path $Root 'publisher\news\f1_news_browser_poller.lock.json'
$Runner = Join-Path $PSScriptRoot 'RUN_F1_NEWS_SLOT.ps1'
$CreativeRunner = Join-Path $PSScriptRoot 'RUN_F1_DAILY_CREATIVE_TEST.ps1'
$Now = Get-Date
$Minutes = ($Now.Hour * 60) + $Now.Minute

function Refresh-JsonFromOrigin {
    param([string]$RepoPath,[string]$Destination)
    $lines = git -C $Root show ("origin/main:" + $RepoPath) 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $lines) { return $false }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Destination, ($lines -join [Environment]::NewLine) + [Environment]::NewLine, $utf8)
    return $true
}

git -C $Root fetch origin main *> $null
if ($LASTEXITCODE -ne 0) { exit 0 }

if (-not (Refresh-JsonFromOrigin 'publisher/news/f1_news_browser_queue.json' $QueueSnapshot)) { exit 0 }
if (-not (Refresh-JsonFromOrigin 'publisher/final_content_queue.json' $FinalSnapshot)) { exit 0 }
$CreativeControlAvailable = Refresh-JsonFromOrigin 'publisher/chatgpt_query_runner/f1_daily_creative_control.json' $CreativeControlSnapshot

$Queue = Get-Content $QueueSnapshot -Raw | ConvertFrom-Json
$Final = Get-Content $FinalSnapshot -Raw | ConvertFrom-Json

$completed = @{}
foreach ($job in @($Final.jobs)) {
    $cid = [string]$job.communication_id
    if ($cid -and ([string]$job.status -eq 'PUBLISHED_VERIFIED')) { $completed[$cid] = $true }
}

if (Test-Path $LockPath) {
    try {
        $lock = Get-Content $LockPath -Raw | ConvertFrom-Json
        $started = [DateTimeOffset]::Parse([string]$lock.started_at)
        if ((([DateTimeOffset]::Now - $started).TotalMinutes) -lt 50) { exit 0 }
    } catch {}
    Remove-Item $LockPath -Force -ErrorAction SilentlyContinue
}

# Priority 1: one-shot visible ChatGPT creative requested by GitHub.
if ($CreativeControlAvailable -and (Test-Path $CreativeControlSnapshot)) {
    try {
        $Creative = Get-Content $CreativeControlSnapshot -Raw | ConvertFrom-Json
        $expectedCid = [string]$Creative.expected_communication_id
        $forceCreative = [bool]$Creative.force_immediate
        $existingFinal = @($Final.jobs) | Where-Object { [string]$_.communication_id -eq $expectedCid } | Select-Object -First 1

        if ($forceCreative -and $expectedCid -and -not $existingFinal) {
            @{
                job_id = [string]$Creative.target_query_id
                communication_id = $expectedCid
                mode = 'daily-creative'
                started_at = [DateTimeOffset]::Now.ToString('o')
            } | ConvertTo-Json | Set-Content -Path $LockPath -Encoding UTF8

            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $CreativeRunner
                exit $LASTEXITCODE
            } finally {
                Remove-Item $LockPath -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

$candidates = @($Queue.items) | Where-Object {
    $status = [string]$_.status
    $cid = [string]$_.id
    $slotKey = [string]$_.slot_key
    if (-not $cid -or $completed.ContainsKey($cid)) { return $false }
    if ($status -in @('PUBLISHED_VERIFIED','FAILED_FINAL','CANCELLED')) { return $false }
    if ([bool]$_.force_immediate) { return $true }
    if ($slotKey -match '^([0-9]{4}-[0-9]{2}-[0-9]{2})\|(MIDDAY|EVENING|IMMEDIATE)$') {
        $datePart = $Matches[1]
        $slotPart = $Matches[2]
        if ($datePart -ne $Now.ToString('yyyy-MM-dd')) { return $false }
        if ($slotPart -eq 'IMMEDIATE') { return $true }
        if ($slotPart -eq 'MIDDAY') { return ($Minutes -ge 660 -and $Minutes -le 780) }
        if ($slotPart -eq 'EVENING') { return ($Minutes -ge 1140 -and $Minutes -le 1260) }
    }
    return $false
} | Sort-Object created_at

if (-not $candidates -or $candidates.Count -eq 0) { exit 0 }

$job = $candidates[0]
$slot = switch -Regex ([string]$job.slot_key) {
    '\|MIDDAY$' { 'midday'; break }
    '\|EVENING$' { 'evening'; break }
    default { 'immediate' }
}

@{
    job_id = [string]$job.id
    slot_key = [string]$job.slot_key
    started_at = [DateTimeOffset]::Now.ToString('o')
} | ConvertTo-Json | Set-Content -Path $LockPath -Encoding UTF8

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Runner -Slot $slot
    exit $LASTEXITCODE
} finally {
    Remove-Item $LockPath -Force -ErrorAction SilentlyContinue
}
