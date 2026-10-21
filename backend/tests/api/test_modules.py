from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import httpx
import pytest
from app.assignments.models import AssignmentSnapshot
from app.canvas.client import CanvasClient
from app.database.assignment_repository import AssignmentRepository
from app.database.course_repository import CourseRepository
from app.database.module_repository import ModuleRepository
from app.database.session import get_session
from app.main import app
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from sqlalchemy.orm import Session, sessionmaker

from tests.services.test_assignment_sync import add_course


def make_session_override(
    session_factory: sessionmaker[Session],
) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return override


def seed_structure(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        course = add_course(session, "101", name="Autonomous Robots")
        AssignmentRepository(session).synchronize_course(
            course,
            [
                AssignmentSnapshot(
                    canvas_assignment_id="501",
                    canvas_course_id="101",
                    name="Homework 1",
                    due_at=datetime(2026, 10, 1, tzinfo=UTC),
                )
            ],
            synced_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        ModuleRepository(session).synchronize_course(
            course,
            [
                ModuleSnapshot(
                    canvas_module_id="202",
                    canvas_course_id="101",
                    name="Kinematics",
                    position=2,
                    items=(
                        ModuleItemSnapshot(
                            canvas_module_item_id="1003",
                            canvas_module_id="202",
                            canvas_course_id="101",
                            title="Future type",
                            position=None,
                            item_type="FutureCanvasType",
                        ),
                        ModuleItemSnapshot(
                            canvas_module_item_id="1002",
                            canvas_module_id="202",
                            canvas_course_id="101",
                            title="Homework 1",
                            position=2,
                            item_type="Assignment",
                            content_id="501",
                        ),
                        ModuleItemSnapshot(
                            canvas_module_item_id="1001",
                            canvas_module_id="202",
                            canvas_course_id="101",
                            title="Lecture 02.pdf",
                            position=1,
                            item_type="File",
                            content_id="7002",
                            external_url="https://untrusted.example/never-fetch",
                        ),
                    ),
                ),
                ModuleSnapshot(
                    canvas_module_id="201",
                    canvas_course_id="101",
                    name="Introduction",
                    position=1,
                ),
            ],
            synced_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/modules", "/api/modules?course_id=101", "/api/courses/101/modules"],
)
async def test_module_apis_read_local_database_in_deterministic_order(
    path: str,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_structure(session_factory)

    async def fail_if_called(*_: object, **__: object) -> list[dict[str, object]]:
        raise AssertionError("local module GET APIs must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_paginated", fail_if_called)
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [entry["canvas_module_id"] for entry in payload] == ["201", "202"]
    assert [entry["canvas_module_item_id"] for entry in payload[1]["items"]] == [
        "1001",
        "1002",
        "1003",
    ]
    assignment = payload[1]["items"][1]["assignment"]
    assert assignment["canvas_assignment_id"] == "501"
    assert "id" not in payload[0]
    assert payload[1]["items"][2]["item_type"] == "FutureCanvasType"


@pytest.mark.asyncio
async def test_course_filter_is_canvas_id_and_missing_assignment_is_unresolved(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        first = add_course(session, "101")
        add_course(session, "102")
        ModuleRepository(session).synchronize_course(
            first,
            [
                ModuleSnapshot(
                    canvas_module_id="201",
                    canvas_course_id="101",
                    items=(
                        ModuleItemSnapshot(
                            canvas_module_item_id="1001",
                            canvas_module_id="201",
                            canvas_course_id="101",
                            item_type="Assignment",
                            content_id="missing",
                        ),
                    ),
                )
            ],
            synced_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        session.commit()

    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/modules", params={"course_id": "101"})
            invalid = await client.get("/api/modules", params={"course_id": "bad id"})
            absent = await client.get("/api/courses/102/modules")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["canvas_course_id"] == "101"
    assert response.json()[0]["items"][0]["assignment"] is None
    assert invalid.status_code == 422
    assert absent.status_code == 200 and absent.json() == []


def test_course_repository_still_lists_courses_after_module_relationships(session: Session) -> None:
    add_course(session, "101")
    assert [course.canvas_course_id for course in CourseRepository(session).list_all()] == ["101"]
