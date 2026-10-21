from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.assignments.models import AssignmentSnapshot
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasAPIError
from app.canvas.modules import CanvasModuleSource
from app.database.assignment_repository import AssignmentRepository
from app.database.models import Assignment, CourseModule, ModuleItem
from app.database.module_repository import ModuleRepository
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from app.services.module_sync import ModuleSyncService
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import canvas_module_item_payload, canvas_module_payload
from tests.services.test_assignment_sync import add_course


class FakeModuleSource:
    def __init__(self, results: dict[str, list[ModuleSnapshot] | Exception]) -> None:
        self.results = results

    async def fetch_course_modules(self, canvas_course_id: str) -> list[ModuleSnapshot]:
        result = self.results[canvas_course_id]
        if isinstance(result, Exception):
            raise result
        return result


def item(
    item_id: str = "1001",
    *,
    course_id: str = "101",
    module_id: str = "201",
    title: str = "Lecture 01.pdf",
    position: int | None = 1,
    item_type: str = "File",
    content_id: str | None = "7001",
) -> ModuleItemSnapshot:
    return ModuleItemSnapshot(
        canvas_module_item_id=item_id,
        canvas_module_id=module_id,
        canvas_course_id=course_id,
        title=title,
        position=position,
        item_type=item_type,
        content_id=content_id,
        indent=0,
        published=True,
    )


def module(
    module_id: str = "201",
    *,
    course_id: str = "101",
    name: str = "Introduction",
    position: int | None = 1,
    items: tuple[ModuleItemSnapshot, ...] | None = None,
) -> ModuleSnapshot:
    return ModuleSnapshot(
        canvas_module_id=module_id,
        canvas_course_id=course_id,
        name=name,
        position=position,
        workflow_state="active",
        published=True,
        items_count=len(items or ()),
        items=items or (),
    )


@pytest.mark.asyncio
async def test_first_sync_creates_then_identical_sync_is_idempotent(session: Session) -> None:
    add_course(session, "101")
    first_at = datetime(2026, 9, 28, 13, 0, tzinfo=UTC)
    second_at = first_at + timedelta(hours=1)
    source = FakeModuleSource({"101": [module(items=(item(),))]})

    first = await ModuleSyncService(
        source=source, session=session, clock=lambda: first_at
    ).synchronize()
    second = await ModuleSyncService(
        source=source, session=session, clock=lambda: second_at
    ).synchronize()

    stored_module = session.scalar(select(CourseModule))
    stored_item = session.scalar(select(ModuleItem))
    assert first.modules_created == first.items_created == 1
    assert second.modules_unchanged == second.items_unchanged == 1
    assert session.scalar(select(func.count()).select_from(CourseModule)) == 1
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 1
    assert stored_module is not None and stored_item is not None
    assert stored_module.first_seen_at == first_at
    assert stored_item.last_synced_at == second_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("module_name", "Renamed"),
        ("module_position", 4),
        ("item_title", "Renamed item"),
        ("item_position", 5),
        ("content_id", "7999"),
    ],
)
async def test_metadata_and_order_changes_update_existing_rows(
    change: str,
    expected: str | int,
    session: Session,
) -> None:
    add_course(session, "101")
    source = FakeModuleSource({"101": [module(items=(item(),))]})
    await ModuleSyncService(source=source, session=session).synchronize()
    changed_item = item(
        title="Renamed item" if change == "item_title" else "Lecture 01.pdf",
        position=5 if change == "item_position" else 1,
        content_id="7999" if change == "content_id" else "7001",
    )
    source.results["101"] = [
        module(
            name="Renamed" if change == "module_name" else "Introduction",
            position=4 if change == "module_position" else 1,
            items=(changed_item,),
        )
    ]

    summary = await ModuleSyncService(source=source, session=session).synchronize()

    stored_module = session.scalar(select(CourseModule))
    stored_item = session.scalar(select(ModuleItem))
    assert stored_module is not None and stored_item is not None
    if change.startswith("module"):
        assert summary.modules_updated == 1
        assert getattr(stored_module, change.removeprefix("module_")) == expected
    else:
        assert summary.items_updated == 1
        field = "title" if change == "item_title" else change.removeprefix("item_")
        assert getattr(stored_item, field) == expected


@pytest.mark.asyncio
async def test_missing_modules_and_items_are_not_deleted(session: Session) -> None:
    add_course(session, "101")
    source = FakeModuleSource({"101": [module(items=(item(),))]})
    await ModuleSyncService(source=source, session=session).synchronize()
    source.results["101"] = []

    await ModuleSyncService(source=source, session=session).synchronize()

    assert session.scalar(select(func.count()).select_from(CourseModule)) == 1
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 1


@pytest.mark.asyncio
async def test_item_can_move_between_modules_without_duplication(session: Session) -> None:
    add_course(session, "101")
    source = FakeModuleSource(
        {
            "101": [
                module("201", items=(item(module_id="201"),)),
                module("202", name="Kinematics", position=2),
            ]
        }
    )
    await ModuleSyncService(source=source, session=session).synchronize()
    source.results["101"] = [
        module("201"),
        module("202", name="Kinematics", position=2, items=(item(module_id="202"),)),
    ]

    summary = await ModuleSyncService(source=source, session=session).synchronize()
    stored = session.scalar(select(ModuleItem))

    assert summary.items_updated == 1
    assert stored is not None and stored.module.canvas_module_id == "202"
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 1


