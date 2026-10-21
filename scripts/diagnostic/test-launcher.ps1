# Non-destructive launcher verification from worktree.
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $here "..\..\launcher\windows"
. (Join-Path $launcher "config.ps1")
. (Join-Path $launcher "ProcessHelpers.ps1")
$cfg = Get-HeyCanvasConfig

$log = @()

function Note([string]$msg) { $log += $msg; Write-Host $msg }

Note "=== Launcher diagnostic $(Get-Date -Format o) ==="
Note "Repo: $($cfg.RepoRoot)"
Note "Venv exists: $(Test-Path $cfg.VenvPython)"
Note "node_modules exists: $(Test-Path (Join-Path $cfg.FrontendDir 'node_modules'))"

$ollama = Test-OllamaReachable -BaseUrl $cfg.OllamaUrl
Note "Ollama reachable: $ollama"

foreach ($port in @($cfg.BackendPort, $cfg.FrontendPort)) {
    $owner = Get-ListeningProcessId -Port $port
    Note "Port $port listener PID: $(if ($owner) { $owner } else { 'none' })"
}

# Stop if state exists
& (Join-Path $launcher "Stop-HeyCanvas.ps1") 2>&1 | ForEach-Object { Note $_ }

# Missing venv start should fail clearly
if (-not (Test-Path $cfg.VenvPython)) {
    try {
        & (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser 2>&1 | Out-Null
        Note "Start without venv: UNEXPECTED success"
    } catch {
        Note "Start without venv: expected failure (venv missing)"
    }
}

# Shortcut script dry-run path check
$shortcutScript = Join-Path $launcher "Create-HeyCanvasShortcut.ps1"
Note "Shortcut script exists: $(Test-Path $shortcutScript)"

# Log redirect fix sanity (stdout/stderr must differ for Start-Process)
$startContent = Get-Content (Join-Path $launcher "Start-HeyCanvas.ps1") -Raw
Note "Start uses separate err logs: $(($startContent -match 'backend\.err\.log') -and ($startContent -match 'frontend\.err\.log'))"

$out = Join-Path $cfg.RunDir "launcher-test-log.txt"
$log | Set-Content $out -Encoding UTF8
Note "Wrote $out"
