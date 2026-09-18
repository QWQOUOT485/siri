[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [switch]$SkipFirewallPrompt,
    [switch]$SkipStartupPrompt
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$EnvFile = Join-Path $Root '.env'

if ($env:OS -ne 'Windows_NT') {
    throw 'This setup script must run on Windows PowerShell.'
}

Write-Host '=== Windows Siri Agent setup ===' -ForegroundColor Cyan
Write-Host "Project: $Root"

$pyCommand = Get-Command py -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pyCommand) {
    $pythonExecutable = $pyCommand.Source
    $pythonPrefix = @('-3')
} elseif ($pythonCommand) {
    $pythonExecutable = $pythonCommand.Source
    $pythonPrefix = @()
} else {
    Write-Host 'Python 3.11+ was not found.' -ForegroundColor Yellow
    Write-Host 'Install it from https://www.python.org/downloads/windows/'
    Write-Host 'After confirmation, you may use: winget install Python.Python.3.12'
    throw 'Python is not installed.'
}

$versionText = (& $pythonExecutable @pythonPrefix -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')").Trim()
try { $version = [version]$versionText } catch { throw "Could not read Python version: $versionText" }
if ($version -lt [version]'3.11') { throw "Python 3.11+ is required; found $versionText." }
Write-Host "Python $versionText OK" -ForegroundColor Green

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host 'Creating .venv ...'
    & $pythonExecutable @pythonPrefix -m venv $Venv
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath (Join-Path $Root '.env.example') -Destination $EnvFile
    $generatedKey = (& $VenvPython -c 'import secrets; print(secrets.token_urlsafe(32))').Trim()
    $envText = Get-Content -LiteralPath $EnvFile -Raw
    $envText = $envText -replace 'SIRI_AGENT_API_KEY=replace-with-a-random-secret-generated-by-setup', "SIRI_AGENT_API_KEY=$generatedKey"
    Set-Content -LiteralPath $EnvFile -Value $envText -Encoding UTF8 -NoNewline
    Write-Host 'Generated a new API key in .env (the key is not printed).' -ForegroundColor Green
} else {
    Write-Host '.env already exists; keeping the current API key.'
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root 'runtime'), (Join-Path $Root 'logs') | Out-Null

if (-not $SkipDependencyInstall) {
    Write-Host 'Installing Python dependencies ...'
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $Root 'requirements.txt')
}

Write-Host 'Running self-test and application discovery ...'
Push-Location $Root
try {
    & $VenvPython -m app.cli --self-test
    if ($LASTEXITCODE -ne 0) { throw 'Self-test failed.' }
} finally {
    Pop-Location
}

$port = 8000
$envLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^SIRI_AGENT_PORT=' } | Select-Object -First 1
if ($envLine -match '^SIRI_AGENT_PORT=(\d+)') { $port = [int]$Matches[1] }

$profiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
if ($profiles | Where-Object { $_.NetworkCategory -eq 'Public' }) {
    Write-Host 'WARNING: a network profile is Public. Change your trusted home network to Private; this script will not change it.' -ForegroundColor Yellow
}

if (-not $SkipFirewallPrompt) {
    $answer = Read-Host "Create a Private-only TCP $port Windows Firewall rule for RFC1918 networks? (y/N)"
    if ($answer -match '^(y|yes)$') {
        $ruleName = 'Siri Windows Agent'
        try {
            Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -Profile Private -RemoteAddress @('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16') | Out-Null
            Write-Host 'Firewall rule created: Private profile only.' -ForegroundColor Green
        } catch {
            Write-Warning "Firewall rule creation failed. Run PowerShell as Administrator if needed: $($_.Exception.Message)"
        }
    } else {
        Write-Host 'Firewall rule skipped.' -ForegroundColor Yellow
    }
}

if (-not $SkipStartupPrompt) {
    $startupAnswer = Read-Host 'Enable Task Scheduler At log on for the current interactive user? (y/N)'
    if ($startupAnswer -match '^(y|yes)$') {
        try {
            & (Join-Path $PSScriptRoot 'install-startup.ps1') -PythonPath $VenvPython
        } catch {
            Write-Warning "Task Scheduler registration failed: $($_.Exception.Message)"
        }
    } else {
        Write-Host 'Automatic startup skipped.'
    }
}

$privateIps = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)' } | Select-Object -ExpandProperty IPAddress -Unique)
Write-Host ''
Write-Host '=== Setup complete ===' -ForegroundColor Green
Write-Host 'Manual start: double-click scripts\start.bat (Ctrl+C stops it).'
Write-Host 'Health URLs:'
foreach ($ip in $privateIps) { Write-Host "  http://${ip}:$port/health" }
Write-Host 'If no IP is listed, run ipconfig.'
Write-Host 'Next: use the Windows address and API key in README.md to create the iPhone Shortcut.'
