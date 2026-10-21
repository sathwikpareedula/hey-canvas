from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.canvas.files import normalize_file
from app.database.file_repository import FileRepository
from app.database.module_repository import ModuleRepository
from app.database.session import get_session
from app.main import app
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from sqlalchemy.orm import Session, sessionmaker

from tests.factories import canvas_file_payload
from tests.services.test_assignment_sync import add_course


def override_factory(factory: sessionmaker[Session]) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    return override


def seed(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        course = add_course(session, "101")
        ModuleRepository(session).synchronize_course(
            course,
            [
                ModuleSnapshot(
                    canvas_module_id="201",
                    canvas_course_id="101",
                    items=(
                        ModuleItemSnapshot(
                            canvas_module_item_id="1001",
                            canvas_module_id="201",
                            canvas_course_id="101",
                            item_type="File",
                            content_id="7001",
                            title="Lecture.pdf",
                        ),
                    ),
                )
            ],
            synced_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        FileRepository(session).synchronize(
            [normalize_file(canvas_file_payload()).snapshot],
            synced_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        record = FileRepository(session).get("7001")
        assert record is not None
        FileRepository(session).record_download_success(
            record,
            downloaded_at=datetime(2026, 9, 29, tzinfo=UTC),
            local_relative_path="7001/lecture.pdf",
            sha256="a" * 64,
            local_size=12345,
            http_content_type="application/pdf",
        )
        session.commit()


@pytest.mark.asyncio
async def test_file_api_is_local_only_filters_and_exposes_no_url_or_absolute_path(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(session_factory)

    async def fail(*_: object, **__: object) -> object:
        raise AssertionError("local file GET API must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_json", fail)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            all_files = await client.get("/api/files")
            filtered = await client.get(
                "/api/files", params={"course_id": "101", "download_state": "downloaded"}
            )
            one = await client.get("/api/files/7001")
            absent = await client.get("/api/files/missing")
    finally:
        app.dependency_overrides.clear()

    assert all_files.status_code == filtered.status_code == one.status_code == 200
    payload = one.json()
    assert payload["canvas_file_id"] == "7001"
    assert payload["local_relative_path"] == "7001/lecture.pdf"
    assert not Path(payload["local_relative_path"]).is_absolute()
    assert "url" not in payload
    assert "metadata_fingerprint" not in payload
    assert payload["references"][0]["canvas_module_item_id"] == "1001"
    assert len(filtered.json()) == 1
    assert absent.status_code == 404


@pytest.mark.asyncio
async def test_file_api_rejects_invalid_filters(session_factory: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            invalid_course = await client.get("/api/files", params={"course_id": "bad id"})
            invalid_state = await client.get("/api/files", params={"download_state": "unknown"})
    finally:
        app.dependency_overrides.clear()
    assert invalid_course.status_code == 422
    assert invalid_state.status_code == 422
