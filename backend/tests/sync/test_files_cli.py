import pytest
from app.canvas.exceptions import CanvasConfigurationError
from app.config import Settings
from app.sync import files_download_cli, files_metadata_cli
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker


@pytest.mark.asyncio
async def test_file_clis_require_local_credentials_without_exposing_values() -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url=None,
        canvas_token=None,
        database_url="sqlite:///:memory:",
    )
    with pytest.raises(CanvasConfigurationError, match=r"local \.env"):
        await files_metadata_cli.synchronize_configured_file_metadata(settings)
    with pytest.raises(CanvasConfigurationError, match=r"local \.env"):
        await files_download_cli.download_configured_file(settings, canvas_file_id="7001")


@pytest.mark.asyncio
async def test_metadata_cli_with_no_references_downloads_nothing_and_hides_token(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url="https://canvas.example.edu",
        canvas_token=SecretStr("fake-unit-token"),
        database_url="sqlite:///:memory:",
    )
    monkeypatch.setattr(files_metadata_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(files_metadata_cli, "get_session_factory", lambda: session_factory)
    result = await files_metadata_cli.synchronize_configured_file_metadata(settings)
    output = capsys.readouterr()
    assert result == 0
    assert "No files were downloaded" in output.out
    assert "fake-unit-token" not in output.out + output.err


@pytest.mark.asyncio
async def test_download_cli_no_matching_file_is_safe_and_concise(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url="https://canvas.example.edu",
        canvas_token=SecretStr("fake-unit-token"),
        database_url="sqlite:///:memory:",
        academic_files_root="data/test-files",
    )
    monkeypatch.setattr(files_download_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(files_download_cli, "get_session_factory", lambda: session_factory)
    result = await files_download_cli.download_configured_file(
        settings, canvas_file_id="7001", canvas_course_id="101"
    )
    output = capsys.readouterr()
    assert result == 1
    assert "Run canvas-sync-file-metadata first" in output.err
    assert "fake-unit-token" not in output.out + output.err
