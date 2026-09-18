[CmdletBinding()]
param(
    [switch]$RemoveRuntimeData,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$RuleName = 'Siri Windows Agent'

if (-not $Force) {
    $answer = Read-Host 'Remove the Task Scheduler and Firewall settings? Code, .env, and config will be kept by default. (y/N)'
    if ($answer -notmatch '^(y|yes)$') { Write-Host 'Cancelled.'; exit 0 }
}

try { & (Join-Path $PSScriptRoot 'uninstall-startup.ps1') } catch { Write-Warning "Task Scheduler removal failed: $($_.Exception.Message)" }
try {
    Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    Write-Host 'Firewall rule removed if it existed.'
} catch {
    Write-Warning "Firewall rule removal failed; Administrator PowerShell may be required: $($_.Exception.Message)"
}

if ($RemoveRuntimeData) {
    $runtime = Join-Path $Root 'runtime'
    $logs = Join-Path $Root 'logs'
    if (Test-Path -LiteralPath $runtime) { Get-ChildItem -LiteralPath $runtime -Force | Remove-Item -Force -Recurse }
    if (Test-Path -LiteralPath $logs) { Get-ChildItem -LiteralPath $logs -Force | Remove-Item -Force -Recurse }
    Write-Host 'Runtime and log contents removed; .env, config, and source remain.'
}

Write-Host 'Uninstall settings complete. Keep the project folder unless you no longer need the source and local configuration.'
