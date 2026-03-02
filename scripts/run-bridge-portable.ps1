Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$isWin = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$bridgePythonRelPath = if ($isWin) { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
$bridgePython = Join-Path $bridgeDir $bridgePythonRelPath

if (-not (Test-Path $bridgePython)) {
    throw 'Missing bridge virtualenv. Run ./scripts/bootstrap-portable.ps1 first.'
}

Push-Location $bridgeDir
try {
    & $bridgePython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}
