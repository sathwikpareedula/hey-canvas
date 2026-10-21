<#
.SYNOPSIS
  Windows verification of the V1.2 release candidate in an ISOLATED, synthetic-only stack.

.DESCRIPTION
  Seeds a disposable synthetic SQLite database, starts the backend and Next.js on
  isolated ports with an isolated Next build directory, then runs the HTTP-level
  gates that can be automated. Browser, microphone and real-Ollama gates are printed
  as a manual checklist: this script NEVER marks them as passed.

  It does not read Canvas credentials, does not touch the live V1.1 installation,
  its ports (3001 / 13117 unless you override them), its database or its .env.

  STATUS: written on Linux, parse-checked with PowerShell only. It has NOT been run on
  Windows by the author. Treat every result as UNVERIFIED until you run it.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostic\windows-v12-final-verify.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostic\windows-v12-final-verify.ps1 -Stop
#>
param(
    [int]$BackendPort = 18461,
    [int]$FrontendPort = 18462,
    [switch]$UseOllama,
    [switch]$SkipBuild,
    [switch]$Stop
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Run = Join-Path $Root ".hey-canvas\verify-v12"
$StateFile = Join-Path $Run "stack.json"
$DbPath = Join-Path $Run ("synthetic-{0}.db" -f $PID)
$NextDist = ".next-verify-v12-$FrontendPort"
$Results = New-Object System.Collections.Generic.List[object]
$SeedCommand = Join-Path $Root ".venv\Scripts\academic-seed-demo.exe"
$UvicornCommand = Join-Path $Root ".venv\Scripts\uvicorn.exe"

function Add-Result([string]$Name, [bool]$Passed, [string]$Detail = "") {
    $Results.Add([pscustomobject]@{ Gate = $Name; Result = $(if ($Passed) { "PASS" } else { "FAIL" }); Detail = $Detail })
    Write-Host ("{0,-6} {1} {2}" -f $(if ($Passed) { "PASS" } else { "FAIL" }), $Name, $Detail)
}

function Wait-HttpReady([string]$Url, [int]$TimeoutSeconds = 90, [string]$ExpectedText = "") {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $lastError = "no response"
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 5
            $contentReady = (-not $ExpectedText) -or ($response.Content -like "*$ExpectedText*")
            if ($response.StatusCode -eq 200 -and $contentReady) { return $response }
            $lastError = "HTTP $($response.StatusCode); expected content present: $contentReady"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }
    throw "Timed out waiting for $Url after $TimeoutSeconds seconds ($lastError)"
}

function Stop-Stack {
    if (Test-Path $StateFile) {
        $st = Get-Content $StateFile -Raw | ConvertFrom-Json
        $entries = @(
            @{ pid = $st.backendPid; port = $st.backendPort },
            @{ pid = $st.frontendPid; port = $st.frontendPort }
        )
        foreach ($entry in $entries) {
            $procId = $entry.pid
            $port = $entry.port
            $listener = if ($port) {
                Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            } else { $null }
            $listenerOwned = $listener -and ($listener.OwningProcess -contains [uint32]$procId)
            if ($procId -and $listenerOwned -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
                # taskkill /T stops the whole process tree for ONLY the PIDs this script recorded.
                $savedErrorPreference = $ErrorActionPreference
                try {
                    $ErrorActionPreference = "Continue"
                    & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
                } finally {
                    $ErrorActionPreference = $savedErrorPreference
                }
            }
        }
        Remove-Item $StateFile -Force
        if ($st.dbPath -and (Test-Path $st.dbPath)) {
            Remove-Item $st.dbPath -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Stopped isolated stack (recorded PIDs only)."
    } else {
        Write-Host "No recorded isolated stack to stop."
    }
}

if ($Stop) { Stop-Stack; return }

# A crashed or interrupted prior run can leave an obsolete PID file behind.
# Never act on it unless its recorded ports are still listening; PID values can be reused.
if (Test-Path $StateFile) {
    $prior = Get-Content $StateFile -Raw | ConvertFrom-Json
    $priorListeners = @($prior.backendPort, $prior.frontendPort) | Where-Object {
        $_ -and (Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue)
    }
    if ($priorListeners.Count -gt 0) {
        throw "A recorded isolated verification stack is still active. Run this script with -Stop first."
    }
    Remove-Item $StateFile -Force
}

# ---- Safety preconditions -------------------------------------------------------------
foreach ($port in @($BackendPort, $FrontendPort)) {
    if ($port -in 3001, 13117, 8000, 3000) {
        throw "Port $port is reserved for the live/default install. Choose an isolated port."
    }
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Pick another with -BackendPort / -FrontendPort."
    }
}
if ($env:DATABASE_URL) {
    Write-Warning "DATABASE_URL is set in this shell; it is overridden for child processes only."
}
New-Item -ItemType Directory -Force -Path $Run | Out-Null
Push-Location $Root
$completed = $false
$backend = $null
$frontend = $null

