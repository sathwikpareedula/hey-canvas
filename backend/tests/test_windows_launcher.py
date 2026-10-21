from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPOSITORY_ROOT / "launcher" / "windows" / "Start-HeyCanvas.ps1"
STOP_LAUNCHER = REPOSITORY_ROOT / "launcher" / "windows" / "Stop-HeyCanvas.ps1"
PROCESS_HELPERS = REPOSITORY_ROOT / "launcher" / "windows" / "ProcessHelpers.ps1"
ACCEPTANCE_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "v12-academic-evidence.yml"
)
STARTUP_ROUTE = (
    REPOSITORY_ROOT
    / "frontend"
    / "src"
    / "app"
    / "(startup)"
    / "startup"
    / "page.tsx"
)


def test_windows_launcher_opens_browser_only_after_startup_route_is_ready() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    readiness_check = "Wait-HeyCanvasStartup"
    browser_open = "Start-Process $startupUrl"

    assert STARTUP_ROUTE.is_file()
    assert source.count(browser_open) == 1
    assert source.index(readiness_check) < source.index(browser_open)
    assert "Hey Canvas is starting..." in source


def test_windows_launcher_remains_legacy_powershell_ascii_safe() -> None:
    source_bytes = LAUNCHER.read_bytes()

    assert all(byte < 128 for byte in source_bytes)


def test_windows_launcher_defaults_personal_mode_to_local_ai() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'if (-not $env:ACADEMIC_MODEL_PROVIDER)' in source
    assert '$env:ACADEMIC_MODEL_PROVIDER = "ollama"' in source
    assert '$env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"' in source


def test_windows_demo_launcher_uses_explicit_supported_switch() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    demo_cmd = (LAUNCHER.parent / "Start-HeyCanvas-Demo.cmd").read_text(
        encoding="utf-8"
    )

    assert "[switch]$Demo" in source
    assert "if ($Demo)" in source
    assert '$env:ACADEMIC_MODEL_PROVIDER = "synthetic"' in source
    assert '$env:NEXT_PUBLIC_HEY_CANVAS_DEMO = "1"' in source
    assert '$demoDir = Join-Path $cfg.RunDir "demo"' in source
    assert '$demoDatabase = Join-Path $demoDir "hey-canvas-demo.db"' in source
    assert '$env:DATABASE_URL = "sqlite:///' in source
    assert "$env:ACADEMIC_FILES_ROOT = $demoFiles" in source
    assert "-m app.dev_fixture --database-path $demoDatabase" in source
    assert "$SkipOllama = $true" in source
    assert "-Demo" in demo_cmd
    assert "%*" in demo_cmd
    assert "if errorlevel 1" in demo_cmd


def test_windows_launcher_does_not_reuse_a_different_application_mode() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert '$requestedMode = if ($Demo) { "demo" } else { "personal" }' in source
    assert "mode        = $requestedMode" in source
    assert '$runningMode -ne $requestedMode' in source
    assert "Stop it before starting $requestedMode mode." in source
    assert source.index("if ($existingOwner)") < source.index(
        '$runningMode -ne $requestedMode'
    )


def test_windows_cmd_launchers_forward_optional_arguments() -> None:
    start_cmd = (LAUNCHER.parent / "Start-HeyCanvas.cmd").read_text(encoding="utf-8")
    demo_cmd = (LAUNCHER.parent / "Start-HeyCanvas-Demo.cmd").read_text(
        encoding="utf-8"
    )

    assert 'Start-HeyCanvas.ps1" %*' in start_cmd
    assert 'Start-HeyCanvas.ps1" -Demo %*' in demo_cmd


def test_windows_launcher_fails_fast_for_missing_prerequisites() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'throw "Python virtual environment not found.' in source
    assert 'throw "Frontend dependencies missing. Run: cd frontend && npm ci"' in source
    assert 'throw "Port $($cfg.BackendPort) is in use by another program' in source
    assert 'throw "Port $($cfg.FrontendPort) is in use by another program' in source


def test_stop_launcher_does_not_kill_unowned_port_listeners() -> None:
    """A second checkout or unrelated service may occupy the configured ports."""
    source = STOP_LAUNCHER.read_text(encoding="utf-8")

    assert "Get-ListeningProcessId" not in source
    assert "No launcher state found; leaving existing port listeners untouched." in source
    assert 'Stop-ProcessTree -ProcessId ([int]$procId)' in source
    assert "Test-ProcessStartTimeMatches" in source
    assert "PID $procId is missing or has been reused; leaving it untouched." in source
    assert source.index("Test-ProcessStartTimeMatches") < source.index(
        "Stop-ProcessTree -ProcessId ([int]$procId)"
    )


def test_start_launcher_records_process_creation_times() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert (
        '$state.backendProcessStartedAt = $backendProc.StartTime.ToUniversalTime().ToString("o")'
        in source
    )
    assert (
        '$state.frontendProcessStartedAt = $frontendProc.StartTime.ToUniversalTime().ToString("o")'
        in source
    )


def test_stop_launcher_refuses_legacy_pid_only_state() -> None:
    source = STOP_LAUNCHER.read_text(encoding="utf-8")
    assert 'if (-not $expectedStart)' in source
    assert 'No process creation timestamp for $pidProp' in source


def test_start_launcher_refuses_existing_unverified_services() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    guard = 'Existing listeners must not be adopted'
    assert guard in source
    assert 'Get-ListeningProcessId -Port $entry.Port' in source
    assert 'will not reuse an unverified' in source
    assert source.index(guard) < source.index('$healthUrl =')


def test_launcher_normalizes_serialized_process_start_times() -> None:
    helpers = PROCESS_HELPERS.read_text(encoding="utf-8")
    start_source = LAUNCHER.read_text(encoding="utf-8")
    stop_source = STOP_LAUNCHER.read_text(encoding="utf-8")

    assert "function Test-ProcessStartTimeMatches" in helpers
    assert "$ExpectedStart -is [datetime]" in helpers
    assert "[System.Globalization.DateTimeStyles]::RoundtripKind" in helpers
    assert "Test-ProcessStartTimeMatches" in start_source
    assert "Test-ProcessStartTimeMatches" in stop_source


def test_windows_clean_clone_smoke_uses_public_course_api_identifier() -> None:
    workflow = ACCEPTANCE_WORKFLOW.read_text(encoding="utf-8")

    assert '$_.canvas_course_id.StartsWith("synthetic-")' in workflow
    assert '$_.id.StartsWith("synthetic-")' not in workflow
