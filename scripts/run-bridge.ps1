Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$bridgePython = Join-Path $bridgeDir '.venv/Scripts/python.exe'

if (-not (Test-Path $bridgePython)) {
    throw 'Missing bridge virtualenv. Run .\scripts\bootstrap.ps1 first.'
}

Push-Location $bridgeDir
try {
    & $bridgePython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}
