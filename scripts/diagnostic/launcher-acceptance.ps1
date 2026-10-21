# Executable launcher acceptance checks (isolated ports; restores state).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $here "..\..\launcher\windows"
. (Join-Path $launcher "config.ps1")
. (Join-Path $launcher "ProcessHelpers.ps1")

$backendPort = 18180
$frontendPort = 13101
$env:HEY_CANVAS_BACKEND_PORT = "$backendPort"
$env:HEY_CANVAS_FRONTEND_PORT = "$frontendPort"
$cfg = Get-HeyCanvasConfig

function Test-HttpOk([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
    } catch {
        return $false
    }
}

$results = @()
function Pass([string]$name) { $results += "PASS $name"; Write-Host "PASS $name" -ForegroundColor Green }
function Fail([string]$name, [string]$why) {
    $results += "FAIL ${name} - $why"
    Write-Host "FAIL ${name} - $why" -ForegroundColor Red
}

if (-not (Test-Path $cfg.VenvPython)) {
    Fail "venv" "missing $($cfg.VenvPython)"
    $results | Set-Content (Join-Path $cfg.RunDir "launcher-acceptance.txt") -Encoding UTF8
    exit 1
}

& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null

# Stale process state (dead PIDs) must not block a fresh start
Remove-Item (Join-Path $cfg.RunDir "start.lock") -Force -ErrorAction SilentlyContinue
$staleState = @{
    frontendPid = 999999
    backendPid  = 999998
    startedAt   = "2020-01-01T00:00:00Z"
} | ConvertTo-Json
Set-Content -Path $cfg.StateFile -Value $staleState -Encoding UTF8
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser | Out-Null
if (Test-HttpOk -Url "$($cfg.BackendUrl)/health") { Pass "stale_process_state" } else { Fail "stale_process_state" "health failed with stale state file" }
& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 2

# Stale lock older than 120s should be ignored
$lock = Join-Path $cfg.RunDir "start.lock"
Set-Content -Path $lock -Value "stale" -Encoding UTF8
(Get-Item $lock).LastWriteTime = (Get-Date).AddMinutes(-5)
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser | Out-Null
if (Test-Path $lock) { Fail "stale_lock" "lock not cleared after successful start" } else { Pass "stale_lock" }

Start-Sleep -Seconds 2
if (-not (Test-HttpOk -Url "$($cfg.BackendUrl)/health")) { Fail "health" "backend not healthy" } else { Pass "health" }

# Repeated start
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser 2>&1 | Out-String | Out-Null
Pass "repeated_start"

# Port conflict on backend
& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 2
$blocker = Start-Process -FilePath $cfg.VenvPython -ArgumentList @(
    "-m", "http.server", "$backendPort", "--bind", "127.0.0.1"
) -WorkingDirectory $cfg.RepoRoot -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5
$owner = Get-ListeningProcessId -Port $backendPort
if (-not $owner) {
    Fail "port_conflict_backend" "blocker did not bind port $backendPort"
} else {
    $startFailed = $false
    try {
        & (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser 2>&1 | Out-Null
    } catch {
        $startFailed = $true
    }
    if ($startFailed) { Pass "port_conflict_backend" } else { Fail "port_conflict_backend" "start succeeded while port occupied" }
}
Stop-ProcessTree -ProcessId $blocker.Id
Start-Sleep -Seconds 2

# Cold restart after stop
Remove-Item (Join-Path $cfg.RunDir "start.lock") -Force -ErrorAction SilentlyContinue
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser | Out-Null
if (Test-HttpOk -Url "$($cfg.FrontendUrl)/startup") { Pass "restart_after_stop" } else { Fail "restart_after_stop" "frontend /startup not OK" }

& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 2
foreach ($port in @($backendPort, $frontendPort)) {
    $owner = Get-ListeningProcessId -Port $port
    if ($owner) { Fail "cleanup_port_$port" "PID $owner still listening" } else { Pass "cleanup_port_$port" }
}

if (Test-OllamaReachable -BaseUrl $cfg.OllamaUrl) { Pass "ollama_reachable" } else { Fail "ollama_reachable" "not reachable" }

# Desktop shortcut target (temp .lnk — no Desktop clutter)
$tmpLnk = Join-Path $env:TEMP "Hey-Canvas-shortcut-acceptance.lnk"
$cmdPath = Join-Path $launcher "Start-HeyCanvas.cmd"
$w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut($tmpLnk)
$s.TargetPath = $cmdPath
$s.WorkingDirectory = $launcher
$s.Save()
$r = $w.CreateShortcut($tmpLnk)
$targetOk = (Resolve-Path $r.TargetPath).Path -eq (Resolve-Path $cmdPath).Path
$workOk = (Resolve-Path $r.WorkingDirectory).Path -eq (Resolve-Path $launcher).Path
if ($targetOk -and $workOk) { Pass "desktop_shortcut" } else { Fail "desktop_shortcut" "unexpected shortcut fields" }
Remove-Item $tmpLnk -Force -ErrorAction SilentlyContinue

# Missing venv must fail without touching the real .venv
$env:HEY_CANVAS_VENV_PYTHON = Join-Path $cfg.RepoRoot ".venv-missing-test\Scripts\python.exe"
& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 1
$missingFailed = $false
try {
    & (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser 2>&1 | Out-Null
} catch {
    $missingFailed = $true
}
Remove-Item Env:HEY_CANVAS_VENV_PYTHON -ErrorAction SilentlyContinue
Remove-Item (Join-Path $cfg.RunDir "start.lock") -Force -ErrorAction SilentlyContinue
if ($missingFailed) { Pass "missing_venv" } else { Fail "missing_venv" "start succeeded without venv" }

# Browser must open only after /startup readiness (static launcher contract)
$launcherSource = Get-Content (Join-Path $launcher "Start-HeyCanvas.ps1") -Raw
$readinessMarker = "Wait-HeyCanvasStartup"
$browserMarker = "Start-Process `$startupUrl"
if ($launcherSource -notmatch [regex]::Escape($readinessMarker)) {
    Fail "browser_after_startup" "missing bounded /startup readiness wait"
} elseif ($launcherSource.IndexOf($browserMarker) -lt $launcherSource.IndexOf($readinessMarker)) {
    Fail "browser_after_startup" "browser open appears before /startup readiness"
} elseif (($launcherSource | Select-String -Pattern "Start-Process.*startup" -AllMatches).Matches.Count -gt 1) {
    Fail "browser_after_startup" "multiple premature browser opens"
} else {
    Pass "browser_after_startup"
}

# Start with Ollama probe skipped (backend/frontend only)
Remove-Item (Join-Path $cfg.RunDir "start.lock") -Force -ErrorAction SilentlyContinue
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser -SkipOllama | Out-Null
if (Test-HttpOk -Url "$($cfg.BackendUrl)/health") { Pass "start_skip_ollama" } else { Fail "start_skip_ollama" "backend unhealthy" }
& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 2

$out = Join-Path $cfg.RunDir "launcher-acceptance.txt"
$results | Set-Content $out -Encoding UTF8
Write-Host "Wrote $out"
if ($results -match "^FAIL") { exit 1 }
