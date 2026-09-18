[CmdletBinding()]
param(
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $Root '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python executable was not found: $PythonPath. Run setup.ps1 first."
}

$TaskName = 'Siri Windows Agent'
$UserId = "$env:USERDOMAIN\$env:USERNAME"
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument '-m app.main' -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $UserId
$Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'LAN-only Windows Siri Agent (interactive user session)' -Force | Out-Null
Write-Host "Task Scheduler startup installed: $TaskName" -ForegroundColor Green
Write-Host 'Trigger: At log on; user: current user; mode: interactive logon; run level: limited.'
