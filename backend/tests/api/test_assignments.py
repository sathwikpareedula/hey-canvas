from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.api.routes.deadlines import get_deadline_clock
from app.assignments.models import AssignmentSnapshot
from app.canvas.client import CanvasClient
from app.database.assignment_repository import AssignmentRepository
from app.database.session import get_session
from app.main import app
from sqlalchemy.orm import Session, sessionmaker

from tests.services.test_assignment_sync import add_course


def seed_assignment(
    session_factory: sessionmaker[Session],
    *,
    due_at: datetime,
) -> None:
    with session_factory() as session:
        course = add_course(session, "101")
        AssignmentRepository(session).synchronize_course(
            course,
            [
                AssignmentSnapshot(
                    canvas_assignment_id="501",
                    canvas_course_id="101",
                    name="Homework 1",
                    description_html="<p>Untrusted instructions</p>",
                    due_at=due_at,
                    html_url="https://canvas.example.edu/courses/101/assignments/501",
                )
            ],
            synced_at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
        )
        session.commit()


def make_session_override(
    session_factory: sessionmaker[Session],
) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return override


@pytest.mark.asyncio
async def test_assignment_api_reads_local_database_and_never_calls_canvas(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    due_at = datetime(2026, 10, 2, 4, 59, tzinfo=UTC)
    seed_assignment(session_factory, due_at=due_at)

    async def fail_if_called(*_: object, **__: object) -> list[dict[str, object]]:
        raise AssertionError("local GET API must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_paginated", fail_if_called)
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/assignments", params={"course_id": "101"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["canvas_assignment_id"] == "501"
    assert payload[0]["description_html"] == "<p>Untrusted instructions</p>"
    assert payload[0]["due_at"] == "2026-10-02T04:59:00Z"
    assert "id" not in payload[0]


@pytest.mark.asyncio
async def test_deadline_api_reads_local_database_and_validates_inputs(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_now = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    seed_assignment(session_factory, due_at=frozen_now + timedelta(days=1))

    async def fail_if_called(*_: object, **__: object) -> list[dict[str, object]]:
        raise AssertionError("local GET API must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_paginated", fail_if_called)
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    app.dependency_overrides[get_deadline_clock] = lambda: (lambda: frozen_now)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            valid = await client.get("/api/deadlines", params={"window": "next_7_days"})
            bad_window = await client.get("/api/deadlines", params={"window": "someday"})
            bad_course = await client.get(
                "/api/deadlines",
                params={"window": "upcoming", "course_id": "has whitespace"},
            )
    finally:
        app.dependency_overrides.clear()

    assert valid.status_code == 200
    assert len(valid.json()) == 1
    assert bad_window.status_code == 422
    assert bad_course.status_code == 422


@pytest.mark.asyncio
async def test_assignment_api_rejects_naive_or_reversed_date_filters(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            naive = await client.get("/api/assignments", params={"from": "2026-10-01T00:00:00"})
            reversed_range = await client.get(
                "/api/assignments",
                params={
                    "from": "2026-10-02T00:00:00Z",
                    "to": "2026-10-01T00:00:00Z",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert naive.status_code == 422
    assert reversed_range.status_code == 422
