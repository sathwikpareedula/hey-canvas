# Stop only processes verified as belonging to this launcher checkout.
. (Join-Path $PSScriptRoot "config.ps1")
. (Join-Path $PSScriptRoot "ProcessHelpers.ps1")
$cfg = Get-HeyCanvasConfig

$stopped = @()
$state = $null

if (Test-Path $cfg.StateFile) {
    try {
        $raw = Get-Content $cfg.StateFile -Raw -ErrorAction Stop
        if ($raw) {
            $state = $raw | ConvertFrom-Json -ErrorAction Stop
        }
    } catch {
        Write-Warning "Launcher state could not be read; leaving processes untouched."
        exit 1
    }
}

if ($state) {
    foreach ($pidProp in @("frontendPid", "backendPid", "ollamaPid")) {
        $procId = $state.$pidProp
        if (-not $procId) { continue }

        # A PID alone is not proof of ownership because Windows can reuse it.
        $startedProp = $pidProp -replace 'Pid$', 'ProcessStartedAt'
        $expectedStart = $state.$startedProp
        if (-not $expectedStart) {
            Write-Warning "No process creation timestamp for $pidProp; leaving PID $procId untouched."
            continue
        }
        try {
            if (-not (Test-ProcessStartTimeMatches -ProcessId ([int]$procId) -ExpectedStart $expectedStart)) {
                Write-Warning "PID $procId is missing or has been reused; leaving it untouched."
                continue
            }
            Stop-ProcessTree -ProcessId ([int]$procId)
            $stopped += "$pidProp=$procId"
        } catch {
            Write-Warning "Could not verify $pidProp PID $procId; leaving it untouched."
        }
    }
    Remove-Item $cfg.StateFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "No launcher state found; leaving existing port listeners untouched."
}

if ($stopped.Count -eq 0) {
    Write-Host "No Hey Canvas launcher processes found."
} else {
    Write-Host "Hey Canvas stopped: $($stopped -join ', ')"
}
