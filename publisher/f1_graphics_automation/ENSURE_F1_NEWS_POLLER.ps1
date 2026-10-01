param()

$ErrorActionPreference = 'Stop'
$TaskName = 'F1_News_GitHub_Poller'
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "$TaskName rimosso: F1 e in modalita manual publish-only." -ForegroundColor Yellow
} else {
    Write-Host "$TaskName non presente. Nessun poller grafico da installare." -ForegroundColor Green
}
exit 0