try {
    # ---- 1. Synthetic database ---------------------------------------------------------
    foreach ($command in @($SeedCommand, $UvicornCommand)) {
        if (-not (Test-Path $command)) {
            throw "The isolated Python environment is incomplete ($command is missing). Run 'uv sync --extra dev' in this worktree."
        }
    }
    & $SeedCommand --database-path $DbPath | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Synthetic database seed failed with exit code $LASTEXITCODE" }
    Add-Result "synthetic_db_seeded" (Test-Path $DbPath) $DbPath

    # ---- 2. Backend (guard ON, origins limited to the isolated frontend) ----------------
    $env:DATABASE_URL = "sqlite:///" + ($DbPath -replace "\\", "/")
    $env:ACADEMIC_MODEL_PROVIDER = $(if ($UseOllama) { "ollama" } else { "synthetic" })
    $env:LOCAL_API_GUARD_ENABLED = "true"
    $env:LOCAL_API_ALLOWED_ORIGINS = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
    $backend = Start-Process -FilePath $UvicornCommand -ArgumentList @(
        "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--app-dir", "backend"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Run "backend.out.log") -RedirectStandardError (Join-Path $Run "backend.err.log")
    @{ backendPid = $backend.Id; frontendPid = $null; backendPort = $BackendPort; frontendPort = $FrontendPort; dbPath = $DbPath } |
        ConvertTo-Json | Set-Content $StateFile
    Wait-HttpReady "http://127.0.0.1:$BackendPort/health" 90 | Out-Null
    $backendPid = (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction Stop |
        Select-Object -First 1 -ExpandProperty OwningProcess)
    @{ backendPid = $backendPid; frontendPid = $null; backendPort = $BackendPort; frontendPort = $FrontendPort; dbPath = $DbPath } |
        ConvertTo-Json | Set-Content $StateFile
    $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 10
    Add-Result "backend_health" ($health.status -eq "ok") ($health | ConvertTo-Json -Compress)

    # ---- 3. Local backend guard (HTTP) --------------------------------------------------
    function Get-Status($Method, $Url, $Headers, $Body) {
        try {
            $r = Invoke-WebRequest -Method $Method -Uri $Url -Headers $Headers -Body $Body -ContentType "application/json" -UseBasicParsing -TimeoutSec 15
            return [int]$r.StatusCode
        } catch { return [int]$_.Exception.Response.StatusCode }
    }
    $api = "http://127.0.0.1:$BackendPort"
    $client = @{ "X-Hey-Canvas-Client" = "hey-canvas-local" }
    $q = '{"query":"What is due today?"}'
    Add-Result "guard_blocks_missing_client_header" ((Get-Status POST "$api/api/assistant/respond" @{} $q) -eq 403)
    Add-Result "guard_blocks_hostile_origin" ((Get-Status POST "$api/api/assistant/respond" @{ "X-Hey-Canvas-Client" = "hey-canvas-local"; "Origin" = "https://attacker.example" } $q) -eq 403)
    Add-Result "guard_allows_legitimate_request" ((Get-Status POST "$api/api/assistant/respond" $client $q) -eq 200)
    $huge = '{"query":"' + ("a" * 600000) + '"}'
    Add-Result "guard_caps_oversized_body" ((Get-Status POST "$api/api/assistant/respond" $client $huge) -eq 413)

    # ---- 4. Frontend build + start (isolated dist dir) ----------------------------------
    $env:HEY_CANVAS_NEXT_DIST_DIR = $NextDist
    $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$BackendPort"
    $env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"
    Push-Location (Join-Path $Root "frontend")
    if (-not $SkipBuild) {
        & npm ci | Out-Host
        $savedErrorPreference = $ErrorActionPreference
        try {
            # Windows PowerShell 5 wraps native stderr (including harmless Next warnings)
            # as ErrorRecord objects. Capture it without converting warnings into a
            # terminating PowerShell exception; the native exit code remains authoritative.
            $ErrorActionPreference = "Continue"
            & npm.cmd run build 2>&1 | Tee-Object -FilePath (Join-Path $Run "frontend-build.log") | Out-Host
            $buildExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedErrorPreference
        }
        Add-Result "frontend_production_build" ($buildExitCode -eq 0) "see $Run\frontend-build.log (needs internet for Google Fonts on first build)"
        if ($buildExitCode -ne 0) { throw "Frontend production build failed with exit code $buildExitCode" }
    }
    $frontend = Start-Process -FilePath "npx.cmd" -ArgumentList @("next", "start", "-p", "$FrontendPort", "-H", "127.0.0.1") `
        -WorkingDirectory (Get-Location).Path -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Run "frontend.out.log") -RedirectStandardError (Join-Path $Run "frontend.err.log")
    Pop-Location
    @{ backendPid = $backend.Id; frontendPid = $frontend.Id; backendPort = $BackendPort; frontendPort = $FrontendPort; dbPath = $DbPath } |
        ConvertTo-Json | Set-Content $StateFile
    $page = Wait-HttpReady "http://127.0.0.1:$FrontendPort/dashboard" 120 "Hey Canvas"
    $frontendPid = (Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction Stop |
        Select-Object -First 1 -ExpandProperty OwningProcess)
    @{ backendPid = $backendPid; frontendPid = $frontendPid; backendPort = $BackendPort; frontendPort = $FrontendPort; dbPath = $DbPath } |
        ConvertTo-Json | Set-Content $StateFile
    Add-Result "frontend_serves_dashboard" ($page.StatusCode -eq 200)

    # ---- 5. Next chat streaming proxy -> backend (needs the local client header) --------
    $front = "http://127.0.0.1:$FrontendPort"
    Add-Result "next_proxy_blocks_missing_client_header" ((Get-Status POST "$front/api/assistant/stream" @{} $q) -in 400, 403)
    $stream = Invoke-WebRequest -Method POST -Uri "$front/api/assistant/stream" -Headers $client -Body $q -ContentType "application/json" -UseBasicParsing -TimeoutSec 60
    $terminal = ([regex]::Matches($stream.Content, "event: (completed|error)")).Count
    Add-Result "next_stream_has_exactly_one_terminal_event" ($terminal -eq 1) "terminal events: $terminal"

    # ---- 6. Real Ollama (only with -UseOllama) ----------------------------------------
    if ($UseOllama) {
        $ollama = Get-Command ollama -ErrorAction SilentlyContinue
        Add-Result "ollama_installed" ($null -ne $ollama)
        try {
            $tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
            Add-Result "ollama_reachable_with_models" ($tags.models.Count -gt 0) "models: $($tags.models.Count)"
        } catch { Add-Result "ollama_reachable_with_models" $false $_.Exception.Message }
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $body = '{"query":"Summarize the main ideas of the Synthetic Kinematics Notes.","course_id":"synthetic-robotics"}'
        $ans = Invoke-WebRequest -Method POST -Uri "$front/api/assistant/stream" -Headers $client -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 180
        $sw.Stop()
        Add-Result "ollama_streamed_answer_terminates" (([regex]::Matches($ans.Content, "event: (completed|error)")).Count -eq 1) ("{0:N1}s" -f $sw.Elapsed.TotalSeconds)
    } else {
        Write-Host "Skipping real-Ollama gates (re-run with -UseOllama)."
    }

    # ---- 7. Privacy scan of logs ---------------------------------------------------------
    $logs = Get-ChildItem $Run -Filter "*.log" | Get-Content -Raw
    $leak = $logs -match "(?i)(bearer\s+[a-z0-9]{12,}|canvas_token\s*=|C:\\Users\\[^\\]+\\AppData)"
    Add-Result "logs_contain_no_token_or_profile_paths" (-not $leak)
    $completed = $true
}
finally {
    Pop-Location
    if (-not $completed) {
        # These Process objects were created by this exact invocation, so early-failure
        # cleanup can stop their trees without trusting stale PID-file data.
        foreach ($started in @($frontend, $backend)) {
            if ($null -ne $started -and -not $started.HasExited) {
                $savedErrorPreference = $ErrorActionPreference
                try {
                    $ErrorActionPreference = "Continue"
                    & taskkill.exe /PID $started.Id /T /F 2>$null | Out-Null
                } finally {
                    $ErrorActionPreference = $savedErrorPreference
                }
            }
        }
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
        Remove-Item $DbPath -Force -ErrorAction SilentlyContinue
    }
}

$Results | Format-Table -AutoSize | Out-Host
$Results | ConvertTo-Json | Set-Content (Join-Path $Run "results.json")
Write-Host @"

MANUAL GATES - NOT automated, NOT claimed as passed:
  [ ] Open http://127.0.0.1:$FrontendPort in Edge/Chrome; finish onboarding; dashboard shows synthetic courses.
  [ ] Chat: 'What is due today?', 'When is Kinematics Worksheet due?', 'Explain the Robot Planning Quiz'.
  [ ] Stop generation mid-answer (if the UI offers it); Send must re-enable; ask a follow-up.
  [ ] DevTools console: no red errors except the expected Ollama-unavailable notice when Ollama is off.
  [ ] Microphone: click voice input; browser permission prompt appears; deny -> friendly message, no crash.
  [ ] Kill the backend (Task Manager, the recorded PID only); reload -> 'Connection problem' banner, no blank page.
  [ ] Mobile width (DevTools device toolbar, 390px): no horizontal scroll.
  [ ] Launcher start/restart scripts under launcher\windows on their own isolated ports.
Stop the isolated stack with:  scripts\diagnostic\windows-v12-final-verify.ps1 -Stop
"@
