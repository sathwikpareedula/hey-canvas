# Shared process/port helpers for Hey Canvas launcher (repo-relative).

function Stop-ProcessTree {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return }
    try {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    } catch {
        try { Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue } catch { }
    }
}

function Get-ListeningProcessId {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn) { return [int]$conn.OwningProcess }
    } catch {
        $line = netstat -ano | Select-String -Pattern ":\s*$Port\s+.*LISTENING\s+(\d+)" | Select-Object -First 1
        if ($line -and $line.Matches.Success) {
            return [int]$line.Matches.Groups[1].Value
        }
    }
    return $null
}

function Test-PortOwnedByProcess {
    param([int]$Port, [int]$ExpectedPid)
    $owner = Get-ListeningProcessId -Port $Port
    if (-not $owner) { return $false }
    return $owner -eq $ExpectedPid
}

function Test-ProcessIsOrDescendantOf {
    param(
        [int]$ProcessId,
        [int]$RootProcessId
    )
    if ($ProcessId -le 0 -or $RootProcessId -le 0) { return $false }
    if ($ProcessId -eq $RootProcessId) { return $true }
    $currentPid = $ProcessId
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentPid" -ErrorAction SilentlyContinue
            if (-not $proc -or $proc.ParentProcessId -le 0) { break }
            if ($proc.ParentProcessId -eq $RootProcessId) { return $true }
            $currentPid = [int]$proc.ParentProcessId
        } catch {
            break
        }
    }
    return $false
}

function Test-ProcessStartTimeMatches {
    param(
        [int]$ProcessId,
        [object]$ExpectedStart,
        [double]$ToleranceSeconds = 2
    )
    if ($ProcessId -le 0 -or -not $ExpectedStart) { return $false }
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        $recordedStart = if ($ExpectedStart -is [datetime]) {
            ([datetime]$ExpectedStart).ToUniversalTime()
        } else {
            [datetime]::Parse(
                [string]$ExpectedStart,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind
            ).ToUniversalTime()
        }
        $actualStart = $process.StartTime.ToUniversalTime()
        return [math]::Abs(($actualStart - $recordedStart).TotalSeconds) -le $ToleranceSeconds
    } catch {
        return $false
    }
}

function Test-OllamaReachable {
    param(
        [string]$BaseUrl = "http://127.0.0.1:11434",
        [int]$TimeoutSec = 3
    )
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl/api/tags" -UseBasicParsing -TimeoutSec $TimeoutSec
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
    } catch {
        return $false
    }
}

function Start-OllamaRuntimeIfInstalled {
    param([int]$WaitSeconds = 20)
    if (Test-OllamaReachable) {
        Write-Host "Local AI runtime already reachable."
        return $true
    }
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Host "Ollama command not found - install Local AI runtime from Settings guidance."
        return $false
    }
    Write-Host "Starting Local AI runtime (ollama serve)..."
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaReachable -TimeoutSec 5) { return $true }
        Start-Sleep -Seconds 2
    }
    if (Test-OllamaReachable -TimeoutSec 8) { return $true }
    Write-Host "Local AI runtime is still starting. Hey Canvas will keep checking from Settings while Ollama finishes warming up."
    return $false
}
