param(
    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$missionDir = Join-Path $repoRoot 'apps/mission-control'

Push-Location $missionDir
try {
    if ($Install -or -not (Test-Path (Join-Path $missionDir 'node_modules'))) {
        npm install
    }
    npm run dev
}
finally {
    Pop-Location
}
