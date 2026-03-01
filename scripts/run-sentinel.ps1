Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$sentinelPython = Join-Path $sentinelDir '.venv/Scripts/python.exe'

if (-not (Test-Path $sentinelPython)) {
    throw 'Missing desktop virtualenv. Run .\scripts\bootstrap.ps1 first.'
}

Push-Location $sentinelDir
try {
    & $sentinelPython -m sentinel.main
}
finally {
    Pop-Location
}
