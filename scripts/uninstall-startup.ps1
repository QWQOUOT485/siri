[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$TaskName = 'Siri Windows Agent'
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task Scheduler startup removed: $TaskName" -ForegroundColor Green
} else {
    Write-Host 'No Siri Windows Agent startup task was found.'
}
