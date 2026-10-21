import pytest
from app.canvas.exceptions import CanvasConfigurationError
from app.config import Settings
from app.sync.assignments_cli import synchronize_configured_assignments


@pytest.mark.asyncio
async def test_assignment_sync_requires_local_canvas_configuration() -> None:
    settings = Settings(
        _env_file=None,
        canvas_base_url=None,
        canvas_token=None,
        database_url="sqlite:///:memory:",
    )

    with pytest.raises(CanvasConfigurationError, match=r"local \.env"):
        await synchronize_configured_assignments(settings)

