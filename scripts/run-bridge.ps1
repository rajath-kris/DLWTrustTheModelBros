Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$bridgePython = Join-Path $bridgeDir '.venv/Scripts/python.exe'
$defaultScoraticScript = Join-Path $repoRoot 'scripts/sentinel_brain (1).py'

if (-not (Test-Path $bridgePython)) {
    throw 'Missing bridge virtualenv. Run .\scripts\bootstrap.ps1 first.'
}

Push-Location $bridgeDir
try {
    if ([string]::IsNullOrWhiteSpace($env:SENTINEL_SCORATIC_SCRIPT_PATH) -and (Test-Path $defaultScoraticScript)) {
        $env:SENTINEL_SCORATIC_SCRIPT_PATH = $defaultScoraticScript
    }
    & $bridgePython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}
