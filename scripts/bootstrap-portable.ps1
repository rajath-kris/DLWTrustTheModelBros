param(
    [switch]$SkipNode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$missionDir = Join-Path $repoRoot 'apps/mission-control'

$isWin = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$venvPythonRelPath = if ($isWin) { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
$npmExe = if ($isWin) { 'npm.cmd' } else { 'npm' }

$pythonLauncher = if ($isWin) {
    if (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
    else { throw 'Python was not found on PATH.' }
} else {
    if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
    else { throw 'Python was not found on PATH.' }
}

$envFile = Join-Path $repoRoot '.env'
$envExample = Join-Path $repoRoot '.env.example'
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host 'Created .env from .env.example'
}

$bridgePython = Join-Path $bridgeDir $venvPythonRelPath
if (-not (Test-Path $bridgePython)) {
    & $pythonLauncher -m venv (Join-Path $bridgeDir '.venv')
}
& $bridgePython -m pip install -r (Join-Path $bridgeDir 'requirements.txt')

$sentinelPython = Join-Path $sentinelDir $venvPythonRelPath
if (-not (Test-Path $sentinelPython)) {
    & $pythonLauncher -m venv (Join-Path $sentinelDir '.venv')
}
& $sentinelPython -m pip install -r (Join-Path $sentinelDir 'requirements.txt')

if (-not $SkipNode) {
    Push-Location $missionDir
    try {
        & $npmExe install
    }
    finally {
        Pop-Location
    }
}

Write-Host 'Bootstrap complete.'
Write-Host 'Run: ./scripts/run-bridge.ps1, ./scripts/run-sentinel.ps1, ./scripts/run-mission-control.ps1'
