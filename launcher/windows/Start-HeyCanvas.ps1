# Starts Hey Canvas backend + frontend and opens the startup UI.
param(
    [switch]$NoBrowser,
    [switch]$SkipOllama,
    [switch]$Demo
)

. (Join-Path $PSScriptRoot "config.ps1")
. (Join-Path $PSScriptRoot "ProcessHelpers.ps1")
$cfg = Get-HeyCanvasConfig
$requestedMode = if ($Demo) { "demo" } else { "personal" }

if (-not (Test-Path $cfg.LogDir)) {
    New-Item -ItemType Directory -Path $cfg.LogDir -Force | Out-Null
}

$lockFile = Join-Path $cfg.RunDir "start.lock"
if (Test-Path $lockFile) {
    $lockAge = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($lockAge.TotalSeconds -lt 120) {
        Write-Host "Hey Canvas is already starting (lock file). If this is wrong, delete $lockFile"
        exit 0
    }
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
Set-Content -Path $lockFile -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding UTF8

Write-Host "Hey Canvas is starting..."

function Test-HttpOk([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
    } catch {
        return $false
    }
}

function Test-HeyCanvasStartupPage([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300) { return $false }
        return $r.Content -match "Hey Canvas"
    } catch {
        return $false
    }
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk $Url) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-HeyCanvasStartup([string]$Url, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HeyCanvasStartupPage $Url) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

$state = @{
    backendPid  = $null
    backendProcessStartedAt = $null
    frontendPid = $null
    frontendProcessStartedAt = $null
    ollamaPid   = $null
    mode        = $requestedMode
    startedAt   = (Get-Date).ToUniversalTime().ToString("o")
}

# Demo mode is explicit. Ordinary launches always prefer the real local provider,
# while tests may still set a provider before invoking the launcher.
if ($Demo) {
    $env:ACADEMIC_MODEL_PROVIDER = "synthetic"
    $env:NEXT_PUBLIC_HEY_CANVAS_DEMO = "1"
    $demoDir = Join-Path $cfg.RunDir "demo"
    $demoDatabase = Join-Path $demoDir "hey-canvas-demo.db"
    $demoFiles = Join-Path $demoDir "files"
    New-Item -ItemType Directory -Path $demoDir -Force | Out-Null
    $env:DATABASE_URL = "sqlite:///$($demoDatabase.Replace('\', '/'))"
    $env:ACADEMIC_FILES_ROOT = $demoFiles
    $SkipOllama = $true
} elseif (-not $env:ACADEMIC_MODEL_PROVIDER) {
    $env:ACADEMIC_MODEL_PROVIDER = "ollama"
}
if (-not $env:ASSISTANT_REQUEST_TIMEOUT_SECONDS) {
    $env:ASSISTANT_REQUEST_TIMEOUT_SECONDS = "180"
}

# Local AI runtime (optional bounded start)
if (-not $SkipOllama) {
    if (-not (Test-OllamaReachable -BaseUrl $cfg.OllamaUrl)) {
        $null = Start-OllamaRuntimeIfInstalled -WaitSeconds $cfg.OllamaWaitSec
    }
}
# Default to Ollama when reachable so the launcher matches "Local AI" UX (override via ACADEMIC_MODEL_PROVIDER).
if (-not $env:ACADEMIC_MODEL_PROVIDER -and (Test-OllamaReachable -BaseUrl $cfg.OllamaUrl)) {
    $env:ACADEMIC_MODEL_PROVIDER = "ollama"
}

# Existing listeners must not be adopted just because their HTTP response looks healthy.
# A second checkout or an older version may be running on the same ports.
$verifiedState = $null
if (Test-Path $cfg.StateFile) {
    try {
        $verifiedState = Get-Content $cfg.StateFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction SilentlyContinue
    } catch { }
}

foreach ($entry in @(
    @{ Port = $cfg.BackendPort; Label = "backend"; PidProp = "backendPid"; StartProp = "backendProcessStartedAt" },
    @{ Port = $cfg.FrontendPort; Label = "frontend"; PidProp = "frontendPid"; StartProp = "frontendProcessStartedAt" }
)) {
    $existingOwner = Get-ListeningProcessId -Port $entry.Port
    if ($existingOwner) {
        $runningMode = if ($verifiedState -and $verifiedState.mode) { [string]$verifiedState.mode } else { "personal" }
        if ($runningMode -ne $requestedMode) {
            Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
            throw "Hey Canvas is already running in $runningMode mode. Stop it before starting $requestedMode mode."
        }
        $isVerified = $false
        if ($verifiedState -and $verifiedState.($entry.PidProp)) {
            $rootPid = [int]$verifiedState.($entry.PidProp)
            $expectedStart = $verifiedState.($entry.StartProp)
            if (
                (Test-ProcessStartTimeMatches -ProcessId $rootPid -ExpectedStart $expectedStart) -and
                (Test-ProcessIsOrDescendantOf -ProcessId $existingOwner -RootProcessId $rootPid)
            ) {
                $isVerified = $true
            }
        }
        if (-not $isVerified) {
            Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
            throw "Port $($entry.Port) already has a listener (PID $existingOwner). Hey Canvas will not reuse an unverified $($entry.Label) service. Stop it manually or choose separate ports for this checkout."
        }
    }
}

