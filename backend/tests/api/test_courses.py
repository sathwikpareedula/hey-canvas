from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.courses.models import CourseSnapshot
from app.database.course_repository import CourseRepository
from app.database.session import get_session
from app.main import app
from sqlalchemy.orm import Session, sessionmaker


@pytest.mark.asyncio
async def test_api_returns_persisted_courses_without_contacting_canvas(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_at = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    with session_factory() as session:
        CourseRepository(session).synchronize(
            [
                CourseSnapshot(
                    canvas_course_id="900719925474099312345",
                    course_code="CSE 4360",
                    course_name="Autonomous Robots",
                    workflow_state="available",
                    enrollment_state="active",
                )
            ],
            synced_at=observed_at,
        )
        session.commit()

    async def fail_if_canvas_is_called(*_: object, **__: object) -> list[dict[str, object]]:
        raise AssertionError("GET /api/courses must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_paginated", fail_if_canvas_is_called)

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/courses")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["canvas_course_id"] == "900719925474099312345"
    assert payload[0]["course_name"] == "Autonomous Robots"
    assert payload[0]["first_seen_at"] == "2026-09-28T15:00:00Z"
    assert "id" not in payload[0]


@pytest.mark.asyncio
async def test_api_returns_empty_list_for_empty_database(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/courses")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []

