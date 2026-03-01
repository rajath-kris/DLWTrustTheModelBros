param(
    [switch]$SkipNode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$missionDir = Join-Path $repoRoot 'apps/mission-control'

$envFile = Join-Path $repoRoot '.env'
$envExample = Join-Path $repoRoot '.env.example'
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host 'Created .env from .env.example'
}

$bridgePython = Join-Path $bridgeDir '.venv/Scripts/python.exe'
if (-not (Test-Path $bridgePython)) {
    python -m venv (Join-Path $bridgeDir '.venv')
}
& $bridgePython -m pip install -r (Join-Path $bridgeDir 'requirements.txt')

$sentinelPython = Join-Path $sentinelDir '.venv/Scripts/python.exe'
if (-not (Test-Path $sentinelPython)) {
    python -m venv (Join-Path $sentinelDir '.venv')
}
& $sentinelPython -m pip install -r (Join-Path $sentinelDir 'requirements.txt')

if (-not $SkipNode) {
    Push-Location $missionDir
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

Write-Host 'Bootstrap complete.'
Write-Host 'Run: .\scripts\run-bridge.ps1, .\scripts\run-sentinel.ps1, .\scripts\run-mission-control.ps1'
