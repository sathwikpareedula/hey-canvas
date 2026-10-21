"""Canvas connection and sync trigger API (no live credentials)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.routes import canvas_operations
from app.config import Settings, get_settings
from app.main import app


def _unconfigured_settings() -> Settings:
    return Settings(
        canvas_api_token=None,
        canvas_base_url=None,
    )


def test_canvas_connection_not_configured() -> None:
    app.dependency_overrides[get_settings] = _unconfigured_settings
    try:
        client = TestClient(app)
        response = client.get("/api/canvas/connection")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "not_configured"
    finally:
        app.dependency_overrides.clear()


def test_canvas_sync_rejects_when_not_configured() -> None:
    app.dependency_overrides[get_settings] = _unconfigured_settings
    try:
        client = TestClient(app)
        response = client.post(
            "/api/canvas/sync",
            headers={"x-hey-canvas-client": "hey-canvas-local"},
        )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def _configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        canvas_base_url="https://canvas.example.edu",
        canvas_token=SecretStr("synthetic-test-token"),
    )


def test_canvas_sync_trigger_is_atomic_before_background_job_starts(session) -> None:
    class CapturingTasks:
        def __init__(self) -> None:
            self.tasks: list[object] = []

        def add_task(self, function, *args, **kwargs) -> None:
            self.tasks.append((function, args, kwargs))

    tasks = CapturingTasks()
    assert not canvas_operations._SYNC_SINGLE_FLIGHT.locked()
    try:
        first = canvas_operations.trigger_canvas_sync(tasks, _configured_settings(), session)
        second = canvas_operations.trigger_canvas_sync(tasks, _configured_settings(), session)
        assert first.accepted is True
        assert second.accepted is False
        assert len(tasks.tasks) == 1
    finally:
        if canvas_operations._SYNC_SINGLE_FLIGHT.locked():
            canvas_operations._SYNC_SINGLE_FLIGHT.release()


def test_canvas_sync_trigger_releases_reservation_when_scheduling_fails(session) -> None:
    class FailingTasks:
        def add_task(self, function, *args, **kwargs) -> None:
            del function, args, kwargs
            raise RuntimeError("synthetic scheduler failure")

    with pytest.raises(RuntimeError, match="scheduler failure"):
        canvas_operations.trigger_canvas_sync(
            FailingTasks(), _configured_settings(), session
        )
    assert not canvas_operations._SYNC_SINGLE_FLIGHT.locked()


def test_canvas_sync_job_releases_reservation_after_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_sync(*args, **kwargs) -> None:
        del args, kwargs
        raise ValueError("synthetic sync failure")

    monkeypatch.setattr(canvas_operations, "synchronize_all", fail_sync)
    assert canvas_operations._SYNC_SINGLE_FLIGHT.acquire(blocking=False)
    canvas_operations._run_sync_job()
    assert not canvas_operations._SYNC_SINGLE_FLIGHT.locked()
