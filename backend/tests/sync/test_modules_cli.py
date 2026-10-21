import pytest
from app.canvas.exceptions import CanvasConfigurationError
from app.config import Settings
from app.sync import modules_cli
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker


@pytest.mark.asyncio
async def test_module_sync_requires_local_canvas_configuration() -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url=None,
        canvas_token=None,
        database_url="sqlite:///:memory:",
    )

    with pytest.raises(CanvasConfigurationError, match=r"local \.env"):
        await modules_cli.synchronize_configured_modules(settings)


@pytest.mark.asyncio
async def test_module_sync_with_no_local_courses_is_clear_and_makes_no_request(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url="https://canvas.example.edu",
        canvas_token=SecretStr("unit-test-secret"),
        database_url="sqlite:///:memory:",
    )
    monkeypatch.setattr(modules_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(modules_cli, "get_session_factory", lambda: session_factory)

    exit_code = await modules_cli.synchronize_configured_modules(settings)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Run canvas-sync-courses first" in captured.out
    assert "unit-test-secret" not in captured.out + captured.err
