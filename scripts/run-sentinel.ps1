Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$isWindowsPlatform = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$venvPythonPath = if ($isWindowsPlatform) { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
$sentinelPython = Join-Path $sentinelDir $venvPythonPath

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