# Backend
$healthUrl = "$($cfg.BackendUrl)/health"
if (Test-HttpOk $healthUrl) {
    Write-Host "Backend already running at $($cfg.BackendUrl)"
    if ($verifiedState -and $verifiedState.backendPid) {
        $state.backendPid = $verifiedState.backendPid
        $state.backendProcessStartedAt = $verifiedState.backendProcessStartedAt
    }
} else {
    $portOwner = Get-ListeningProcessId -Port $cfg.BackendPort
    if ($portOwner) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Port $($cfg.BackendPort) is in use by another program (PID $portOwner). Stop it or set HEY_CANVAS_BACKEND_PORT."
    }
    if (-not (Test-Path $cfg.VenvPython)) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Python virtual environment not found. From the repo folder run: python -m venv .venv then install dependencies per README.md"
    }
    if ($Demo) {
        Push-Location (Join-Path $cfg.RepoRoot "backend")
        try {
            & $cfg.VenvPython -m app.dev_fixture --database-path $demoDatabase
            if ($LASTEXITCODE -ne 0) {
                throw "Synthetic demo data could not be prepared."
            }
        } finally {
            Pop-Location
        }
    }
    $backendLog = Join-Path $cfg.LogDir "backend.log"
    $backendErrLog = Join-Path $cfg.LogDir "backend.err.log"
    $backendArgs = @(
        "-m", "uvicorn", "app.main:app",
        "--app-dir", "backend",
        "--host", "127.0.0.1",
        "--port", "$($cfg.BackendPort)"
    )
    $backendProc = Start-Process -FilePath $cfg.VenvPython -ArgumentList $backendArgs `
        -WorkingDirectory $cfg.RepoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendLog `
        -RedirectStandardError $backendErrLog `
        -PassThru
    $state.backendPid = $backendProc.Id
    $state.backendProcessStartedAt = $backendProc.StartTime.ToUniversalTime().ToString("o")
    Write-Host "Starting backend (PID $($backendProc.Id))..."
    if (-not (Wait-HttpOk $healthUrl $cfg.HealthTimeoutSec)) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Backend did not become healthy in time. See $backendLog"
    }
}

# Frontend
$frontendProbe = "$($cfg.FrontendUrl)/startup"
if (Test-HeyCanvasStartupPage $frontendProbe) {
    Write-Host "Frontend already running at $($cfg.FrontendUrl)"
    if ($verifiedState -and $verifiedState.frontendPid) {
        $state.frontendPid = $verifiedState.frontendPid
        $state.frontendProcessStartedAt = $verifiedState.frontendProcessStartedAt
    }
} else {
    $portOwner = Get-ListeningProcessId -Port $cfg.FrontendPort
    if ($portOwner) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Port $($cfg.FrontendPort) is in use by another program (PID $portOwner). Stop it or set HEY_CANVAS_FRONTEND_PORT."
    }
    if (-not (Test-Path $cfg.FrontendDir)) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Frontend directory not found: $($cfg.FrontendDir)"
    }
    $nodeModules = Join-Path $cfg.FrontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Frontend dependencies missing. Run: cd frontend && npm ci"
    }
    $frontendLog = Join-Path $cfg.LogDir "frontend.log"
    $frontendErrLog = Join-Path $cfg.LogDir "frontend.err.log"
    $env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"
    $env:NEXT_PUBLIC_API_BASE_URL = $cfg.BackendUrl
    $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
        "/c", "npm run dev -- --port $($cfg.FrontendPort)"
    ) `
        -WorkingDirectory $cfg.FrontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendLog `
        -RedirectStandardError $frontendErrLog `
        -PassThru
    $state.frontendPid = $frontendProc.Id
    $state.frontendProcessStartedAt = $frontendProc.StartTime.ToUniversalTime().ToString("o")
    Write-Host "Starting frontend (PID $($frontendProc.Id))..."
    if (-not (Wait-HeyCanvasStartup $frontendProbe $cfg.FrontendTimeoutSec)) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        throw "Hey Canvas startup page did not become ready in time. See $frontendLog"
    }
}

$state | ConvertTo-Json | Set-Content -Path $cfg.StateFile -Encoding UTF8
Remove-Item $lockFile -Force -ErrorAction SilentlyContinue

$startupUrl = "$($cfg.FrontendUrl)/startup"
if (-not (Test-HeyCanvasStartupPage $startupUrl)) {
    throw "Startup route is not serving Hey Canvas at $startupUrl. Services may have failed - see $($cfg.LogDir)"
}

if (-not $NoBrowser) {
    Start-Process $startupUrl
    Write-Host "Hey Canvas is ready. Opened $startupUrl"
} else {
    Write-Host "Hey Canvas is ready. Open $startupUrl when you are ready."
}