@pytest.mark.asyncio
async def test_multiple_courses_are_isolated_and_one_failure_does_not_rollback_other(
    session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_course(session, "101")
    add_course(session, "102")
    marker = "private-module-title-marker"
    source = FakeModuleSource(
        {
            "101": [module(name=marker, items=(item(),))],
            "102": CanvasAPIError("Canvas returned 503 for GET /safe/path"),
        }
    )
    caplog.set_level("INFO")

    summary = await ModuleSyncService(source=source, session=session).synchronize()

    assert summary.courses_succeeded == 1
    assert summary.courses_failed == 1
    assert session.scalar(select(func.count()).select_from(CourseModule)) == 1
    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_same_module_and_item_ids_are_isolated_by_course(session: Session) -> None:
    add_course(session, "101")
    add_course(session, "102")
    source = FakeModuleSource(
        {
            "101": [module(items=(item(),))],
            "102": [
                module(
                    course_id="102",
                    items=(item(course_id="102"),),
                )
            ],
        }
    )

    summary = await ModuleSyncService(source=source, session=session).synchronize()

    assert summary.modules_created == 2
    assert summary.items_created == 2
    assert session.scalar(select(func.count()).select_from(CourseModule)) == 2
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 2


@pytest.mark.asyncio
async def test_conflicting_item_snapshots_roll_back_complete_course(session: Session) -> None:
    add_course(session, "101")
    source = FakeModuleSource(
        {
            "101": [
                module("201", items=(item(),)),
                module("202", items=(item(module_id="202", title="conflict"),)),
            ]
        }
    )

    summary = await ModuleSyncService(source=source, session=session).synchronize()

    assert summary.courses_failed == 1
    assert session.scalar(select(func.count()).select_from(CourseModule)) == 0
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 0


@pytest.mark.asyncio
async def test_module_list_success_then_item_fetch_failure_persists_nothing(
    session: Session,
) -> None:
    add_course(session, "101")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/modules"):
            first = canvas_module_payload("201", items=[canvas_module_item_payload()])
            second = canvas_module_payload("202", name="Second", items=None)
            second.pop("items")
            return httpx.Response(200, json=[first, second])
        return httpx.Response(503, json={"private": "body must not escape"})

    async with CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        summary = await ModuleSyncService(
            source=CanvasModuleSource(client),
            session=session,
        ).synchronize()

    assert summary.courses_failed == 1
    assert session.scalar(select(func.count()).select_from(CourseModule)) == 0
    assert session.scalar(select(func.count()).select_from(ModuleItem)) == 0
    assert "private" not in summary.failures[0].message


@pytest.mark.asyncio
async def test_successful_retry_after_failed_fetch_persists_complete_structure(
    session: Session,
) -> None:
    add_course(session, "101")
    source = FakeModuleSource({"101": CanvasAPIError("temporary failure")})
    first = await ModuleSyncService(source=source, session=session).synchronize()
    source.results["101"] = [module(items=(item(),))]

    second = await ModuleSyncService(source=source, session=session).synchronize()

    assert first.courses_failed == 1
    assert second.courses_succeeded == 1
    assert second.modules_created == second.items_created == 1


@pytest.mark.asyncio
async def test_assignment_reference_requires_no_assignment_and_creates_no_fake_row(
    session: Session,
) -> None:
    course = add_course(session, "101")
    assignment_item = item(item_type="Assignment", content_id="501")
    summary = await ModuleSyncService(
        source=FakeModuleSource({"101": [module(items=(assignment_item,))]}),
        session=session,
    ).synchronize()

    assert summary.items_created == 1
    assert session.scalar(select(func.count()).select_from(Assignment)) == 0
    assert course.id is not None


def test_declared_foreign_keys_are_enforced(session: Session) -> None:
    invalid = ModuleItem(
        course_id=999,
        module_id=999,
        canvas_module_item_id="orphan",
        item_type="File",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


@pytest.mark.asyncio
async def test_missing_and_equal_positions_use_stable_identity_fallback(session: Session) -> None:
    add_course(session, "101")
    source = FakeModuleSource(
        {
            "101": [
                module(
                    "203",
                    position=None,
                    items=(item("1003", module_id="203", position=None),),
                ),
                module(
                    "202",
                    position=1,
                    items=(item("1002", module_id="202", position=1),),
                ),
                module(
                    "201",
                    position=1,
                    items=(
                        item("1005", module_id="201", position=None),
                        item("1004", module_id="201", position=1),
                    ),
                ),
            ]
        }
    )
    await ModuleSyncService(source=source, session=session).synchronize()

    ordered = ModuleRepository(session).list_ordered(canvas_course_id="101")

    assert [entry.canvas_module_id for entry in ordered] == ["201", "202", "203"]
    assert [entry.canvas_module_item_id for entry in ordered[0].items] == ["1004", "1005"]


def seed_assignment(session: Session) -> None:
    course = add_course(session, "101")
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
    session.commit()
