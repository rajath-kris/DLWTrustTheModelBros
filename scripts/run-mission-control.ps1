param(
    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$missionDir = Join-Path $repoRoot 'apps/mission-control'
<<<<<<< Updated upstream
=======
$isWindowsPlatform = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$npmExe = if ($isWindowsPlatform) { 'npm.cmd' } else { 'npm' }
>>>>>>> Stashed changes

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
