param(
    [switch]$Install,
    [string]$BridgeBaseUrl = 'http://127.0.0.1:8000',
    [string]$DevHost = '127.0.0.1',
    [int]$Port = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$missionDir = Join-Path $repoRoot 'apps/mission-control'
$npmExe = 'npm.cmd'

Push-Location $missionDir
try {
    if ($Install -or -not (Test-Path (Join-Path $missionDir 'node_modules'))) {
        & $npmExe install
    }
    & $npmExe run dev -- --host $DevHost --port $Port
}
finally {
    try {
        $stopUrl = "$($BridgeBaseUrl.TrimEnd('/'))/api/v1/sentinel/runtime/stop"
        Invoke-RestMethod -Uri $stopUrl -Method Post -TimeoutSec 2 | Out-Null
        Write-Host "[run-mission-control] Requested Sentinel runtime stop on Mission Control shutdown."
    }
    catch {
        # Best effort cleanup only.
    }
    Pop-Location
}
