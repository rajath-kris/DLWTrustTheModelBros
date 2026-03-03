param(
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string]$Action = 'restart',
    [switch]$EnsureBootstrap,
    [int]$BridgePort = 8000,
    [int]$MissionControlPort = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bridgeDir = Join-Path $repoRoot 'services/bridge-api'
$missionDir = Join-Path $repoRoot 'apps/mission-control'
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'

$bridgePython = Join-Path $bridgeDir '.venv/Scripts/python.exe'
$sentinelPython = Join-Path $sentinelDir '.venv/Scripts/python.exe'
$powershellExe = 'powershell.exe'
$missionLauncher = Join-Path $PSScriptRoot 'run-mission-control.ps1'

$runtimeRoot = Join-Path $repoRoot 'artifacts/stack-runtime'
$runtimeMeta = Join-Path $runtimeRoot 'stack-processes.json'

function Invoke-BootstrapIfNeeded {
    if (-not $EnsureBootstrap) {
        return
    }
    Write-Host '[run-demo-stack] Running bootstrap...'
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}

function Read-Metadata {
    if (-not (Test-Path $runtimeMeta)) {
        return $null
    }
    try {
        return (Get-Content $runtimeMeta -Raw | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Write-Metadata([hashtable]$payload) {
    $runtimeDir = Split-Path -Parent $runtimeMeta
    if (-not (Test-Path $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content $runtimeMeta -Encoding UTF8
}

function Remove-Metadata {
    if (Test-Path $runtimeMeta) {
        Remove-Item $runtimeMeta -Force
    }
}

function Stop-ManagedProcess([int]$processId, [string]$name) {
    if ($processId -le 0) {
        return
    }
    try {
        $proc = Get-Process -Id $processId -ErrorAction Stop
        Write-Host "[run-demo-stack] Stopping $name (pid=$processId)"
        Stop-Process -Id $proc.Id -Force
    }
    catch {
        # Already stopped.
    }
}

function Stop-FromMetadata {
    $meta = Read-Metadata
    if ($null -eq $meta) {
        return
    }
    foreach ($entry in @($meta.processes)) {
        $pidValue = 0
        try {
            $pidValue = [int]$entry.pid
        }
        catch {
            $pidValue = 0
        }
        Stop-ManagedProcess -processId $pidValue -name ([string]$entry.name)
    }
}

function Get-PortPids([int]$port) {
    try {
        return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique)
    }
    catch {
        return @()
    }
}

function Test-PortInUse([int]$port) {
    return ((@((Get-PortPids -port $port))).Count -gt 0)
}

function Select-LaunchPort([int]$preferredPort, [int[]]$fallbackPorts) {
    if (-not (Test-PortInUse -port $preferredPort)) {
        return $preferredPort
    }
    foreach ($candidate in $fallbackPorts) {
        if (-not (Test-PortInUse -port $candidate)) {
            Write-Host "[run-demo-stack] Port $preferredPort is busy; using fallback port $candidate."
            return $candidate
        }
    }
    throw "No free port available. Preferred port $preferredPort is in use and no fallback ports were free."
}

function Stop-PortListeners([int[]]$ports) {
    $allPids = @()
    foreach ($port in $ports) {
        $allPids += Get-PortPids -port $port
    }
    $uniquePids = $allPids | Where-Object { $_ -gt 0 } | Select-Object -Unique
    foreach ($listenerPid in $uniquePids) {
        Stop-ManagedProcess -processId ([int]$listenerPid) -name 'port-listener'
    }
    if ((@($uniquePids)).Count -gt 0) {
        Start-Sleep -Milliseconds 800
    }
}

function Wait-HttpReady([string]$url, [int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 2 -UseBasicParsing
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

function Assert-Prereqs {
    if (-not (Test-Path $bridgePython)) {
        throw "Missing bridge venv at $bridgePython. Run .\scripts\bootstrap.ps1"
    }
    if (-not (Test-Path $sentinelPython)) {
        throw "Missing sentinel venv at $sentinelPython. Run .\scripts\bootstrap.ps1"
    }
    if (-not (Test-Path (Join-Path $missionDir 'node_modules'))) {
        throw "Missing mission-control node_modules. Run .\scripts\bootstrap.ps1"
    }
    if (-not (Test-Path $missionLauncher)) {
        throw "Missing mission-control launcher at $missionLauncher."
    }
}

function Start-Stack {
    Invoke-BootstrapIfNeeded
    Assert-Prereqs

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $runDir = Join-Path $runtimeRoot $timestamp
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null

    Write-Host '[run-demo-stack] Cleaning old processes...'
    Stop-FromMetadata
    Stop-PortListeners -ports @($BridgePort, $MissionControlPort, 18000, 15173)

    $resolvedBridgePort = Select-LaunchPort -preferredPort $BridgePort -fallbackPorts @(18000, 28000, 38000)
    $resolvedMissionPort = Select-LaunchPort -preferredPort $MissionControlPort -fallbackPorts @(15173, 25173, 35173)
    $resolvedBridgeHealthUrl = "http://127.0.0.1:$resolvedBridgePort/healthz"
    $resolvedMissionUrl = "http://127.0.0.1:$resolvedMissionPort"
    $resolvedBridgeUrl = "http://127.0.0.1:$resolvedBridgePort"

    # Ensure launched processes (bridge + runtime-managed Sentinel) agree on the active bridge URL/port.
    $env:BRIDGE_HOST = '127.0.0.1'
    $env:BRIDGE_PORT = $resolvedBridgePort.ToString()
    $env:SENTINEL_BRIDGE_URL = $resolvedBridgeUrl
    $env:VITE_API_BASE_URL = $resolvedBridgeUrl

    $bridgeLog = Join-Path $runDir 'bridge.log'
    $bridgeErr = Join-Path $runDir 'bridge.err.log'
    $missionLog = Join-Path $runDir 'mission-control.log'
    $missionErr = Join-Path $runDir 'mission-control.err.log'
    $sentinelLog = Join-Path $runDir 'sentinel.log'
    $sentinelErr = Join-Path $runDir 'sentinel.err.log'

    Write-Host '[run-demo-stack] Starting bridge...'
    $bridgeProc = Start-Process -FilePath $bridgePython `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', $resolvedBridgePort.ToString()) `
        -WorkingDirectory $bridgeDir `
        -RedirectStandardOutput $bridgeLog `
        -RedirectStandardError $bridgeErr `
        -PassThru

    if (-not (Wait-HttpReady -url $resolvedBridgeHealthUrl -timeoutSeconds 30)) {
        throw "Bridge did not become healthy in time. Check $bridgeErr"
    }

    $env:VITE_API_BASE_URL = $resolvedBridgeUrl
    $env:SENTINEL_BRIDGE_URL = $resolvedBridgeUrl

    Write-Host '[run-demo-stack] Starting Mission Control...'
    $quotedMissionLauncher = ('"{0}"' -f $missionLauncher)
    $missionProc = Start-Process -FilePath $powershellExe `
        -ArgumentList @(
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $quotedMissionLauncher,
            '-BridgeBaseUrl',
            "http://127.0.0.1:$resolvedBridgePort",
            '-DevHost',
            '127.0.0.1',
            '-Port',
            $resolvedMissionPort.ToString()
        ) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $missionLog `
        -RedirectStandardError $missionErr `
        -PassThru

    if (-not (Wait-HttpReady -url $resolvedMissionUrl -timeoutSeconds 45)) {
        throw "Mission Control did not become ready in time. Check $missionErr"
    }

    Write-Host '[run-demo-stack] Starting Sentinel desktop...'
    $sentinelProc = Start-Process -FilePath $sentinelPython `
        -ArgumentList @('-m', 'sentinel.main') `
        -WorkingDirectory $sentinelDir `
        -RedirectStandardOutput $sentinelLog `
        -RedirectStandardError $sentinelErr `
        -PassThru

    Write-Metadata @{
        started_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        run_dir = $runDir
        bridge_port = $resolvedBridgePort
        mission_control_port = $resolvedMissionPort
        bridge_url = "http://127.0.0.1:$resolvedBridgePort"
        mission_control_url = "http://127.0.0.1:$resolvedMissionPort"
        processes = @(
            @{ name = 'bridge'; pid = $bridgeProc.Id; log = $bridgeLog; err = $bridgeErr },
            @{ name = 'mission-control'; pid = $missionProc.Id; log = $missionLog; err = $missionErr },
            @{ name = 'sentinel'; pid = $sentinelProc.Id; log = $sentinelLog; err = $sentinelErr }
        )
    }

    Write-Host 'stack_started=true'
    Write-Host "run_dir=$runDir"
    Write-Host "bridge_pid=$($bridgeProc.Id)"
    Write-Host "mission_control_pid=$($missionProc.Id)"
    Write-Host "sentinel_pid=$($sentinelProc.Id)"
    Write-Host "bridge_url=http://127.0.0.1:$resolvedBridgePort"
    Write-Host "mission_control_url=http://127.0.0.1:$resolvedMissionPort"
}

function Stop-Stack {
    Write-Host '[run-demo-stack] Stopping managed processes...'
    $meta = Read-Metadata
    Stop-FromMetadata
    $portsToStop = @($BridgePort, $MissionControlPort, 18000, 15173)
    if ($null -ne $meta) {
        try {
            $portsToStop += [int]$meta.bridge_port
        }
        catch {
            # Ignore missing bridge_port in older metadata files.
        }
        try {
            $portsToStop += [int]$meta.mission_control_port
        }
        catch {
            # Ignore missing mission_control_port in older metadata files.
        }
    }
    Stop-PortListeners -ports ($portsToStop | Select-Object -Unique)
    Remove-Metadata
    Write-Host 'stack_stopped=true'
}

function Show-Status {
    $meta = Read-Metadata
    $statusBridgePort = $BridgePort
    $statusMissionPort = $MissionControlPort
    if ($null -ne $meta) {
        try {
            $statusBridgePort = [int]$meta.bridge_port
        }
        catch {
            $statusBridgePort = $BridgePort
        }
        try {
            $statusMissionPort = [int]$meta.mission_control_port
        }
        catch {
            $statusMissionPort = $MissionControlPort
        }
    }
    $statusBridgeHealth = "http://127.0.0.1:$statusBridgePort/healthz"
    $statusMissionUrl = "http://127.0.0.1:$statusMissionPort"
    $bridgeReady = Wait-HttpReady -url $statusBridgeHealth -timeoutSeconds 2
    $missionReady = Wait-HttpReady -url $statusMissionUrl -timeoutSeconds 2

    if ($null -eq $meta) {
        Write-Host "repo_root=$repoRoot"
        Write-Host 'managed_processes=none'
        Write-Host "bridge_url=http://127.0.0.1:$statusBridgePort"
        Write-Host "mission_control_url=http://127.0.0.1:$statusMissionPort"
        Write-Host "bridge_health=$bridgeReady"
        Write-Host "mission_control_http=$missionReady"
        return
    }

    Write-Host "repo_root=$repoRoot"
    Write-Host "run_dir=$($meta.run_dir)"
    Write-Host "bridge_url=http://127.0.0.1:$statusBridgePort"
    Write-Host "mission_control_url=http://127.0.0.1:$statusMissionPort"
    Write-Host 'processes:'
    foreach ($entry in @($meta.processes)) {
        $alive = $false
        $pidValue = [int]$entry.pid
        try {
            Get-Process -Id $pidValue -ErrorAction Stop | Out-Null
            $alive = $true
        }
        catch {
            $alive = $false
        }
        Write-Host "  - $($entry.name): pid=$pidValue alive=$alive"
    }
    Write-Host "bridge_health=$bridgeReady"
    Write-Host "mission_control_http=$missionReady"
}

switch ($Action) {
    'start' {
        Start-Stack
    }
    'stop' {
        Stop-Stack
    }
    'status' {
        Show-Status
    }
    'restart' {
        Stop-Stack
        Start-Stack
    }
    default {
        throw "Unsupported action: $Action"
    }
}
