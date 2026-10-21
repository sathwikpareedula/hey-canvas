# Measure Hey Canvas startup phases (bounded, isolated ports).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$launcher = Join-Path $root "launcher\windows"
$runDir = Join-Path $root ".hey-canvas\run"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$env:HEY_CANVAS_BACKEND_PORT = "18195"
$env:HEY_CANVAS_FRONTEND_PORT = "13195"
. (Join-Path $launcher "config.ps1")
. (Join-Path $launcher "ProcessHelpers.ps1")
$cfg = Get-HeyCanvasConfig

$phases = [ordered]@{}
$sw = [System.Diagnostics.Stopwatch]::StartNew()

function Mark([string]$Name) {
    $phases[$Name] = [int]$sw.ElapsedMilliseconds
}

try {
    & (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
    Start-Sleep -Seconds 1
    Mark "stop_cleanup"

    & (Join-Path $PSScriptRoot "ollama_http_probe.ps1") -TimeoutSec 5 | Out-Null
    Mark "ollama_http_probe"

    & (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser -SkipOllama | Out-Null
    Mark("launcher_returned")

    for ($i = 0; $i -lt 120; $i++) {
        try {
            $h = Invoke-WebRequest -Uri "$($cfg.BackendUrl)/health" -UseBasicParsing -TimeoutSec 2
            if ($h.StatusCode -eq 200) { Mark("backend_health"); break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }

    for ($i = 0; $i -lt 180; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "$($cfg.FrontendUrl)/startup" -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400 -and $r.Content -match "Hey Canvas") {
                Mark("startup_page_ready")
                break
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
} finally {
    & (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
    $sw.Stop()
    $phases["total_ms"] = [int]$sw.ElapsedMilliseconds
    $out = Join-Path $runDir "startup-timing.json"
    $phases | ConvertTo-Json | Set-Content -Path $out -Encoding UTF8
    $phases | ConvertTo-Json -Compress
}
