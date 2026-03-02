param(
    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$missionDir = Join-Path $repoRoot 'apps/mission-control'
$isWin = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$npmExe = if ($isWin) { 'npm.cmd' } else { 'npm' }

Push-Location $missionDir
try {
    if ($Install -or -not (Test-Path (Join-Path $missionDir 'node_modules'))) {
        & $npmExe install
    }
    & $npmExe run dev
}
finally {
    Pop-Location
}
