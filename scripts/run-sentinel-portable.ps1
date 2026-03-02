Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sentinelDir = Join-Path $repoRoot 'apps/sentinel-desktop'
$isWin = $PSVersionTable.Platform -eq 'Win32NT' -or $env:OS -eq 'Windows_NT'
$sentinelPythonRelPath = if ($isWin) { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
$sentinelPython = Join-Path $sentinelDir $sentinelPythonRelPath

if (-not (Test-Path $sentinelPython)) {
    throw 'Missing desktop virtualenv. Run ./scripts/bootstrap-portable.ps1 first.'
}

Push-Location $sentinelDir
try {
    if (-not $isWin) {
        $qtBase = Get-ChildItem -Path (Join-Path $sentinelDir '.venv/lib') -Directory -Filter 'python*' |
            ForEach-Object { Join-Path $_.FullName 'site-packages/PyQt6/Qt6' } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1

        if ($qtBase) {
            $env:QT_PLUGIN_PATH = Join-Path $qtBase 'plugins'
            $env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $qtBase 'plugins/platforms'
            $env:DYLD_FRAMEWORK_PATH = Join-Path $qtBase 'lib'
        }
    }
    & $sentinelPython -m sentinel.main
}
finally {
    Pop-Location
}
