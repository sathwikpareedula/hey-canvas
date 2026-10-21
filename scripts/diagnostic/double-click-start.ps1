# Simulate student double-click Start-HeyCanvas.cmd (bounded, isolated ports).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$launcher = Join-Path $root "launcher\windows"
$cmd = Join-Path $launcher "Start-HeyCanvas.cmd"
$runDir = Join-Path $root ".hey-canvas\run"

$env:HEY_CANVAS_BACKEND_PORT = "18193"
$env:HEY_CANVAS_FRONTEND_PORT = "13193"

function Test-HttpOk([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
    } catch { return $false }
}

. (Join-Path $launcher "config.ps1")
. (Join-Path $launcher "ProcessHelpers.ps1")
$cfg = Get-HeyCanvasConfig

$result = @{
    first_start_ok = $false
    second_start_ok = $false
    health_ok = $false
    startup_page_ok = $false
    duplicate_backend = $false
}

try {
    & (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
    Start-Sleep -Seconds 2

    $p1 = Start-Process -FilePath $cmd -WorkingDirectory $launcher -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    $p2 = Start-Process -FilePath $cmd -WorkingDirectory $launcher -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url "$($cfg.BackendUrl)/health") {
            $result.first_start_ok = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    Start-Sleep -Seconds 2
    $result.second_start_ok = $true
    $pageDeadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $pageDeadline) {
        $result.health_ok = Test-HttpOk -Url "$($cfg.BackendUrl)/health"
        try {
            $r = Invoke-WebRequest -Uri "$($cfg.FrontendUrl)/startup" -UseBasicParsing -TimeoutSec 10
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) {
                $result.startup_page_ok = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 2
    }
    $owners = @(Get-NetTCPConnection -LocalPort $cfg.BackendPort -State Listen -ErrorAction SilentlyContinue)
    $result.duplicate_backend = ($owners.Count -gt 1)
} finally {
    & (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
    if ($p1 -and -not $p1.HasExited) { Stop-Process -Id $p1.Id -Force -ErrorAction SilentlyContinue }
    if ($p2 -and -not $p2.HasExited) { Stop-Process -Id $p2.Id -Force -ErrorAction SilentlyContinue }
}

$out = Join-Path $runDir "double-click-start.json"
$result | ConvertTo-Json | Set-Content -Path $out -Encoding UTF8
$result | ConvertTo-Json -Compress
if (-not ($result.health_ok -and $result.startup_page_ok -and -not $result.duplicate_backend)) { exit 1 }
exit 0
