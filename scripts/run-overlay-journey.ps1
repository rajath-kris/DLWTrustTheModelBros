param(
    [ValidateSet("success_fast", "success_slow", "http_500", "timeout", "malformed", "flaky")]
    [string]$Scenario = "success_fast",
    [switch]$SkipBootstrap,
    [string]$ReportDir = "artifacts/overlay-journey",
    [int]$Port = 8011
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 15
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 2
            if ($resp.status -eq 'ok') {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    return $false
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeUrl = "http://127.0.0.1:$Port"

$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$sentinelPython = Join-Path $sentinelDir '.venv/Scripts/python.exe'
$mockScript = Join-Path $repoRoot 'scripts/mock_bridge.py'
$reportScript = Join-Path $repoRoot 'scripts/overlay_journey_report.py'

if (-not $SkipBootstrap) {
    Write-Host "Bootstrapping Python environments (SkipNode=true)..."
    & (Join-Path $repoRoot 'scripts/bootstrap.ps1') -SkipNode
}

if (-not (Test-Path $sentinelPython)) {
    throw 'Missing desktop virtualenv python. Run .\scripts\bootstrap.ps1 first.'
}

$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $repoRoot (Join-Path $ReportDir $runStamp)
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$sentinelLog = Join-Path $runDir 'raw-sentinel.log'
$sentinelErrLog = Join-Path $runDir 'raw-sentinel.err.log'
$bridgeLog = Join-Path $runDir 'raw-mock-bridge.log'
$bridgeErrLog = Join-Path $runDir 'raw-mock-bridge.err.log'
$timelinePath = Join-Path $runDir 'timeline.json'
$reportPath = Join-Path $runDir 'session-report.md'

$mockProc = $null
$sentinelProc = $null
$timelineProc = $null

try {
    Write-Host "Starting mock bridge on $bridgeUrl ($Scenario)..."
    $mockProc = Start-Process `
        -FilePath $sentinelPython `
        -ArgumentList @("""$mockScript""", '--host', '127.0.0.1', '--port', "$Port", '--scenario', $Scenario) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -RedirectStandardOutput $bridgeLog `
        -RedirectStandardError $bridgeErrLog `
        -PassThru

    if (-not (Wait-ForHealth -Url "$bridgeUrl/healthz" -TimeoutSeconds 20)) {
        throw "Mock bridge did not become healthy at $bridgeUrl/healthz"
    }

    Write-Host 'Starting sentinel desktop in test mode...'
    $oldBridge = $env:SENTINEL_BRIDGE_URL
    $oldTestMode = $env:SENTINEL_TEST_MODE
    $oldLocalTrigger = $env:SENTINEL_LOCAL_TRIGGER_ENABLED
    $oldLocalTriggerKey = $env:SENTINEL_LOCAL_TRIGGER_KEY
    $oldScenarioLabel = $env:SENTINEL_TEST_SCENARIO_LABEL
    $oldUnbuffered = $env:PYTHONUNBUFFERED

    $env:SENTINEL_BRIDGE_URL = $bridgeUrl
    $env:SENTINEL_TEST_MODE = '1'
    $env:SENTINEL_LOCAL_TRIGGER_ENABLED = '1'
    $env:SENTINEL_LOCAL_TRIGGER_KEY = 'Ctrl+Shift+S'
    $env:SENTINEL_TEST_SCENARIO_LABEL = $Scenario
    $env:PYTHONUNBUFFERED = '1'

    $sentinelProc = Start-Process `
        -FilePath $sentinelPython `
        -ArgumentList @('-m', 'sentinel.main') `
        -WorkingDirectory $sentinelDir `
        -NoNewWindow `
        -RedirectStandardOutput $sentinelLog `
        -RedirectStandardError $sentinelErrLog `
        -PassThru

    $env:SENTINEL_BRIDGE_URL = $oldBridge
    $env:SENTINEL_TEST_MODE = $oldTestMode
    $env:SENTINEL_LOCAL_TRIGGER_ENABLED = $oldLocalTrigger
    $env:SENTINEL_LOCAL_TRIGGER_KEY = $oldLocalTriggerKey
    $env:SENTINEL_TEST_SCENARIO_LABEL = $oldScenarioLabel
    $env:PYTHONUNBUFFERED = $oldUnbuffered

    Start-Sleep -Milliseconds 800
    if ($sentinelProc.HasExited) {
        throw "Sentinel desktop exited early. Check $sentinelErrLog"
    }

    Write-Host 'Starting live timeline stream...'
    $timelineProc = Start-Process `
        -FilePath $sentinelPython `
        -ArgumentList @(
            """$reportScript""",
            '--follow',
            '--sentinel-log', """$sentinelLog""",
            '--bridge-log', """$bridgeLog""",
            '--timeline-out', """$timelinePath"""
        ) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    Write-Host ''
    Write-Host 'Overlay Journey Instructions'
    Write-Host '1. Trigger capture with Alt+S or Journey Control button.'
    Write-Host "2. Drag-select a region, then click the input area and submit one reply with Send."
    Write-Host "3. Observe prompt -> analyzing -> prompt loop and input telemetry in timeline."
    Write-Host "4. Press Esc to verify dismiss behavior."
    Write-Host "5. To force a failure mid-run, switch scenario:"
    Write-Host "   Invoke-RestMethod -Method Post -Uri $bridgeUrl/__scenario -ContentType 'application/json' -Body '{`"scenario`":`"http_500`"}'"
    Write-Host "6. Click Retry on overlay to test retry after an input turn."
    Write-Host ''
    Read-Host 'Press Enter when your user journey is complete'
}
finally {
    foreach ($proc in @($timelineProc, $sentinelProc, $mockProc)) {
        if ($null -ne $proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force
        }
    }
}

Write-Host 'Generating timeline and session report...'
& $sentinelPython "$reportScript" `
    --sentinel-log $sentinelLog `
    --bridge-log $bridgeLog `
    --timeline-out $timelinePath `
    --report-out $reportPath `
    --scenario $Scenario | Out-Host

Write-Host ''
Write-Host "Journey complete."
Write-Host "Artifacts: $runDir"
Write-Host " - $sentinelLog"
Write-Host " - $bridgeLog"
Write-Host " - $timelinePath"
Write-Host " - $reportPath"
